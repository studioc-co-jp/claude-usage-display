"""サーバーの状態（CloudWatch のメトリクスと、外形・死活監視の判定）の取得と判定。

``monitor`` コマンドが使う。何を読むか（リージョン・メトリクス・しきい値・監視の状態ファイル）は、
git に入れない設定ファイル（``monitor.toml``。見本は ``monitor.example.toml``）に書く。

- メトリクスは ``cloudwatch:GetMetricStatistics`` で 1 分ごとの平均を読み、いちばん新しい値を使う
  （GetMetricData は無料の範囲の対象外のため使わない。CloudWatch の料金ページ「Free Tier」）
- 監視の状態ファイルは、S3 の JSON（``{"<種類>:<名前>": {"alerting": bool, "reason": str, "since": 秒}}``）
- 鍵は Keychain に置いた読み取り専用の IAM ユーザーのもの（アカウント名 = アクセスキー ID、
  パスワード = シークレット）。値をログや画面に出さない
"""

from __future__ import annotations

import json
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

METRIC_WINDOW = timedelta(minutes=10)   # この範囲の 1 分ごとの平均を読み、いちばん新しい値を使う
METRIC_STALE = timedelta(minutes=5)     # これより古い値しかなければ「届いていない」
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

    def display_name(self, incident: "Incident") -> str:
        name = dict(self.names).get(incident.name, incident.name)
        return f"証明書 {name}" if incident.kind == "tls" else name


@dataclass(frozen=True)
class MetricValue:
    spec: MetricSpec
    value: float | None
    at: datetime | None


@dataclass(frozen=True)
class Incident:
    kind: str
    name: str
    reason: str
    since: datetime | None


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
    """``alerts`` があれば画面全体を赤にする。``warnings`` は見出しにオレンジで出す。"""

    alerts: tuple[str, ...]
    warnings: tuple[str, ...]
    alerting_metrics: frozenset[str]

    @property
    def red(self) -> bool:
        return bool(self.alerts)


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
                       float(m["threshold"]))
            for m in raw["metrics"])
        state = raw.get("state", {})
        config = MonitorConfig(
            title=raw["title"], region=raw["region"], keychain_service=raw["keychain_service"], metrics=metrics,
            state_bucket=state.get("bucket"), state_key=state.get("key"),
            state_stale=timedelta(seconds=int(state.get("stale_seconds", 300))),
            red_kinds=tuple(state.get("red_kinds", ("http", "tls"))),
            names=tuple(sorted((str(k), str(v)) for k, v in state.get("names", {}).items())))
    except (KeyError, TypeError, ValueError) as e:
        raise ConfigError(f"設定ファイルの項目が足りないか、形が違います: {e!r}") from e
    if len(config.metrics) != 4:
        raise ConfigError(f"metrics は 4 つ書く（画面が 2×2 のため）: {len(config.metrics)} 個")
    return config


def latest(datapoints: list[dict]) -> tuple[float | None, datetime | None]:
    """GetMetricStatistics の Datapoints から、いちばん新しい平均を取り出す。"""
    if not datapoints:
        return None, None
    point = max(datapoints, key=lambda p: p["Timestamp"])
    return float(point["Average"]), point["Timestamp"]


def parse_state(document: dict, updated_at: datetime) -> MonitorState:
    """監視の状態ファイルから、障害中の監視を取り出す（``_`` で始まる項目は監視ではない）。"""
    incidents = []
    for key, entry in document.items():
        if key.startswith("_") or not isinstance(entry, dict) or not entry.get("alerting"):
            continue
        kind, _, name = key.partition(":")
        since = entry.get("since")
        incidents.append(Incident(kind, name or kind, str(entry.get("reason", "")),
                                  datetime.fromtimestamp(since, timezone.utc) if isinstance(since, (int, float)) else None))
    incidents.sort(key=lambda i: (i.since or updated_at, i.kind, i.name))
    return MonitorState(tuple(incidents), updated_at)


def assess(status: ServerStatus, config: MonitorConfig, now: datetime) -> Assessment:
    """アラートは気付くべき順（監視の停止 → サイト → 値が届かない → しきい値）に並べる。画面には先頭を出す。"""
    stopped, site, missing, over, warnings, alerting_metrics = [], [], [], [], [], set()
    for metric in status.metrics:
        spec = metric.spec
        if metric.value is None or metric.at is None or now - metric.at > METRIC_STALE:
            missing.append(f"{spec.label}の値が届いていません")
            alerting_metrics.add(spec.label)
        elif metric.value >= spec.threshold:
            over.append(f"{spec.label} {metric.value:.0f}%（しきい値 {spec.threshold:g}%）")
            alerting_metrics.add(spec.label)
    if status.monitor is not None:
        if now - status.monitor.updated_at > config.state_stale:
            stopped.append(f"監視が止まっています（{status.monitor.updated_at.astimezone(JST):%H:%M} から）")
        others = []
        for incident in status.monitor.incidents:
            if incident.kind in config.red_kinds:
                site.append(f"{config.display_name(incident)} {incident.reason}".strip())
            else:
                others.append(incident)
        if others:
            jobs = sum(1 for i in others if i.kind == "job")
            rest = len(others) - jobs
            warnings.append("・".join(text for text in (f"ジョブ障害 {jobs} 件" if jobs else "",
                                                        f"監視の障害 {rest} 件" if rest else "") if text))
    return Assessment(tuple(stopped + site + missing + over), tuple(warnings), frozenset(alerting_metrics))


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
                    StartTime=now - METRIC_WINDOW, EndTime=now, Period=60, Statistics=["Average"])
                value, at = latest(response.get("Datapoints", []))
                metrics.append(MetricValue(spec, value, at))
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
