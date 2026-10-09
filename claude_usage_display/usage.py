"""利用枠の取得。

Claude Code が macOS の Keychain に保存したログイン情報（アクセストークン）を読み、
``https://api.anthropic.com/api/oauth/usage`` から利用枠を取得する。

ログイン情報は読むだけで、書き換えない。アクセストークンの期限切れは Claude Code が
次に起動したときに更新するため、ここではリフレッシュトークンを使わない。
（tokscale は更新結果を書き戻して Claude Code のログインを壊した。junhoyeo/tokscale #1001）
"""

from __future__ import annotations

import email.utils
import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
BETA_HEADER = "oauth-2025-04-20"
KEYCHAIN_SERVICE = "Claude Code-credentials"

# Retry-After がこれより長くても、この秒数で打ち切る（壊れた値で何時間も止まらないため）
MAX_RETRY_AFTER = 3600


@dataclass(frozen=True)
class Meter:
    label: str
    percent: float | None
    resets_at: datetime | None


@dataclass(frozen=True)
class Snapshot:
    meters: tuple[Meter, ...]
    fetched_at: datetime


class UsageError(Exception):
    """取得に失敗した。``message`` は画面に出す短い日本語。

    ``rate_limited`` は HTTP 429（間隔を空けるよう求められた）。``detail`` はログにだけ残す補足で、
    429 の Retry-After などを入れる。アクセストークンや利用者を識別する値は入れない。
    """

    def __init__(self, message: str, retry_after: int | None = None, *, rate_limited: bool = False,
                 detail: str | None = None):
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after
        self.rate_limited = rate_limited
        self.detail = detail


def read_access_token() -> str:
    try:
        proc = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as e:
        raise UsageError("Keychain の応答がありません") from e
    if proc.returncode != 0:
        raise UsageError("Keychain にログイン情報がありません")
    try:
        token = json.loads(proc.stdout)["claudeAiOauth"]["accessToken"]
    except (ValueError, KeyError, TypeError) as e:
        raise UsageError("ログイン情報の形式が想定と違います") from e
    if not isinstance(token, str) or not token:
        raise UsageError("ログイン情報にトークンがありません")
    return token


def parse_retry_after(value: str | None, now: datetime | None = None) -> int | None:
    """Retry-After（秒数または HTTP 日付）を秒数にする。"""
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        seconds = int(value)
    else:
        try:
            when = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        seconds = int((when - (now or datetime.now(timezone.utc))).total_seconds())
    return max(0, min(seconds, MAX_RETRY_AFTER))


def describe_rate_limit(raw: str | None, seconds: int | None, headers) -> str:
    """429 のときにログへ残す説明。Retry-After と、名前に ratelimit を含む見出しだけを並べる。"""
    parts = [f"HTTP 429。Retry-After: {raw or 'なし'}" + ("" if seconds is None else f" → {seconds} 秒")]
    parts += [f"{name}: {value}" for name, value in (headers.items() if headers else ()) if "ratelimit" in name.lower()]
    return "。".join(parts)


def fetch_raw(token: str, timeout: float = 15) -> dict:
    req = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "anthropic-beta": BETA_HEADER,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise UsageError("ログイン切れ（Claude Code を起動すると戻ります）") from e
        if e.code == 429:
            raw = e.headers.get("Retry-After") if e.headers else None
            seconds = parse_retry_after(raw)
            raise UsageError("取得の間隔を空けています", seconds, rate_limited=True,
                             detail=describe_rate_limit(raw, seconds, e.headers)) from e
        raise UsageError(f"取得に失敗しました（HTTP {e.code}）") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise UsageError("通信できません") from e
    except ValueError as e:
        raise UsageError("応答を読めません") from e
    if not isinstance(body, dict):
        raise UsageError("応答を読めません")
    return body


def _parse_time(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        when = datetime.fromisoformat(value)
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _percent(value) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _limits(body: dict) -> list[dict]:
    limits = body.get("limits")
    return [e for e in limits if isinstance(e, dict)] if isinstance(limits, list) else []


def _pick(entries: list[dict]) -> dict | None:
    """同じ枠が複数あれば、いま効いている枠（is_active）を優先する。"""
    if not entries:
        return None
    return next((e for e in entries if e.get("is_active") is True), entries[0])


def _model_matches(entry: dict, model: str) -> bool:
    scoped = ((entry.get("scope") or {}).get("model")) or {}
    name = scoped.get("display_name")
    model_id = scoped.get("id")
    wanted = model.casefold()
    return (isinstance(name, str) and name.strip().casefold() == wanted) or (
        isinstance(model_id, str) and wanted in model_id.casefold()
    )


def _from_limit(label: str, entry: dict | None) -> Meter | None:
    if entry is None:
        return None
    return Meter(label, _percent(entry.get("percent")), _parse_time(entry.get("resets_at")))


def _from_window(label: str, window) -> Meter | None:
    if not isinstance(window, dict):
        return None
    return Meter(label, _percent(window.get("utilization")), _parse_time(window.get("resets_at")))


def meter_labels(model: str = "Fable") -> tuple[str, str, str]:
    """3 本のメーターの名前（5 時間・週次・モデル別週次）。値が無いときの画面にも使う。"""
    return "5時間", "週次", f"{model}週次"


def parse_usage(body: dict, model: str = "Fable") -> tuple[Meter, ...]:
    """応答から「5 時間・週次・モデル別週次」の 3 本を取り出す。

    ``limits`` 配列を正とし、無い場合だけ旧来の ``five_hour`` / ``seven_day`` を使う。
    モデル別の週次上限は ``limits`` の ``kind: "weekly_scoped"`` にしか現れない。
    """
    session_label, weekly_label, scoped_label = meter_labels(model)
    limits = _limits(body)
    session = _from_limit(session_label, _pick([e for e in limits if e.get("kind") == "session"]))
    weekly = _from_limit(weekly_label, _pick([e for e in limits if e.get("kind") == "weekly_all"]))
    scoped = _from_limit(
        scoped_label,
        _pick([e for e in limits if e.get("kind") == "weekly_scoped" and _model_matches(e, model)]),
    )
    return (
        session or _from_window(session_label, body.get("five_hour")) or Meter(session_label, None, None),
        weekly or _from_window(weekly_label, body.get("seven_day")) or Meter(weekly_label, None, None),
        scoped or Meter(scoped_label, None, None),
    )


def fetch_snapshot(model: str = "Fable") -> Snapshot:
    body = fetch_raw(read_access_token())
    return Snapshot(parse_usage(body, model), datetime.now(timezone.utc))
