"""席を離れているかを、キーボード・マウスの無操作の時間で判定する。ディスプレイの焼き付き対策の消灯に使う。

無操作の時間は、macOS の IOHIDSystem の ``HIDIdleTime``（最後の入力からのナノ秒）を ``ioreg`` で読む
（1 回 10 ミリ秒ほど。WindowServer にも TCC にも問い合わせない）。

- Mac の画面が消えたかを、CoreGraphics の ``CGDisplayIsAsleep`` で問い合わせる方法は使わない。WindowServer に
  接続して問い合わせることになり、2026-10-15 に試した直後に Mac がフリーズした（原因は ESET と trustd の
  行き詰まりで、問い合わせとの関係は確定しなかった。docs/handover.md §4-12）
- ``ioreg`` の ``IOMobileFramebufferShim`` の ``CurrentPowerState`` は、Mac の画面が消えても 1 のままで使えなかった
- この Mac は無操作 10 分で画面を消す設定（``pmset -g`` の ``displaysleep 10``）なので、既定の 10 分で、
  Mac の画面とほぼ同じ時に消える
"""

from __future__ import annotations

import logging
import re
import subprocess

IOREG = ("/usr/sbin/ioreg", "-c", "IOHIDSystem", "-d", "4")
POLL_SECONDS = 5  # 席を離れたかを確かめる間隔。操作が戻ってから点くまで、最長でこの秒数かかる
DEFAULT_AWAY_MINUTES = 10

log = logging.getLogger("claude_usage_display")


def parse_idle_seconds(text: str) -> float | None:
    match = re.search(r'"HIDIdleTime" = (\d+)', text)
    return int(match.group(1)) / 1e9 if match else None


def idle_seconds(run=subprocess.run) -> float | None:
    """キーボード・マウスを最後に触ってからの秒数。読めなければ None。"""
    try:
        result = run(IOREG, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse_idle_seconds(result.stdout or "")


class Presence:
    """``away_minutes`` 分以上キーボードとマウスを触っていなければ、席を離れているとみなす。0 なら判定しない。"""

    def __init__(self, away_minutes: float, read=idle_seconds):
        self.away_after = away_minutes * 60
        self.read = read
        self.failed = False

    @property
    def enabled(self) -> bool:
        return self.away_after > 0

    def away(self) -> bool:
        if not self.enabled:
            return False
        idle = self.read()
        if idle is None:  # 読めないときは、消したまま戻らなくなるより、表示を続ける
            if not self.failed:
                log.warning("無操作の時間を読めません。消灯せずに表示を続けます")
                self.failed = True
            return False
        self.failed = False
        return idle >= self.away_after
