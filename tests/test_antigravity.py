import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from claude_usage_display import antigravity as ag

NOW = datetime(2026, 10, 11, 2, 0, tzinfo=timezone.utc)


def usage_line(groups=None, **top):
    """agy の /usage の応答のうち、使う項目だけを持つ 1 行（実際の応答は残さない）。"""
    if groups is None:
        groups = [
            {"name": "Gemini Models", "buckets": [
                {"id": "gemini-weekly", "window": "weekly", "remaining_fraction": 0.94, "reset_time": "2026-10-14T07:31:00Z"},
                {"id": "gemini-5h", "window": "5h", "remaining_fraction": 0.98, "reset_time": "2026-10-10T18:37:00Z"},
            ]},
            {"name": "Claude and GPT models", "buckets": [
                {"id": "3p-5h", "window": "5h", "remaining_fraction": 1.0, "reset_time": "2026-10-10T21:54:00Z"},
            ]},
        ]
    value = {"status": "SUCCESS", "num_turns": 0, "conversation_id": "",
             "command": {"name": "usage", "data": {"groups": groups}}}
    value.update(top)
    return json.dumps(value)


class ParseTest(unittest.TestCase):
    def test_reads_the_gemini_group_in_five_hour_then_weekly_order(self):
        snapshot = ag.parse_usage(usage_line() + "\n", "", NOW)
        self.assertEqual([m.label for m in snapshot.meters], ["5時間", "週次"])
        self.assertEqual([round(m.percent) for m in snapshot.meters], [2, 6])
        self.assertEqual(snapshot.meters[0].resets_at, datetime(2026, 10, 10, 18, 37, tzinfo=timezone.utc))
        self.assertEqual(snapshot.fetched_at, NOW)

    def test_a_prompt_instead_of_a_command_stops_for_good(self):
        for extra in ({"num_turns": 1}, {"conversation_id": "abc"}):
            with self.subTest(extra=extra), self.assertRaises(ag.AntigravityError) as caught:
                ag.parse_usage(usage_line(**extra), "", NOW)
            self.assertTrue(caught.exception.permanent)

    def test_errors_become_short_japanese(self):
        cases = {
            'AGY_ERROR: {"status": "UNAUTHENTICATED", "error_code": 401}': "Antigravity にログインしていません",
            'AGY_ERROR: {"status": "RESOURCE_EXHAUSTED", "error_code": 429}': "取得の間隔を空けるよう求められました",
            "Error: You are not logged into Antigravity.": "Antigravity にログインしていません",
            "": "利用枠を読めませんでした",
        }
        for stderr, message in cases.items():
            with self.subTest(stderr=stderr), self.assertRaises(ag.AntigravityError) as caught:
                ag.parse_usage("", stderr, NOW)
            self.assertEqual(caught.exception.message, message)
            self.assertFalse(caught.exception.permanent)

    def test_missing_gemini_group_or_disabled_buckets(self):
        with self.assertRaises(ag.AntigravityError):
            ag.parse_usage(usage_line(groups=[{"name": "Claude and GPT models", "buckets": []}]), "", NOW)
        groups = [{"name": "Gemini Models", "buckets": [
            {"window": "5h", "remaining_fraction": 0.5, "reset_time": "2026-10-10T18:37:00Z", "disabled": True},
            {"window": "weekly", "remaining_fraction": 0.25, "reset_time": "2026-10-14T07:31:00Z"}]}]
        meters = ag.parse_usage(usage_line(groups=groups), "", NOW).meters
        self.assertEqual([(m.label, m.percent) for m in meters], [("5時間", None), ("週次", 75.0)])

    def test_version(self):
        self.assertEqual(ag.parse_version("1.3.1\n"), (1, 3, 1))
        self.assertIsNone(ag.parse_version("unknown"))
        self.assertLess(ag.parse_version("agy 1.1.10"), ag.MIN_VERSION)


class FakeRun:
    def __init__(self, version="1.3.1", stdout=None):
        self.version = version
        self.stdout = usage_line() if stdout is None else stdout
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        out = self.version if args[-1] == "--version" else self.stdout
        return subprocess.CompletedProcess(args, 0, out, "")


class ReaderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.agy = Path(self.tmp.name) / "agy"
        self.agy.write_text("#!/bin/sh\n")
        self.agy.chmod(0o755)
        self.workdir = Path(self.tmp.name) / "work"

    def test_runs_usage_in_its_own_folder_with_its_own_log(self):
        run = FakeRun()
        reader = ag.AntigravityReader(str(self.agy), self.workdir, run)
        reader.fetch(NOW)
        reader.fetch(NOW)
        self.assertEqual([c[0][-1] for c in run.calls].count("--version"), 1)  # 版は最初の 1 回だけ確かめる
        args, kwargs = run.calls[-1]
        self.assertEqual(args[1:7], list(ag.USAGE_ARGS))
        self.assertEqual(args[7:], ["--log-file", str(self.workdir / "agy.log")])
        self.assertEqual(kwargs["cwd"], self.workdir)
        self.assertIn("/opt/homebrew/bin", kwargs["env"]["PATH"].split(":"))

    def test_old_version_is_refused_before_asking_usage(self):
        run = FakeRun(version="1.1.10")
        with self.assertRaises(ag.AntigravityError) as caught:
            ag.AntigravityReader(str(self.agy), self.workdir, run).fetch(NOW)
        self.assertTrue(caught.exception.permanent)
        self.assertEqual(len(run.calls), 1)

    def test_missing_agy(self):
        with self.assertRaises(ag.AntigravityError) as caught:
            ag.AntigravityReader(str(self.agy) + "-none", self.workdir, FakeRun()).fetch(NOW)
        self.assertFalse(caught.exception.permanent)


if __name__ == "__main__":
    unittest.main()
