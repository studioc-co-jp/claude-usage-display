import argparse
import unittest
from datetime import datetime, timezone
from unittest import mock

from claude_usage_display import __main__ as cli
from claude_usage_display.turing import Command, encode_command
from claude_usage_display.usage import Meter, Snapshot, UsageError

LANDSCAPE_HEADER = encode_command(Command.DISPLAY_BITMAP, 0, 0, 479, 319)


def make_args(**overrides):
    values = dict(model="Fable", brightness=30, flip=False, interval=120, save_png=None, theme="gauge")
    values.update(overrides)
    return argparse.Namespace(**values)


def snapshot():
    now = datetime.now(timezone.utc)
    return Snapshot((Meter("5時間", 26, now), Meter("週次", 3, now), Meter("Fable週次", 0, now)), now)


class StopAfterFrames:
    """横向きの画面を ``frames`` 枚受け取ったら、ループに終了の合図を出す送信路。"""

    def __init__(self, runner, frames=1):
        self.runner = runner
        self.frames = frames
        self.writes = []

    def write(self, data):
        self.writes.append(bytes(data))
        if data == LANDSCAPE_HEADER:
            self.frames -= 1
        elif self.frames == 0 and sum(map(len, self.writes[self.writes.index(LANDSCAPE_HEADER) + 1:])) == 480 * 320 * 2:
            self.runner.stop.set()

    def close(self):
        pass


class RunnerTest(unittest.TestCase):
    def test_connects_fetches_and_sends_one_full_frame(self):
        runner = cli.Runner(make_args())
        transport = StopAfterFrames(runner)
        with mock.patch.object(cli.UsbTransport, "open", return_value=transport), \
                mock.patch.object(cli, "fetch_snapshot", return_value=snapshot()) as fetch:
            self.assertEqual(runner.loop(), 0)
        fetch.assert_called_once_with("Fable")
        self.assertIn(LANDSCAPE_HEADER, transport.writes)
        self.assertIsNone(runner.status)

    def test_fetch_error_keeps_running_and_respects_retry_after(self):
        runner = cli.Runner(make_args())
        transport = StopAfterFrames(runner)
        with mock.patch.object(cli.UsbTransport, "open", return_value=transport), \
                mock.patch.object(cli, "fetch_snapshot", side_effect=UsageError("取得の間隔を空けています", 900)), \
                mock.patch.object(cli.time, "monotonic", return_value=1000.0):
            runner.loop()
        self.assertEqual(runner.status, "取得の間隔を空けています")
        self.assertEqual(runner.next_fetch, 1900.0)

    def test_waits_without_fetching_while_device_is_absent(self):
        runner = cli.Runner(make_args())

        def absent():
            runner.stop.set()
            raise cli.DeviceNotFound("未接続")

        with mock.patch.object(cli.UsbTransport, "open", side_effect=absent), \
                mock.patch.object(cli, "fetch_snapshot") as fetch:
            runner.loop()
        fetch.assert_not_called()

    def test_labels_follow_model_when_nothing_was_fetched(self):
        runner = cli.Runner(make_args(model="Opus"))
        transport = StopAfterFrames(runner)
        draw = mock.Mock(wraps=cli.THEMES["gauge"])
        with mock.patch.object(cli.UsbTransport, "open", return_value=transport), \
                mock.patch.object(cli, "fetch_snapshot", side_effect=UsageError("通信できません")), \
                mock.patch.dict(cli.THEMES, {"gauge": draw}), self.assertLogs(cli.log, "WARNING"):
            runner.loop()
        self.assertEqual(draw.call_args.args[3], ("5時間", "週次", "Opus週次"))


class ArgumentsTest(unittest.TestCase):
    def setUp(self):
        # main() はログの出力先を設定する。後に続くテストの出力にログが混ざらないよう止める
        patcher = mock.patch.object(cli.logging, "basicConfig")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_rejects_out_of_range_options_before_starting(self):
        for argv in (["run", "--brightness", "101"], ["run", "--brightness", "-1"],
                     ["test-pattern", "--brightness", "101"], ["run", "--interval", "59"],
                     ["run", "--theme", "unknown"]):
            with self.subTest(argv=argv), mock.patch.object(cli, "cmd_run") as run, \
                    mock.patch.object(cli, "cmd_test_pattern") as test_pattern, mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit) as raised:
                    cli.main(argv)
                self.assertEqual(raised.exception.code, 2)
                run.assert_not_called()
                test_pattern.assert_not_called()

    def test_accepts_brightness_bounds(self):
        for value in ("0", "100"):
            with self.subTest(value=value), mock.patch.object(cli, "cmd_run", return_value=0) as run:
                self.assertEqual(cli.main(["run", "--brightness", value]), 0)
                self.assertEqual(run.call_args.args[0].brightness, int(value))

    def test_theme_defaults_to_gauge_and_classic_stays_available(self):
        for argv, expected in ((["run"], "gauge"), (["run", "--theme", "classic"], "classic"),
                               (["preview", "--theme", "classic"], "classic")):
            with self.subTest(argv=argv), mock.patch.object(cli, "cmd_run", return_value=0) as run, \
                    mock.patch.object(cli, "cmd_preview", return_value=0) as preview:
                cli.main(argv)
                called = run if argv[0] == "run" else preview
                self.assertEqual(called.call_args.args[0].theme, expected)


if __name__ == "__main__":
    unittest.main()
