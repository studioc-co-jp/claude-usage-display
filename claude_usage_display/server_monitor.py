"""サーバーの状態（CloudWatch のメトリクスと、外形・死活監視の判定）の取得と判定。

``monitor`` コマンドが使う。何を読むか（リージョン・メトリクス・しきい値・監視の状態ファイル）は、
git に入れない設定ファイル（``monitor.toml``。見本は ``monitor.example.toml``）に書く。

- メトリクスは ``cloudwatch:GetMetricStatistics`` で ``period`` 秒ごとの平均を読み、いちばん新しい値を使う
  （GetMetricData は無料の範囲の対象外のため使わない。CloudWatch の料金ページ「Free Tier」）
- 画面を赤にするのは、しきい値以上が ``datapoints`` 回続いたとき。CloudWatch のアラームと同じ ``period`` と
  ``datapoints`` を書けば、アラームと同じ条件で赤になる。1 回だけの山では、リングだけが赤になる
  （2026-10-11。直近 1 回で赤にしていたときは、cron やデプロイの 1〜4 分の山でも画面全体が赤になっていた）
- 監視の状態ファイルは、S3 の JSON（``{"<種類>:<名前>": {"alerting": bool, "reason": str, "since": 秒}}``）
- 確認済みの障害（設定の ``[state.acknowledged]`` に ID と ``since`` を書いたもの）は、その障害が続く間だけ
  判定から外す。解決を待つしかない障害を出し続けると、同じ監視で起きた別の失敗にも、ほかの障害にも気付けなく
  なるため（2026-10-16 ユーザーが決定）。成功に戻ってから再び失敗すると ``since`` が変わるので、また出る
- 鍵は Keychain に置いた読み取り専用の IAM ユーザーのもの（アカウント名 = アクセスキー ID、
  パスワード = シークレット）。値をログや画面に出さない
"""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

METRIC_WINDOW = timedelta(minutes=10)   # 少なくともこの範囲の平均を読む（続けて超えた回数を数えるため、必要なら広げる）
METRIC_STALE = timedelta(minutes=5)     # これより古い値しかなければ「届いていない」（period が長いときは 2 周期）
WARNING_MARGIN = 15                     # しきい値のこれだけ手前からオレンジにする
JST = timezone(timedelta(hours=9))


class ConfigError(Exception):
    pass


class FetchError(Exception):
    """取得に失敗した。``message`` は画面に出す短い日本語。"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class MetricSpec:
    label: str
    namespace: str
    name: str
    dimensions: tuple[tuple[str, str], ...]
    threshold: float
    period: int = 60       # 平均を取る秒数（CloudWatch のアラームの Period）
    datapoints: int = 1    # しきい値以上がこの回数続いたら赤にする（アラームの DatapointsToAlarm）

    @property
    def stale_after(self) -> timedelta:
        return max(METRIC_STALE, timedelta(seconds=2 * self.period))

    @property
    def window(self) -> timedelta:
        return max(METRIC_WINDOW, timedelta(seconds=self.period * (self.datapoints + 2)))


@dataclass(frozen=True)
class MonitorConfig:
    title: str
    region: str
    keychain_service: str
    metrics: tuple[MetricSpec, ...]
    state_bucket: str | None = None
    state_key: str | None = None
    state_stale: timedelta = timedelta(minutes=5)
    red_kinds: tuple[str, ...] = ("http", "tls")
    names: tuple[tuple[str, str], ...] = ()  # 監視の ID → 画面に出す名前
    logo: str | None = None  # 見出しの名前の左に出すロゴの画像（PNG）の絶対パス
    # False なら見出しの名前を出さず、横置きの見出しの行を、異常の表示に大きく使う（2026-10-22 ユーザーの指示）
    show_title: bool = True
    # 確認済みの障害の (種類, 名前) と、障害が始まった時刻（UTC、秒まで）
    acknowledged: tuple[tuple[tuple[str, str], datetime], ...] = ()

    def display_name(self, incident: "Incident") -> str:
        name = dict(self.names).get(incident.name) or incident.label or incident.name
        return f"証明書 {name}" if incident.kind == "tls" else name

    def acknowledges(self, incident: "Incident") -> bool:
        """確認済みの障害か（ID と、障害が始まった時刻が同じ）。"""
        return incident.since is not None and ((incident.kind, incident.name), _second(incident.since)) in self.acknowledged


@dataclass(frozen=True)
class MetricValue:
    spec: MetricSpec
    value: float | None
    at: datetime | None
    streak: int | None = None  # いちばん新しい値から、しきい値以上が続いている回数（None は値だけで判断する）
    # この Mac の状態の画面（local_monitor.py）が使う。サーバーの画面は使わない（None のまま）
    detail: tuple[str, ...] | None = None  # リングの右の下の行（None なら「しきい値 N%」。量を出すときに使う）
    tint: str | None = None  # リングの色の段階（normal・warning・critical）の決め打ち。None ならしきい値で決める

    @property
    def sustained(self) -> bool:
        """しきい値以上が ``datapoints`` 回続いているか。"""
        if self.value is None:
            return False
        streak = self.streak if self.streak is not None else int(self.value >= self.spec.threshold)
        return streak >= self.spec.datapoints


@dataclass(frozen=True)
class Incident:
    kind: str
    name: str
    reason: str
    since: datetime | None
    label: str = ""  # 状態ファイルの表示名（name）。無ければ ID で出す

    @property
    def key(self) -> str:
        """状態ファイルの項目の名前（``<種類>:<名前>``。名前の無い項目は種類だけ）。"""
        return self.kind if self.name == self.kind else f"{self.kind}:{self.name}"


@dataclass(frozen=True)
class MonitorState:
    incidents: tuple[Incident, ...]
    updated_at: datetime


@dataclass(frozen=True)
class ServerStatus:
    metrics: tuple[MetricValue, ...]
    monitor: MonitorState | None
    fetched_at: datetime


@dataclass(frozen=True)
class Assessment:
    """``alerts`` があれば画面全体を赤にする。``warnings`` は見出しにオレンジで出す。

    ``acknowledged`` は、確認済みのため出さなかった障害（ログに残す）。
    """

    alerts: tuple[str, ...]
    warnings: tuple[str, ...]
    alerting_metrics: frozenset[str]
    acknowledged: tuple[str, ...] = ()

    @property
    def red(self) -> bool:
        return bool(self.alerts)


def _logo_path(value, config_path: str) -> str | None:
    """``logo`` の値を絶対パスにする。``~`` と、設定ファイルからの相対パスを使える。"""
    if value is None:
        return None
    logo = Path(str(value)).expanduser()
    if not logo.is_absolute():
        logo = Path(config_path).resolve().parent / logo
    if not logo.is_file():
        raise ConfigError(f"logo の画像がありません: {logo}")
    return str(logo)


def _second(at: datetime) -> datetime:
    """時刻を UTC の秒までにする（状態ファイルの ``since`` は秒の小数を持つが、設定には秒まで書く）。"""
    return at.astimezone(timezone.utc).replace(microsecond=0)


def _incident_id(key: str) -> tuple[str, str]:
    """状態ファイルの項目の名前を (種類, 名前) にする（``parse_state`` と同じ分け方）。"""
    kind, _, name = key.partition(":")
    return kind, name or kind


def _acknowledged(table) -> tuple[tuple[tuple[str, str], datetime], ...]:
    """``[state.acknowledged]`` を読む。時刻に時差が無ければ日本時間とみなす。"""
    entries = []
    for key, value in table.items():
        if not isinstance(value, datetime):
            raise ConfigError(f"acknowledged の {key}: 障害が始まった時刻を 2026-10-16T08:02:56+09:00 の形で書く"
                              "（monitor --incidents が書き写す行を出す）")
        entries.append((_incident_id(str(key)), _second(value if value.tzinfo else value.replace(tzinfo=JST))))
    return tuple(sorted(entries))


def acknowledge_line(config: MonitorConfig, incident: Incident) -> str | None:
    """``[state.acknowledged]`` に書き写す 1 行（``since`` の無い障害は確認済みにできないので None）。"""
    if incident.since is None:
        return None
    since = _second(incident.since).astimezone(JST).isoformat()
    return f'"{incident.key}" = {since}  # {config.display_name(incident)} {incident.reason}'.rstrip()


def ended_acknowledgements(config: MonitorConfig, incidents) -> tuple[Incident, ...]:
    """確認済みの行のうち、もう続いていない障害（復旧したか、起き直して始まった時刻が変わった）。"""
    current = {((i.kind, i.name), _second(i.since)) for i in incidents if i.since is not None}
    return tuple(Incident(kind, name, "", since) for (kind, name), since in config.acknowledged
                 if ((kind, name), since) not in current)


def load_config(path: str) -> MonitorConfig:
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except FileNotFoundError as e:
        raise ConfigError(f"設定ファイルがありません: {path}（monitor.example.toml を写して作る）") from e
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"設定ファイルを読めません: {e}") from e
    try:
        metrics = tuple(
            MetricSpec(m["label"], m["namespace"], m["name"],
                       tuple(sorted((str(k), str(v)) for k, v in m.get("dimensions", {}).items())),
                       float(m["threshold"]), int(m.get("period", 60)), int(m.get("datapoints", 1)))
            for m in raw["metrics"])
        state = raw.get("state", {})
        config = MonitorConfig(
            title=raw["title"], region=raw["region"], keychain_service=raw["keychain_service"], metrics=metrics,
            state_bucket=state.get("bucket"), state_key=state.get("key"),
            state_stale=timedelta(seconds=int(state.get("stale_seconds", 300))),
            red_kinds=tuple(state.get("red_kinds", ("http", "tls"))),
            names=tuple(sorted((str(k), str(v)) for k, v in state.get("names", {}).items())),
            logo=_logo_path(raw.get("logo"), path), show_title=bool(raw.get("show_title", True)), acknowledged=_acknowledged(state.get("acknowledged", {})))
    except (KeyError, TypeError, ValueError) as e:
        raise ConfigError(f"設定ファイルの項目が足りないか、形が違います: {e!r}") from e
    if len(config.metrics) != 4:
        raise ConfigError(f"metrics は 4 つ書く（画面が 2×2 のため）: {len(config.metrics)} 個")
    for spec in config.metrics:
        if spec.period < 60 or spec.period % 60 or spec.datapoints < 1:
            raise ConfigError(f"{spec.label}: period は 60 の倍数、datapoints は 1 以上にする")
    return config


def latest(datapoints: list[dict]) -> tuple[float | None, datetime | None]:
    """GetMetricStatistics の Datapoints から、いちばん新しい平均を取り出す。"""
    if not datapoints:
        return None, None
    point = max(datapoints, key=lambda p: p["Timestamp"])
    return float(point["Average"]), point["Timestamp"]


def over_streak(datapoints: list[dict], threshold: float, period: int) -> int:
    """いちばん新しい平均から数えて、しきい値以上が途切れずに続いている回数。

    間が空いた（``period`` より離れた）点は、続いていないとみなす（アラームも欠けた点を超えたとは数えない）。
    """
    streak, previous = 0, None
    for point in sorted(datapoints, key=lambda p: p["Timestamp"], reverse=True):
        if point["Average"] < threshold:
            break
        if previous is not None and (previous - point["Timestamp"]).total_seconds() > period:
            break
        streak, previous = streak + 1, point["Timestamp"]
    return streak


def parse_state(document: dict, updated_at: datetime) -> MonitorState:
    """監視の状態ファイルから、障害中の監視を取り出す（``_`` で始まる項目は監視ではない）。"""
    incidents = []
    for key, entry in document.items():
        if key.startswith("_") or not isinstance(entry, dict) or not entry.get("alerting"):
            continue
        kind, _, name = key.partition(":")
        since = entry.get("since")
        incidents.append(Incident(kind, name or kind, str(entry.get("reason", "")),
                                  datetime.fromtimestamp(since, timezone.utc) if isinstance(since, (int, float)) else None,
                                  str(entry.get("name", ""))))
    incidents.sort(key=lambda i: (i.since or updated_at, i.kind, i.name))
    return MonitorState(tuple(incidents), updated_at)


# 見出しの注意に出す名前の上限（文字数）。長いと 480×320 の 1 行に理由が収まらない
NAME_LIMIT = 20


def short_reason(reason: str) -> str:
    """見出しの 1 行に入る長さにした理由（最初の文だけ・括弧の中を除く）。"""
    first = reason.split("。", 1)[0]
    return re.sub(r"（[^）]*）", "", first).strip()


def assess(status: ServerStatus, config: MonitorConfig, now: datetime) -> Assessment:
    """アラートは気付くべき順（監視の停止 → サイト → 値が届かない → しきい値）に並べる。画面には先頭を出す。

    確認済みの障害は、赤にも件数にも入れない。
    """
    stopped, site, missing, over, warnings, alerting_metrics, acknowledged = [], [], [], [], [], set(), []
    for metric in status.metrics:
        spec = metric.spec
        if metric.value is None or metric.at is None or now - metric.at > spec.stale_after:
            missing.append(f"{spec.label}の値が届いていません")
            alerting_metrics.add(spec.label)
        elif metric.sustained:
            if spec.datapoints > 1:
                minutes = spec.period * spec.datapoints // 60
                over.append(f"{spec.label} {metric.value:.0f}%（{spec.threshold:g}% 以上が {minutes} 分）")
            else:
                over.append(f"{spec.label} {metric.value:.0f}%（しきい値 {spec.threshold:g}%）")
            alerting_metrics.add(spec.label)
    if status.monitor is not None:
        if now - status.monitor.updated_at > config.state_stale:
            stopped.append(f"監視が止まっています（{status.monitor.updated_at.astimezone(JST):%H:%M} から）")
        others = []
        for incident in status.monitor.incidents:
            if config.acknowledges(incident):
                acknowledged.append(f"{incident.key}（{incident.since.astimezone(JST):%m-%d %H:%M} から）")
            elif incident.kind in config.red_kinds:
                site.append(f"{config.display_name(incident)} {incident.reason}".strip())
            else:
                others.append(incident)
        if others:
            # 件数だけでは本物の障害かが分からず、毎回調べないと読めなかった（2026-10-22）。
            # 1 件なら名前と理由、複数なら件数と先頭の名前を出す
            first = config.display_name(others[0])
            if len(first) > NAME_LIMIT:
                first = first[:NAME_LIMIT - 1] + "…"
            if len(others) == 1:
                warnings.append(f"{first}: {short_reason(others[0].reason)}".rstrip(": "))
            else:
                jobs = sum(1 for i in others if i.kind == "job")
                rest = len(others) - jobs
                counts = "・".join(text for text in (f"ジョブ障害 {jobs} 件" if jobs else "",
                                                     f"監視の障害 {rest} 件" if rest else "") if text)
                warnings.append(f"{counts}（{first} ほか）")
    return Assessment(tuple(stopped + site + missing + over), tuple(warnings), frozenset(alerting_metrics),
                      tuple(acknowledged))


def warning_tint(value: float, threshold: float) -> str:
    """リングの色の段階。"""
    if value >= threshold:
        return "critical"
    if value >= threshold - WARNING_MARGIN:
        return "warning"
    return "normal"


def read_credentials(service: str) -> tuple[str, str]:
    """Keychain から読み取り専用の鍵を読む（アカウント名 = アクセスキー ID、パスワード = シークレット）。"""
    try:
        attrs = subprocess.run(["security", "find-generic-password", "-s", service],
                               capture_output=True, text=True, timeout=10, check=True).stdout
        secret = subprocess.run(["security", "find-generic-password", "-s", service, "-w"],
                                capture_output=True, text=True, timeout=10, check=True).stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        raise FetchError("Keychain に鍵がありません") from e
    key_id = next((line.split('"')[3] for line in attrs.splitlines() if '"acct"' in line and line.count('"') >= 4), "")
    if not key_id or not secret:
        raise FetchError("Keychain に鍵がありません")
    return key_id, secret


class AwsReader:
    """CloudWatch と S3 から読む。クライアントは最初に使うときに作り、鍵が変わったら作り直す。"""

    def __init__(self, config: MonitorConfig):
        self.config = config
        self._clients = None
        self._key_id = None

    def _connect(self):
        key_id, secret = read_credentials(self.config.keychain_service)
        if self._clients is None or key_id != self._key_id:
            import boto3
            from botocore.config import Config

            session = boto3.session.Session(aws_access_key_id=key_id, aws_secret_access_key=secret,
                                            region_name=self.config.region)
            options = Config(connect_timeout=10, read_timeout=15, retries={"max_attempts": 2})
            self._clients = (session.client("cloudwatch", config=options), session.client("s3", config=options))
            self._key_id = key_id
        return self._clients

    def fetch(self, now: datetime | None = None) -> ServerStatus:
        from botocore.exceptions import BotoCoreError, ClientError

        now = now or datetime.now(timezone.utc)
        cloudwatch, s3 = self._connect()
        try:
            metrics = []
            for spec in self.config.metrics:
                response = cloudwatch.get_metric_statistics(
                    Namespace=spec.namespace, MetricName=spec.name,
                    Dimensions=[{"Name": k, "Value": v} for k, v in spec.dimensions],
                    StartTime=now - spec.window, EndTime=now, Period=spec.period, Statistics=["Average"])
                points = response.get("Datapoints", [])
                value, at = latest(points)
                metrics.append(MetricValue(spec, value, at, over_streak(points, spec.threshold, spec.period)))
            monitor = None
            if self.config.state_bucket and self.config.state_key:
                obj = s3.get_object(Bucket=self.config.state_bucket, Key=self.config.state_key)
                monitor = parse_state(json.loads(obj["Body"].read()), obj["LastModified"])
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("AccessDenied", "AccessDeniedException", "InvalidClientTokenId",
                        "SignatureDoesNotMatch", "UnrecognizedClientException"):
                raise FetchError("AWS の鍵か権限が合いません") from e
            raise FetchError(f"取得に失敗しました（{code or 'AWS'}）") from e
        except (BotoCoreError, OSError) as e:
            raise FetchError("通信できません") from e
        except ValueError as e:
            raise FetchError("監視の状態を読めません") from e
        return ServerStatus(tuple(metrics), monitor, now)
