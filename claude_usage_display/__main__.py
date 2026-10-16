"""コマンドライン。

    python -m claude_usage_display preview [-o out.png] [--demo]  画像だけ作る（ディスプレイ不要）
    python -m claude_usage_display probe                          ディスプレイの USB 情報を出す
    python -m claude_usage_display test-pattern                   向きと色の確認画面を出す
    python -m claude_usage_display run                            常駐して表示し続ける
    python -m claude_usage_display monitor                        サーバーの状態を表示し続ける（monitor.toml）
    python -m claude_usage_display local                          この Mac の状態を表示し続ける（local_monitor.py）

ディスプレイは、TURZX の 5.2 インチ（turzx_usb.py）を先に探し、無ければ 3.5 インチ（rev A、turing.py）を使う。
2 台を別々のプログラムに使うときは --device 3.5 / --device 5.2 で指定する。3.5 インチを 2 台使うときは、
USB の位置（--location。probe が出す）で分ける（ID もシリアル番号も同じため）。

run と preview に --gemini を付けると、Antigravity の Gemini の枠（antigravity.py）も下の段に出す。
--icons で、見出しに出すアイコン（claude.png・gemini.png）のフォルダを指定する（ロゴはリポジトリに入れない）。
"""

from __future__ import annotations

import argparse
import logging
import math
import signal
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

from PIL import Image

from . import gauge, local_monitor, monitor_screen, render
from .antigravity import LABELS as GEMINI_LABELS
from .antigravity import AntigravityError, AntigravityReader
from .presence import DEFAULT_AWAY_MINUTES, POLL_SECONDS, Presence
from .render import render_test_pattern
from .server_monitor import (Assessment, AwsReader, ConfigError, FetchError, Incident, MetricValue, MonitorConfig,
                             MonitorState, ServerStatus, acknowledge_line, assess, ended_acknowledgements,
                             load_config)
from .turing import PID, VID, DeviceNotFound, TuringRevA, UsbTransport, is_disconnected, location_id
from .turzx_usb import MODELS as TURZX_MODELS
from .turzx_usb import VID as TURZX_VID
from .turzx_usb import TurzxUsb, TurzxUsbTransport
from .usage import Meter, Snapshot, UsageError, fetch_snapshot, meter_labels

log = logging.getLogger("claude_usage_display")

DEVICE_RETRY_SECONDS = 10
DEVICE_IDS = "・".join([f"{TURZX_VID:04x}:{pid:04x}" for pid in TURZX_MODELS] + [f"{VID:04x}:{PID:04x}"])

DEFAULT_THEME = "gauge"
SIZES = {"480x320": (480, 320), "1280x720": (1280, 720)}  # 3.5 インチと 5.2 インチ


DEVICES = ("auto", "3.5", "5.2")


def _location(text: str) -> int:
    """--location の値（16 進数。「0x00111000」も「00111000」も受け付ける）。"""
    try:
        value = int(text, 16)
    except ValueError:
        raise argparse.ArgumentTypeError(f"位置は 16 進数で書いてください（例: 0x00111000）: {text}") from None
    if not 0 <= value <= 0xFFFFFFFF:
        raise argparse.ArgumentTypeError(f"位置は 8 桁の 16 進数です（例: 0x00111000）: {text}")
    return value


def device_ids(device: str) -> str:
    """接続を待つときにログへ出す USB の ID。"""
    return {"3.5": f"{VID:04x}:{PID:04x}", "5.2": f"{TURZX_VID:04x}:" + "/".join(f"{p:04x}" for p in TURZX_MODELS)}.get(
        device, DEVICE_IDS)


def open_display(flipped: bool, device: str = "auto", portrait: bool = False,
                 location: int | None = None) -> TuringRevA | TurzxUsb:
    """つながっているディスプレイを開く。

    auto は TURZX の 5.2 インチを先に探し、無ければ 3.5 インチ（rev A）。2 台を別々のプログラムに使うときは、
    3.5 か 5.2 を指定する（auto のままだと、5.2 インチを外したときに、もう一方のプログラムの 3.5 インチを取りに行く）。
    3.5 インチを 2 台使うときは、``location``（USB の位置）でどちらかを選ぶ（ID もシリアル番号も同じため）。
    """
    if location is not None:
        return TuringRevA(UsbTransport.open(location), flipped=flipped, portrait=portrait)
    if device != "3.5":
        try:
            transport, pid = TurzxUsbTransport.open()
        except DeviceNotFound:
            if device == "5.2":
                raise
        else:
            return TurzxUsb(transport, pid, flipped=flipped, portrait=portrait)
    return TuringRevA(UsbTransport.open(), flipped=flipped, portrait=portrait)


def fit_to(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """大きさの違う画面へ、縦横比を保って拡大・縮小し、黒地の中央に置く。

    横棒の画面（480×320 だけ）を 5.2 インチ（1280×720）に出すときに使う。
    """
    if image.size == size:
        return image
    scale = min(size[0] / image.width, size[1] / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size)
    canvas.paste(resized, ((size[0] - resized.width) // 2, (size[1] - resized.height) // 2))
    return canvas


def _classic(snapshot, now, status=None, labels=("5時間", "週次", "Fable週次"), size=SIZES["480x320"]):
    """横棒の画面は 480×320 だけなので、ほかの大きさの画面には拡大して中央に置く。"""
    return fit_to(render.render(snapshot, now, status, labels), size)


# 画面のデザイン。classic は最初に作った横棒の画面。どちらも size=(幅, 高さ) を受け取る
THEMES = {"gauge": gauge.render, "classic": _classic}


def _demo_snapshot(now: datetime, model: str) -> Snapshot:
    return Snapshot((
        Meter("5時間", 26, now + timedelta(hours=1, minutes=5)),
        Meter("週次", 74, now + timedelta(days=6, hours=17)),
        Meter(f"{model}週次", 93, now + timedelta(days=6, hours=17)),
    ), now)


def _demo_gemini(now: datetime) -> Snapshot:
    return Snapshot((
        Meter("Gemini 5時間", 12, now + timedelta(hours=2, minutes=5)),
        Meter("Gemini 週次", 38, now + timedelta(days=3, hours=3)),
    ), now - timedelta(minutes=4))


def cmd_preview(args) -> int:
    now = datetime.now(timezone.utc)
    size = SIZES[args.size]
    labels = meter_labels(args.model)
    snapshot = status = gemini = gemini_status = None
    if args.demo:
        snapshot = _demo_snapshot(now, args.model)
    else:
        try:
            snapshot = fetch_snapshot(args.model)
        except UsageError as e:
            status = e.message
            print(f"取得に失敗しました: {e.message}", file=sys.stderr)
    if args.gemini:
        if args.demo:
            gemini = _demo_gemini(now)
        else:
            try:
                gemini = AntigravityReader(args.agy).fetch(now)
            except AntigravityError as e:
                gemini_status = e.message
                print(f"Gemini の取得に失敗しました: {e.message}", file=sys.stderr)
    icons = gauge.load_icons(args.icons) if args.icons else {}
    if args.gemini:
        image = gauge.render_with_gemini(snapshot, gemini, now, status, gemini_status, labels, GEMINI_LABELS,
                                         size=size, icons=icons)
    else:
        image = THEMES[args.theme](snapshot, now, status, labels, size=size, **({"icons": icons} if icons else {}))
    image.save(args.output)
    print(args.output)
    return 0


def _describe(device) -> None:
    import usb.core
    import usb.util

    for field in ("manufacturer", "product", "serial_number"):
        try:
            print(f"  {field}: {usb.util.get_string(device, getattr(device, 'i' + field.title().replace('_', '')))}")
        except (ValueError, usb.core.USBError, NotImplementedError) as e:
            print(f"  {field}: 取得できません（{e}）")
    for config in device:
        print(f"  configuration {config.bConfigurationValue}")
        for interface in config:
            try:
                attached = device.is_kernel_driver_active(interface.bInterfaceNumber)
            except (NotImplementedError, usb.core.USBError) as e:
                attached = f"不明（{e}）"
            print(f"    interface {interface.bInterfaceNumber} class=0x{interface.bInterfaceClass:02x} "
                  f"kernel_driver={attached}")
            for endpoint in interface:
                kind = usb.util.endpoint_type(endpoint.bmAttributes)
                direction = "IN" if usb.util.endpoint_direction(endpoint.bEndpointAddress) else "OUT"
                print(f"      endpoint 0x{endpoint.bEndpointAddress:02x} {direction} type={kind} "
                      f"max_packet={endpoint.wMaxPacketSize}")


def cmd_probe(args) -> int:
    import usb.core

    from .turing import _libusb_backend

    known = {(VID, PID): "3.5 インチ（rev A）"}
    known.update({(TURZX_VID, pid): f"TURZX {name}" for pid, (name, _w, _h) in TURZX_MODELS.items()})
    # 同じ機種名でも中身の世代が違う個体があるため（docs/handover.md §4-9）、知らない ID も一覧に出す
    devices = list(usb.core.find(find_all=True, backend=_libusb_backend(),
                                 custom_match=lambda d: d.idVendor in (VID, TURZX_VID)))
    if not devices:
        print(f"{VID:04x}:xxxx・{TURZX_VID:04x}:xxxx の機器は接続されていません")
        return 1
    for device in devices:
        name = known.get((device.idVendor, device.idProduct), "対応していない ID")
        print(f"{device.idVendor:04x}:{device.idProduct:04x} {name} bus={device.bus} address={device.address} "
              f"位置 0x{location_id(device.bus, device.port_numbers):08x}")
        _describe(device)
    found = {(d.idVendor, d.idProduct) for d in devices} & known.keys()
    if not found:
        print("対応している ID の機器がありません")
        return 1
    failed = False
    # 2 台をつないでいると、片方はもう一方の常駐が使っていて確保できない。それでも残りの機器を確かめる。
    # 3.5 インチは同じ ID の 2 台がありうるので、位置ごとに確かめる（--location に書く値）
    targets = [(TURZX_VID, pid, None) for vid, pid in sorted(found) if vid == TURZX_VID]
    targets += [(VID, PID, location_id(d.bus, d.port_numbers)) for d in devices if (d.idVendor, d.idProduct) == (VID, PID)]
    for vid, pid, location in targets:
        label = known[(vid, pid)] + ("" if location is None else f"（位置 0x{location:08x}）")
        try:
            if vid == TURZX_VID:
                TurzxUsbTransport.open()[0].close()
            else:
                UsbTransport.open(location).close()
            print(f"{label}: インターフェースを確保できました")
        except Exception as e:  # noqa: BLE001 - 原因をそのまま見せる
            print(f"{label}: インターフェースを確保できません: {e!r}")
            failed = True
    return 1 if failed else 0


def cmd_test_pattern(args) -> int:
    display = open_display(args.flip, args.device, args.portrait, args.location)
    try:
        display.initialize(args.brightness)
        display.show(render_test_pattern((display.width, display.height)))
    finally:
        if isinstance(display, TurzxUsb):  # 応答の形を実機で確かめるため、届いた応答をそのまま見せる
            for command, response in display.history:
                print(f"命令 {command} の応答: {response[:16].hex(' ')}")
        display.close()
    print("確認画面を送りました。左上に赤と「左上」が見えれば向きは正しいです。")
    return 0


def _duration(elapsed: timedelta) -> str:
    seconds = max(0, round(elapsed.total_seconds()))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours} 時間 {minutes} 分"
    return f"{minutes} 分 {seconds} 秒" if minutes else f"{seconds} 秒"


class _Resident:
    """2 つの常駐の共通部分: ディスプレイへの操作の失敗の扱いと、席を離れている間の消灯（焼き付き対策）。"""

    def _setup_presence(self) -> None:
        self.presence = Presence(getattr(self.args, "away_minutes", 0))
        self.blanked = False

    def _operate(self, action) -> bool:
        """ディスプレイへの操作。失敗したら閉じて、接続を待つ状態に戻す。"""
        try:
            action()
            return True
        except Exception as e:  # noqa: BLE001
            if is_disconnected(e):  # 抜いただけなので、トレースバックは残さない
                log.warning("ディスプレイが外れました。接続を待ちます")
            else:
                log.exception("送信に失敗しました。接続し直します")
            Runner._close(self.display)
            self.display = None
            return False

    def _blank(self) -> bool:
        if self.blanked:
            return True
        if not self._operate(self.display.blank):
            return False
        log.info("席を離れたので消灯しました（無操作 %g 分）", self.presence.away_after / 60)
        self.blanked = True
        return True

    def _unblank(self, reason: str) -> bool:
        if not self.blanked:
            return True
        if not self._operate(lambda: self.display.unblank(self.args.brightness)):
            return False
        log.info("%sので点灯しました", reason)
        self.blanked = False
        self.last_frame = None  # 送り直す
        return True

    def _shutdown(self) -> None:
        """画面を消してから閉じる（2026-10-17 ユーザーが決定）。

        2026-10-16 に利用枠の常駐が止まったまま（登録が ``run --help`` に置き換わった）、5.2 インチは最後の画面を
        一晩出し続け、席を離れたときの消灯も効かなかった。強制終了（SIGKILL）や異常終了では消せない。
        """
        if self.display is None:
            return
        try:
            if not self.blanked:
                self.display.blank()
        except Exception as e:  # noqa: BLE001
            if not is_disconnected(e):  # 外れていれば、消す必要も無い
                log.exception("終わる前に画面を消せませんでした")
        Runner._close(self.display)
        self.display = None

    def _wait(self, seconds: float, wake=None) -> None:
        """``seconds`` 待つ。消灯を使うときは、その間も ``wake``（既定は席を離れたか）を確かめ、真になったら待つのをやめる。"""
        if not self.presence.enabled:
            self.stop.wait(seconds)
            return
        wake = wake or self.presence.away
        end = time.monotonic() + seconds
        while not self.stop.is_set():
            left = end - time.monotonic()
            if left <= 0:
                return
            self.stop.wait(min(left, POLL_SECONDS))
            if wake():
                return


class Runner(_Resident):
    def __init__(self, args):
        self.args = args
        self.stop = threading.Event()
        self.display: TuringRevA | TurzxUsb | None = None
        self.snapshot: Snapshot | None = None
        self.status: str | None = None
        self.next_fetch = 0.0
        self.failed_since: datetime | None = None  # 取得に失敗し始めた時刻（戻ったときに止まっていた長さを記録する）
        self.last_frame: bytes | None = None
        self.waiting_logged = False
        self.open_error: str | None = None
        self.icons = gauge.load_icons(args.icons) if getattr(args, "icons", None) else {}
        # Gemini（Antigravity）の枠。agy の実行に約 6 秒かかるので、Claude とは別の長い間隔で取る
        self.gemini_reader = AntigravityReader(getattr(args, "agy", None)) if getattr(args, "gemini", False) else None
        self.gemini: Snapshot | None = None
        self.gemini_status: str | None = None
        self.next_gemini = 0.0
        self._setup_presence()

    def request_stop(self, signum, _frame) -> None:
        # 送信中に止めるとパネルの同期が崩れるため、ここでは合図だけ立てる
        log.info("終了の合図を受けました（%s）", signal.Signals(signum).name)
        self.stop.set()

    def _connect(self) -> bool:
        try:
            display = open_display(self.args.flip, self.args.device, location=getattr(self.args, "location", None))
        except DeviceNotFound:
            if not self.waiting_logged:
                log.info("ディスプレイの接続を待っています（%s）", device_ids(self.args.device))
                self.waiting_logged = True
            return False
        except Exception as e:  # noqa: BLE001
            # 権限不足などは 10 秒ごとに繰り返すため、内容が変わったときだけ記録する
            if repr(e) != self.open_error:
                log.exception("ディスプレイを開けません")
                self.open_error = repr(e)
            return False
        try:
            display.initialize(self.args.brightness)
        except Exception:  # noqa: BLE001
            log.exception("ディスプレイの初期化に失敗しました")
            self._close(display)
            return False
        log.info("ディスプレイに接続しました")
        self.display = display
        self.last_frame = None
        self.waiting_logged = False
        self.open_error = None
        self.blanked = False  # 初期化で明るさが戻っている
        return True

    @staticmethod
    def _close(display: TuringRevA | TurzxUsb) -> None:
        try:
            display.close()
        except Exception:  # noqa: BLE001
            pass

    def _fetch_if_due(self) -> None:
        now = time.monotonic()
        if now < self.next_fetch:
            return
        try:
            self.snapshot = fetch_snapshot(self.args.model)
            if self.status and self.failed_since:
                log.info("取得が戻りました（%s から %s）", f"{self.failed_since:%H:%M:%S}",
                         _duration(datetime.now(render.JST) - self.failed_since))
            self.status = None
            self.failed_since = None
            self.next_fetch = now + self.args.interval
        except UsageError as e:
            wait = max(self.args.interval, e.retry_after or 0)
            if self.failed_since is None:
                self.failed_since = datetime.now(render.JST)
            if e.rate_limited:  # 原因を絞り込めるよう、429 は続いても毎回、待ち時間とともに記録する
                retry_at = datetime.now(render.JST) + timedelta(seconds=wait)
                log.warning("取得の間隔を空けるよう求められました（%s。次の取得は %s）", e.detail, f"{retry_at:%H:%M:%S}")
            elif e.message != self.status:
                log.warning("取得に失敗しました: %s", e.message)
            self.status = e.message
            self.next_fetch = now + wait

    def _fetch_gemini_if_due(self) -> None:
        if self.gemini_reader is None or time.monotonic() < self.next_gemini:
            return
        try:
            self.gemini = self.gemini_reader.fetch()
            if self.gemini_status:
                log.info("Gemini の取得が戻りました")
            self.gemini_status = None
        except AntigravityError as e:
            if e.message != self.gemini_status:
                log.warning("Gemini の取得に失敗しました: %s", e.message)
            self.gemini_status = e.message
            if e.permanent:
                log.warning("Gemini の取得をやめます（起動し直すまで）")
                self.next_gemini = math.inf
                return
        self.next_gemini = time.monotonic() + self.args.gemini_interval

    def _draw(self, size: tuple[int, int]) -> Image.Image:
        now = datetime.now(timezone.utc)
        labels = meter_labels(self.args.model)
        if self.gemini_reader is not None:
            return gauge.render_with_gemini(self.snapshot, self.gemini, now, self.status, self.gemini_status, labels,
                                            GEMINI_LABELS, size=size, icons=self.icons)
        extra = {"icons": self.icons} if self.icons else {}
        return THEMES[self.args.theme](self.snapshot, now, self.status, labels, size=size, **extra)

    def _seconds_to_wait(self) -> float:
        now = datetime.now()
        to_next_minute = 60 - now.second - now.microsecond / 1_000_000 + 0.5
        to_next_fetch = min(self.next_fetch, self.next_gemini if self.gemini_reader else math.inf) - time.monotonic()
        return max(1.0, min(to_next_minute, to_next_fetch))

    def loop(self) -> int:
        while not self.stop.is_set():
            if self.display is None and not self._connect():
                self.stop.wait(DEVICE_RETRY_SECONDS)
                continue
            if self.presence.away():
                # 席を離れている間は、取得も描き直しもしない。戻ったら、止まっていた取得から始める
                if self._blank():
                    self.stop.wait(POLL_SECONDS)
                continue
            if not self._unblank("操作が戻った"):
                continue
            self._fetch_if_due()
            self._fetch_gemini_if_due()
            image = self._draw((self.display.width, self.display.height))
            frame = image.tobytes()
            if frame != self.last_frame:
                if not self._operate(lambda: self.display.show(image)):
                    continue
                self.last_frame = frame
                if self.args.save_png:
                    image.save(self.args.save_png)
            self._wait(self._seconds_to_wait())
        self._shutdown()
        log.info("終了しました")
        return 0


def _demo_server_status(config, now: datetime, case: str) -> ServerStatus:
    """monitor --demo の見本の値。normal は正常、alert は CPU とサイトの異常、jobs はジョブの障害。"""
    values = {"normal": (23, 61, 47, 3), "alert": (92, 61, 47, 3), "jobs": (23, 61, 47, 3)}[case]
    incidents = {
        "normal": (),
        "alert": (Incident("http", "top", "HTTP 503（期待 200）", now - timedelta(minutes=3)),),
        "jobs": (Incident("job", "nightly-backup", "直近の実行が失敗", now - timedelta(hours=2)),
                 Incident("job", "daily-report", "直近の実行が失敗", now - timedelta(days=5))),
    }[case]
    # しきい値以上の値は、アラームと同じ回数（datapoints）続いているものとして描く
    metrics = tuple(MetricValue(spec, value, now - timedelta(minutes=1), spec.datapoints if value >= spec.threshold else 0)
                    for spec, value in zip(config.metrics, values))
    return ServerStatus(metrics, MonitorState(incidents, now - timedelta(seconds=30)), now)


class MonitorRunner(_Resident):
    """サーバーの状態を ``interval`` 秒ごとに取得し、変わったときだけ送る。

    席を離れている間は消灯するが、取得は続け、画面全体が赤になる異常のときは点灯して赤を出す
    （戻ったときに異常に気付けるように。2026-10-15 ユーザーが決定）。
    """

    def __init__(self, args, config, reader=None):
        self.args = args
        self.config = config
        self.reader = reader or AwsReader(config)
        self.stop = threading.Event()
        self.display: TuringRevA | TurzxUsb | None = None
        self.status: ServerStatus | None = None
        self.error: str | None = None
        self.alerts: tuple[str, ...] = ()
        self.warnings: tuple[str, ...] = ()
        self.acknowledged: tuple[str, ...] = ()
        self.last_frame: bytes | None = None
        self.waiting_logged = False
        self.assessment = None
        self.next_fetch = 0.0
        self._setup_presence()

    def request_stop(self, signum, _frame) -> None:
        log.info("終了の合図を受けました（%s）", signal.Signals(signum).name)
        self.stop.set()

    def _connect(self) -> bool:
        try:
            display = open_display(self.args.flip, self.args.device, self.args.portrait,
                                   getattr(self.args, "location", None))
            display.initialize(self.args.brightness)
        except DeviceNotFound:
            if not self.waiting_logged:
                log.info("ディスプレイの接続を待っています（%s）", device_ids(self.args.device))
                self.waiting_logged = True
            return False
        except Exception:  # noqa: BLE001
            log.exception("ディスプレイを開けません")
            return False
        log.info("ディスプレイに接続しました")
        self.display, self.last_frame, self.waiting_logged = display, None, False
        self.blanked = False  # 初期化で明るさが戻っている
        return True

    def fetch(self) -> None:
        try:
            self.status = self.reader.fetch()
            if self.error:
                log.info("取得が戻りました")
            self.error = None
        except FetchError as e:
            if e.message != self.error:
                log.warning("取得に失敗しました: %s", e.message)
            self.error = e.message
        assessment = assess(self.status, self.config, datetime.now(timezone.utc)) if self.status else None
        alerts = assessment.alerts if assessment else ()
        warnings = assessment.warnings if assessment else ()
        if alerts != self.alerts:
            if alerts:
                log.warning("アラート: %s", " / ".join(alerts))
            else:
                log.info("アラートが解消しました")
            self.alerts = alerts
        if warnings != self.warnings:
            log.info("見出しの注意: %s", " / ".join(warnings) or "なし")
            self.warnings = warnings
        acknowledged = assessment.acknowledged if assessment else ()
        if acknowledged != self.acknowledged:
            log.info("確認済みのため出さない障害: %s", " / ".join(acknowledged) or "なし")
            self.acknowledged = acknowledged
        return assessment

    def loop(self) -> int:
        while not self.stop.is_set():
            if self.display is None and not self._connect():
                self.stop.wait(DEVICE_RETRY_SECONDS)
                continue
            if time.monotonic() >= self.next_fetch:
                self.assessment = self.fetch()
                self.next_fetch = time.monotonic() + self.args.interval
            red = self.assessment is not None and self.assessment.red
            away = self.presence.away()
            if away and not red:
                if self._blank():
                    self.stop.wait(min(POLL_SECONDS, max(0.0, self.next_fetch - time.monotonic())))
                continue
            if not self._unblank("異常が起きた（席を離れています）" if away else "操作が戻った"):
                continue
            image = self._render()
            frame = image.tobytes()
            if frame != self.last_frame:
                if not self._operate(lambda: self.display.show(image)):
                    continue
                self.last_frame = frame
            # 赤を出している間は、席を離れていても待つ（次の取得で異常が解けていれば消灯する）
            self._wait(max(0.0, self.next_fetch - time.monotonic()), wake=lambda: not red and self.presence.away())
        self._shutdown()
        log.info("終了しました")
        return 0

    def _render(self) -> Image.Image:
        return monitor_screen.render(self.status, self.assessment, self.config, self.error,
                                     portrait=self.args.portrait)


class LocalRunner(MonitorRunner):
    """この Mac の状態（local_monitor）を ``interval`` 秒ごとに読み、変わったときだけ送る。

    画面はサーバーの状態の画面の横置きと同じ。画面全体を赤にする異常は無く、異常は見出しにオレンジで出す。
    メモリの逼迫の段階とスワップの量は、変わったときにログへ残す（再起動するとスワップの記録が消え、
    いつ・どれだけ使ったかを後から追えなかったため。2026-10-15）。
    """

    def __init__(self, args, reader=None):
        config = MonitorConfig(title=args.title, region="-", keychain_service="-", metrics=local_monitor.SPECS)
        super().__init__(args, config, reader or local_monitor.LocalReader(args.ssd))
        self.note: str | None = None
        self.pressure: int | None = None
        self.swap_step: float | None = None
        self.read_error = False

    def fetch(self):
        try:
            reading = self.reader.fetch()
        except Exception:  # noqa: BLE001 - 読めない値があっても常駐は止めない（前回の値を残す）
            if not self.read_error:
                log.exception("この Mac の値を読めません")
                self.read_error = True
            return self.assessment
        if self.read_error:
            log.info("この Mac の値を読めるようになりました")
            self.read_error = False
        self.status, self.note = reading.status, reading.note
        swap_step = round(reading.swap / local_monitor.GIB * 2) / 2  # 0.5 GB 刻みで変わったときだけ残す
        if reading.pressure != self.pressure or swap_step != self.swap_step:
            log.info("メモリの逼迫の段階 %d、スワップ %.1f GB", reading.pressure, reading.swap / local_monitor.GIB)
            self.pressure, self.swap_step = reading.pressure, swap_step
        if reading.warnings != self.warnings:
            log.info("見出しの注意: %s", " / ".join(reading.warnings) or "なし")
            self.warnings = reading.warnings
        return Assessment((), reading.warnings, frozenset())

    def _render(self) -> Image.Image:
        return monitor_screen.render(self.status, self.assessment, self.config, note=self.note)


def cmd_local(args) -> int:
    args.device, args.portrait = "3.5", False  # 3.5 インチの横置きだけ（CPU の 2 行目が縦置きの区画に収まらないため）
    args.title = args.title or local_monitor.machine_name()
    if args.preview:
        now = datetime.now(timezone.utc)
        if args.demo:
            reading = local_monitor.build(local_monitor.demo_sample(args.demo, now), now)
        else:
            reading = local_monitor.LocalReader(args.ssd).fetch(now)
        config = MonitorConfig(title=args.title, region="-", keychain_service="-", metrics=local_monitor.SPECS)
        monitor_screen.render(reading.status, Assessment((), reading.warnings, frozenset()), config,
                              note=reading.note).save(args.preview)
        print(args.preview)
        return 0
    runner = LocalRunner(args)
    signal.signal(signal.SIGTERM, runner.request_stop)
    signal.signal(signal.SIGINT, runner.request_stop)
    return runner.loop()


def _print_incidents(config: MonitorConfig) -> int:
    """いま障害中の監視を、``[state.acknowledged]`` に書き写す形で出す。確認済みの行のうち、もう続いていないものも出す。"""
    try:
        status = AwsReader(config).fetch()
    except FetchError as e:
        print(f"取得に失敗しました: {e.message}", file=sys.stderr)
        return 1
    if status.monitor is None:
        print("設定に監視の状態ファイル（[state]）がありません", file=sys.stderr)
        return 2
    incidents = status.monitor.incidents
    print("# いま障害中の監視。確認済みにするものを monitor.toml の [state.acknowledged] に写し、常駐を再起動する")
    for incident in incidents:
        line = acknowledge_line(config, incident)
        mark = "（確認済み）" if config.acknowledges(incident) else ""
        print(f"{line}{mark}" if line else f"# {incident.key}: 始まった時刻が無いため確認済みにできません")
    if not incidents:
        print("# なし")
    for ended in ended_acknowledgements(config, incidents):
        print(f"# 確認済みの {ended.key}（{ended.since.astimezone(render.JST):%m-%d %H:%M} から）は続いていません。"
              "行を消してかまいません")
    return 0


def cmd_monitor(args) -> int:
    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 2
    if args.incidents:
        return _print_incidents(config)
    if args.preview:
        now = datetime.now(timezone.utc)
        error = None
        if args.demo:
            status = _demo_server_status(config, now, args.demo)
        else:
            try:
                status = AwsReader(config).fetch(now)
            except FetchError as e:
                status, error = None, e.message
                print(f"取得に失敗しました: {e.message}", file=sys.stderr)
        assessment = assess(status, config, now) if status else None
        monitor_screen.render(status, assessment, config, error, portrait=args.portrait).save(args.preview)
        print(args.preview)
        return 0
    runner = MonitorRunner(args, config)
    signal.signal(signal.SIGTERM, runner.request_stop)
    signal.signal(signal.SIGINT, runner.request_stop)
    return runner.loop()


def cmd_run(args) -> int:
    runner = Runner(args)
    signal.signal(signal.SIGTERM, runner.request_stop)
    signal.signal(signal.SIGINT, runner.request_stop)
    return runner.loop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claude_usage_display", description="Claude Code の利用枠を表示する")
    parser.add_argument("--model", default="Fable", help="モデル別週次で表示するモデル名（既定: Fable）")
    sub = parser.add_subparsers(dest="command", required=True)

    preview = sub.add_parser("preview", help="画像だけ作る（ディスプレイ不要）")
    preview.add_argument("-o", "--output", default="preview.png")
    preview.add_argument("--demo", action="store_true", help="API を呼ばず見本の値で描く")
    preview.add_argument("--size", choices=SIZES, default="480x320",
                         help="画面の大きさ（既定: 480x320。1280x720 は 5.2 インチ）")
    preview.set_defaults(func=cmd_preview)

    theme_help = f"画面のデザイン（既定: {DEFAULT_THEME}。classic は横棒の画面）"
    preview.add_argument("--theme", choices=THEMES, default=DEFAULT_THEME, help=theme_help)

    def add_gemini_options(p) -> None:
        p.add_argument("--gemini", action="store_true",
                       help="Antigravity の Gemini の枠も出す（下の段。ゲージ型の画面だけ）")
        p.add_argument("--agy", help="agy（Antigravity の CLI）のパス（既定: PATH と /opt/homebrew/bin などから探す）")
        p.add_argument("--icons", help="見出しに出すアイコン（claude.png・gemini.png）のフォルダ")

    add_gemini_options(preview)

    probe = sub.add_parser("probe", help="ディスプレイの USB 情報を出す")
    probe.set_defaults(func=cmd_probe)

    for name, func, help_text in (("test-pattern", cmd_test_pattern, "向きと色の確認画面を出す"),
                                  ("run", cmd_run, "常駐して表示し続ける"),
                                  ("monitor", cmd_monitor, "サーバーの状態を表示し続ける（monitor.toml）"),
                                  ("local", cmd_local, "この Mac の状態（CPU・メモリ・ディスク・SSD）を表示し続ける"
                                                       "（3.5 インチ・横置き）")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--brightness", type=int, default=30, help="明るさ 0〜100（既定: 30）")
        p.add_argument("--flip", action="store_true", help="上下を反転する（ケーブルの向きに合わせる）")
        if name != "local":
            p.add_argument("--device", choices=DEVICES, default="auto",
                           help="使うディスプレイ（既定: auto は 5.2 インチを先に探す。2 台を使い分けるときは指定する）")
        p.add_argument("--location", type=_location,
                       help="3.5 インチを USB の位置で選ぶ（probe が出す「位置 0x…」。同じ 3.5 インチを 2 台つなぐときに使う）")
        p.set_defaults(func=func)
        if name == "run":
            p.add_argument("--interval", type=int, default=120, help="取得の間隔（秒、既定: 120）")
            p.add_argument("--save-png", help="送った画像をこのパスにも保存する（確認用）")
            p.add_argument("--theme", choices=THEMES, default=DEFAULT_THEME, help=theme_help)
            add_gemini_options(p)
            p.add_argument("--gemini-interval", type=int, default=900,
                           help="Gemini の取得の間隔（秒、既定: 900。agy の実行に約 6 秒かかるため長めにする）")
        if name == "local":
            p.add_argument("--interval", type=int, default=60, help="取得の間隔（秒、既定: 60。CPU はこの間の平均）")
            p.add_argument("--title", help="見出しの名前（既定: 機種名。例: Mac mini）")
            p.add_argument("--ssd", default="/Volumes/SSD",
                           help="4 つ目のリングに出す外付けのディスクの場所（既定: /Volumes/SSD）")
            p.add_argument("--preview", help="ディスプレイに送らず、画像をこのパスに保存して終わる")
            p.add_argument("--demo", choices=("normal", "warning"),
                           help="--preview で、この Mac を読まず見本の値で描く（warning はメモリの逼迫）")
        if name in ("run", "monitor", "local"):
            p.add_argument("--away-minutes", type=int, default=DEFAULT_AWAY_MINUTES,
                           help=f"キーボード・マウスをこの分数触らなければ消灯する（焼き付き対策。既定: {DEFAULT_AWAY_MINUTES}。0 で消灯しない）")
        if name in ("test-pattern", "monitor"):
            p.add_argument("--portrait", action="store_true", help="縦置き（320×480）で出す")
        if name == "monitor":
            p.add_argument("--config", default="monitor.toml", help="設定ファイル（既定: monitor.toml）")
            p.add_argument("--interval", type=int, default=60, help="取得の間隔（秒、既定: 60）")
            p.add_argument("--preview", help="ディスプレイに送らず、画像をこのパスに保存して終わる")
            p.add_argument("--demo", choices=("normal", "alert", "jobs"),
                           help="--preview で、AWS を呼ばず見本の値で描く")
            p.add_argument("--incidents", action="store_true",
                           help="いま障害中の監視を、確認済みにするとき monitor.toml に書き写す形で出して終わる")

    args = parser.parse_args(argv)
    if getattr(args, "interval", 60) < 60:
        parser.error("--interval は 60 秒以上にしてください")
    if getattr(args, "gemini_interval", 300) < 300:
        parser.error("--gemini-interval は 300 秒以上にしてください")
    if getattr(args, "gemini", False) and args.theme != "gauge":
        parser.error("--gemini はゲージ型の画面（--theme gauge）で使ってください")
    if getattr(args, "demo", None) and args.command in ("monitor", "local") and not args.preview:
        parser.error(f"{args.command} の --demo は --preview と一緒に使ってください")
    if getattr(args, "location", None) is not None and getattr(args, "device", "3.5") == "5.2":
        parser.error("--location は 3.5 インチを選ぶためのものです（--device 5.2 とは一緒に使えません）")
    if not 0 <= getattr(args, "away_minutes", 0) <= 1440:
        parser.error("--away-minutes は 0〜1440 にしてください")
    # 範囲外の値は接続した時点で初めて失敗し、run が初期化を繰り返し続けるため、ここで止める
    if not 0 <= getattr(args, "brightness", 0) <= 100:
        parser.error("--brightness は 0〜100 にしてください")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
