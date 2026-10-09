"""コマンドライン。

    python -m claude_usage_display preview [-o out.png] [--demo]  画像だけ作る（ディスプレイ不要）
    python -m claude_usage_display probe                          ディスプレイの USB 情報を出す
    python -m claude_usage_display test-pattern                   向きと色の確認画面を出す
    python -m claude_usage_display run                            常駐して表示し続ける

ディスプレイは、TURZX の 5.2 インチ（turzx_usb.py）を先に探し、無ければ 3.5 インチ（rev A、turing.py）を使う。
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

from PIL import Image

from . import gauge, render
from .render import render_test_pattern
from .turing import PID, VID, DeviceNotFound, TuringRevA, UsbTransport, is_disconnected
from .turzx_usb import MODELS as TURZX_MODELS
from .turzx_usb import VID as TURZX_VID
from .turzx_usb import TurzxUsb, TurzxUsbTransport
from .usage import Meter, Snapshot, UsageError, fetch_snapshot, meter_labels

log = logging.getLogger("claude_usage_display")

DEVICE_RETRY_SECONDS = 10
DEVICE_IDS = "・".join([f"{TURZX_VID:04x}:{pid:04x}" for pid in TURZX_MODELS] + [f"{VID:04x}:{PID:04x}"])

DEFAULT_THEME = "gauge"
SIZES = {"480x320": (480, 320), "1280x720": (1280, 720)}  # 3.5 インチと 5.2 インチ


def open_display(flipped: bool) -> TuringRevA | TurzxUsb:
    """つながっているディスプレイを開く。TURZX の 5.2 インチを先に探し、無ければ 3.5 インチ（rev A）。"""
    try:
        transport, pid = TurzxUsbTransport.open()
    except DeviceNotFound:
        return TuringRevA(UsbTransport.open(), flipped=flipped)
    return TurzxUsb(transport, pid, flipped=flipped)


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


def cmd_preview(args) -> int:
    now = datetime.now(timezone.utc)
    draw = THEMES[args.theme]
    size = SIZES[args.size]
    if args.demo:
        image = draw(_demo_snapshot(now, args.model), now, size=size)
    else:
        try:
            image = draw(fetch_snapshot(args.model), now, size=size)
        except UsageError as e:
            image = draw(None, now, e.message, meter_labels(args.model), size=size)
            print(f"取得に失敗しました: {e.message}", file=sys.stderr)
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
        print(f"{device.idVendor:04x}:{device.idProduct:04x} {name} bus={device.bus} address={device.address}")
        _describe(device)
    found = {(d.idVendor, d.idProduct) for d in devices} & known.keys()
    if not found:
        print("対応している ID の機器がありません")
        return 1
    for vid, pid in sorted(found):
        try:
            if vid == TURZX_VID:
                TurzxUsbTransport.open()[0].close()
            else:
                UsbTransport.open().close()
            print(f"{known[(vid, pid)]}: インターフェースを確保できました")
        except Exception as e:  # noqa: BLE001 - 原因をそのまま見せる
            print(f"{known[(vid, pid)]}: インターフェースを確保できません: {e!r}")
            return 1
    return 0


def cmd_test_pattern(args) -> int:
    display = open_display(args.flip)
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


class Runner:
    def __init__(self, args):
        self.args = args
        self.stop = threading.Event()
        self.display: TuringRevA | TurzxUsb | None = None
        self.snapshot: Snapshot | None = None
        self.status: str | None = None
        self.next_fetch = 0.0
        self.last_frame: bytes | None = None
        self.waiting_logged = False
        self.open_error: str | None = None

    def request_stop(self, signum, _frame) -> None:
        # 送信中に止めるとパネルの同期が崩れるため、ここでは合図だけ立てる
        log.info("終了の合図を受けました（%s）", signal.Signals(signum).name)
        self.stop.set()

    def _connect(self) -> bool:
        try:
            display = open_display(self.args.flip)
        except DeviceNotFound:
            if not self.waiting_logged:
                log.info("ディスプレイの接続を待っています（%s）", DEVICE_IDS)
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
            if self.status:
                log.info("取得が戻りました")
            self.status = None
            self.next_fetch = now + self.args.interval
        except UsageError as e:
            if e.message != self.status:
                log.warning("取得に失敗しました: %s", e.message)
            self.status = e.message
            self.next_fetch = now + max(self.args.interval, e.retry_after or 0)

    def _seconds_to_wait(self) -> float:
        now = datetime.now()
        to_next_minute = 60 - now.second - now.microsecond / 1_000_000 + 0.5
        to_next_fetch = self.next_fetch - time.monotonic()
        return max(1.0, min(to_next_minute, to_next_fetch))

    def loop(self) -> int:
        while not self.stop.is_set():
            if self.display is None and not self._connect():
                self.stop.wait(DEVICE_RETRY_SECONDS)
                continue
            self._fetch_if_due()
            image = THEMES[self.args.theme](self.snapshot, datetime.now(timezone.utc), self.status,
                                            meter_labels(self.args.model),
                                            size=(self.display.width, self.display.height))
            frame = image.tobytes()
            if frame != self.last_frame:
                try:
                    self.display.show(image)
                    self.last_frame = frame
                    if self.args.save_png:
                        image.save(self.args.save_png)
                except Exception as e:  # noqa: BLE001
                    if is_disconnected(e):  # 抜いただけなので、トレースバックは残さない
                        log.warning("ディスプレイが外れました。接続を待ちます")
                    else:
                        log.exception("送信に失敗しました。接続し直します")
                    self._close(self.display)
                    self.display = None
                    continue
            self.stop.wait(self._seconds_to_wait())
        if self.display is not None:
            self._close(self.display)
        log.info("終了しました")
        return 0


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

    probe = sub.add_parser("probe", help="ディスプレイの USB 情報を出す")
    probe.set_defaults(func=cmd_probe)

    for name, func, help_text in (("test-pattern", cmd_test_pattern, "向きと色の確認画面を出す"),
                                  ("run", cmd_run, "常駐して表示し続ける")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--brightness", type=int, default=30, help="明るさ 0〜100（既定: 30）")
        p.add_argument("--flip", action="store_true", help="上下を反転する（ケーブルの向きに合わせる）")
        p.set_defaults(func=func)
        if name == "run":
            p.add_argument("--interval", type=int, default=120, help="取得の間隔（秒、既定: 120）")
            p.add_argument("--save-png", help="送った画像をこのパスにも保存する（確認用）")
            p.add_argument("--theme", choices=THEMES, default=DEFAULT_THEME, help=theme_help)

    args = parser.parse_args(argv)
    if getattr(args, "interval", 60) < 60:
        parser.error("--interval は 60 秒以上にしてください")
    # 範囲外の値は接続した時点で初めて失敗し、run が初期化を繰り返し続けるため、ここで止める
    if not 0 <= getattr(args, "brightness", 0) <= 100:
        parser.error("--brightness は 0〜100 にしてください")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
