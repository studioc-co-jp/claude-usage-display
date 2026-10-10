"""Antigravity（Google）の Gemini の利用枠を、公式の CLI（``agy``）の ``/usage`` で読む。

Google の内部 API を自分で呼ばず、``agy`` に聞く。``agy`` は自分のログイン情報で認証するので、
このプログラムは Antigravity のトークンを読まない（2026-10-11、agy 1.3.1 で確かめた。docs/handover.md §4-10）。

    agy -p /usage --output-format json --print-timeout 20s --log-file <自前のファイル>

- 応答は 1 行の JSON。``command.data.groups`` の各グループ（「Gemini Models」「Claude and GPT models」）に、
  ``window`` が ``5h`` と ``weekly`` の枠（``remaining_fraction``・``reset_time``）がある。画面には Gemini の
  グループの 2 つを出す
- **agy 1.1.11 より古い版は ``/usage`` をプロンプトとして扱い、枠を使ってしまう**（Orca 1.4.222 のコードの注記）。
  版を確かめてから呼び、応答に ``num_turns`` が 1 以上か ``conversation_id`` があれば、以後は呼ばない
- 1 回の実行は約 6 秒。agy は言語サーバーを起動し、内部 API を数回呼ぶ。実行するたびに
  ``~/.gemini/antigravity-cli/implicit/`` に 450 バイトほどのファイルが 1 つ増える。間隔は長めにする
- ログは ``--log-file`` で自前のファイルに向ける。付けないと、1 回 21 KB のログが agy のログのフォルダに増え、
  最新のログを指す ``cli.log`` の向きも変わる（Orca などで動いている agy のログを追いにくくなる）
- agy は実行したフォルダを作業場所として扱うので、専用の空のフォルダで実行する
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .usage import Meter, Snapshot

MIN_VERSION = (1, 1, 11)
USAGE_ARGS = ("-p", "/usage", "--output-format", "json", "--print-timeout", "20s")
TIMEOUT_SECONDS = 60
# launchd は PATH を渡さないので、Homebrew の置き場所も探す
SEARCH_PATHS = ("/opt/homebrew/bin/agy", "/usr/local/bin/agy")
WORKDIR = Path.home() / "Library" / "Application Support" / "claude-usage-display" / "agy"
GROUP = "gemini"  # グループ名にこの語を含むもの（「Gemini Models」）
WINDOWS = (("5h", "5時間"), ("weekly", "週次"))
LABELS = tuple(label for _window, label in WINDOWS)
ERROR_MARK = "AGY_ERROR:"
SIGNED_OUT = ("not logged into antigravity", "not logged in", "not signed in", "not authenticated",
              "unauthenticated", "run agy login", "please sign in", "please log in")


class AntigravityError(Exception):
    """取得に失敗した。``message`` は画面に出す短い日本語。``permanent`` は、もう呼ばないほうがよい失敗。"""

    def __init__(self, message: str, *, permanent: bool = False):
        super().__init__(message)
        self.message = message
        self.permanent = permanent


def parse_version(text: str) -> tuple[int, ...] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    return tuple(int(part) for part in match.groups()) if match else None


def find_agy(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit if os.access(explicit, os.X_OK) else None
    found = shutil.which("agy")
    if found:
        return found
    return next((path for path in SEARCH_PATHS if os.access(path, os.X_OK)), None)


def _json_lines(text: str):
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict):
                yield value


def _error_message(text: str) -> str | None:
    """agy が出した失敗の説明を、画面に出す日本語にする。"""
    for line in text.splitlines():
        if ERROR_MARK not in line:
            continue
        try:
            error = json.loads(line.split(ERROR_MARK, 1)[1].strip())
        except ValueError:
            continue
        status = str(error.get("status", "")).upper()
        code = error.get("error_code")
        if status == "UNAUTHENTICATED" or code == 401:
            return "Antigravity にログインしていません"
        if status == "PERMISSION_DENIED" or code == 403:
            return "Antigravity の利用枠がありません"
        if status == "RESOURCE_EXHAUSTED" or code == 429:
            return "取得の間隔を空けるよう求められました"
        if isinstance(code, int) and 500 <= code < 600:
            return "Antigravity のサーバーの障害です"
    lowered = text.lower()
    if any(mark in lowered for mark in SIGNED_OUT):
        return "Antigravity にログインしていません"
    return None


def _parse_time(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_usage(stdout: str, stderr: str, now: datetime) -> Snapshot:
    """``/usage`` の出力から、Gemini のグループの 5 時間と週の枠を取り出す。"""
    for value in _json_lines(stdout):
        turns = value.get("num_turns")
        if (isinstance(turns, int) and turns > 0) or value.get("conversation_id"):
            raise AntigravityError("agy が /usage を命令として扱いませんでした。取得をやめました", permanent=True)
    for value in _json_lines(stdout):
        command = value.get("command")
        if value.get("status") != "SUCCESS" or not isinstance(command, dict) or command.get("name") != "usage":
            continue
        groups = (command.get("data") or {}).get("groups") or []
        for group in groups:
            if not isinstance(group, dict) or GROUP not in str(group.get("name", "")).lower():
                continue
            buckets = {b.get("window"): b for b in group.get("buckets") or []
                       if isinstance(b, dict) and b.get("disabled") is not True}
            meters = []
            for window, label in WINDOWS:
                bucket = buckets.get(window)
                fraction = bucket.get("remaining_fraction") if bucket else None
                if not isinstance(fraction, (int, float)):
                    meters.append(Meter(label, None, None))
                    continue
                percent = min(100.0, max(0.0, (1 - fraction) * 100))
                meters.append(Meter(label, percent, _parse_time(bucket.get("reset_time"))))
            if all(m.percent is None for m in meters):
                raise AntigravityError("Gemini の枠が応答にありません")
            return Snapshot(tuple(meters), now)
        raise AntigravityError("Gemini の枠が応答にありません")
    raise AntigravityError(_error_message(f"{stdout}\n{stderr}") or "利用枠を読めませんでした")


class AntigravityReader:
    """``agy`` を実行して Gemini の利用枠を読む。"""

    def __init__(self, agy: str | None = None, workdir: Path = WORKDIR, run=subprocess.run):
        self.agy = agy
        self.workdir = Path(workdir)
        self.run = run
        self.checked_version = False

    def _path(self) -> str:
        path = find_agy(self.agy)
        if path is None:
            raise AntigravityError("agy（Antigravity の CLI）が見つかりません")
        return path

    def _environment(self) -> dict[str, str]:
        env = dict(os.environ)
        paths = env.get("PATH", "").split(os.pathsep)
        env["PATH"] = os.pathsep.join(paths + [p for p in ("/opt/homebrew/bin", "/usr/local/bin") if p not in paths])
        return env

    def _check_version(self, path: str) -> None:
        try:
            result = self.run([path, "--version"], capture_output=True, text=True, timeout=10, env=self._environment())
        except (OSError, subprocess.TimeoutExpired) as e:
            raise AntigravityError(f"agy を起動できません（{type(e).__name__}）") from e
        version = parse_version(result.stdout or result.stderr or "")
        if version is None:
            raise AntigravityError("agy の版を読めません", permanent=True)
        if version < MIN_VERSION:
            needed = ".".join(map(str, MIN_VERSION))
            raise AntigravityError(f"agy {needed} 以上が要ります（いまは {'.'.join(map(str, version))}）",
                                   permanent=True)
        self.checked_version = True

    def fetch(self, now: datetime | None = None) -> Snapshot:
        path = self._path()
        if not self.checked_version:
            self._check_version(path)
        self.workdir.mkdir(parents=True, exist_ok=True)
        log_file = self.workdir / "agy.log"
        log_file.unlink(missing_ok=True)  # 直近の 1 回分だけ残す
        try:
            result = self.run([path, *USAGE_ARGS, "--log-file", str(log_file)], capture_output=True, text=True,
                              timeout=TIMEOUT_SECONDS, cwd=self.workdir, env=self._environment())
        except subprocess.TimeoutExpired as e:
            raise AntigravityError("agy が時間内に答えませんでした") from e
        except OSError as e:
            raise AntigravityError(f"agy を起動できません（{type(e).__name__}）") from e
        return parse_usage(result.stdout or "", result.stderr or "", now or datetime.now(timezone.utc))
