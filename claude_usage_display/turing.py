"""Turing Smart Screen 3.5 インチ（rev A、USB ``1a86:5722``）への送信。

通信の仕様は次の 2 つから得た事実に基づき、コードは流用せずに書いている
（いずれも GPL-3.0 のため）。

- mathoudebine/turing-smart-screen-python ``library/lcd/lcd_comm_rev_a.py``
  （コマンド番号、6 バイトのコマンド形式、画素の形式）
- 同リポジトリ issue #7 と、そこで報告された macOS 用の実装（gist amarok30/cddaa9a9…）

macOS ではシリアル（``/dev/cu.usbmodem…``）を使わない。macOS の CDC ドライバーが
USB 転送を任意に分割・結合するため、コマンドと画素が混ざって画面が崩れる（issue #7）。
代わりに libusb でバルク OUT エンドポイント ``0x03`` へ直接書き、次を守る。

1. コマンドは 1 つずつ、それだけで 1 回の転送にする（画素と同じ転送に入れない）
2. ``SET_ORIENTATION`` は 11 バイト（6 バイトのコマンド＋向き＋幅・高さ）
3. 画素は 64 バイトの倍数で区切り、合計をちょうど 幅×高さ×2 バイトにする
4. 画素を送っている途中に、ほかのものを書かない
"""

from __future__ import annotations

import errno
import os
from enum import IntEnum

from PIL import Image

VID = 0x1A86
PID = 0x5722
INTERFACE = 1  # CDC のデータ側インターフェース
EP_OUT = 0x03
WRITE_TIMEOUT_MS = 10_000
CHUNK = 4096  # 64 の倍数

NATIVE_WIDTH, NATIVE_HEIGHT = 320, 480  # パネル本来の向き（縦長）

LIBUSB_CANDIDATES = ("/opt/homebrew/lib/libusb-1.0.dylib", "/usr/local/lib/libusb-1.0.dylib")


class Command(IntEnum):
    RESET = 101
    CLEAR = 102
    SCREEN_OFF = 108
    SCREEN_ON = 109
    SET_BRIGHTNESS = 110
    SET_ORIENTATION = 121
    DISPLAY_BITMAP = 197


class Orientation(IntEnum):
    PORTRAIT = 0
    REVERSE_PORTRAIT = 1
    LANDSCAPE = 2
    REVERSE_LANDSCAPE = 3


class DeviceNotFound(Exception):
    pass


def is_disconnected(error: BaseException) -> bool:
    """送信中にディスプレイが抜かれたときの例外か（libusb は ENODEV を返し、pyusb の USBError の errno に入る）。"""
    return getattr(error, "errno", None) == errno.ENODEV


def encode_command(cmd: Command, x: int = 0, y: int = 0, ex: int = 0, ey: int = 0) -> bytes:
    """座標 4 つ（各 10 ビット）とコマンド番号を 6 バイトに詰める。"""
    for value in (x, y, ex, ey):
        if not 0 <= value < 1024:
            raise ValueError(f"座標は 0〜1023: {value}")
    return bytes((
        x >> 2,
        ((x & 3) << 6) | (y >> 4),
        ((y & 15) << 4) | (ex >> 6),
        ((ex & 63) << 2) | (ey >> 8),
        ey & 255,
        int(cmd),
    ))


def encode_orientation(orientation: Orientation) -> bytes:
    landscape = orientation in (Orientation.LANDSCAPE, Orientation.REVERSE_LANDSCAPE)
    width, height = (NATIVE_HEIGHT, NATIVE_WIDTH) if landscape else (NATIVE_WIDTH, NATIVE_HEIGHT)
    return encode_command(Command.SET_ORIENTATION) + bytes((
        int(orientation) + 100, width >> 8, width & 255, height >> 8, height & 255,
    ))


def brightness_level(percent: int) -> int:
    """明るさ（0〜100%）をパネルの値（0 が最も明るく 255 が最も暗い）にする。"""
    if not 0 <= percent <= 100:
        raise ValueError(f"明るさは 0〜100: {percent}")
    return int(255 - percent * 255 / 100)


def to_rgb565le(image: Image.Image) -> bytes:
    raw = image.convert("RGB").tobytes()
    out = bytearray(len(raw) // 3 * 2)
    j = 0
    for i in range(0, len(raw), 3):
        value = ((raw[i] & 0xF8) << 8) | ((raw[i + 1] & 0xFC) << 3) | (raw[i + 2] >> 3)
        out[j] = value & 0xFF
        out[j + 1] = value >> 8
        j += 2
    return bytes(out)


def _libusb_backend():
    import usb.backend.libusb1 as libusb1

    for path in LIBUSB_CANDIDATES:
        if os.path.exists(path):
            backend = libusb1.get_backend(find_library=lambda _name, p=path: p)
            if backend is not None:
                return backend
    backend = libusb1.get_backend()
    if backend is None:
        raise RuntimeError("libusb が見つかりません（brew install libusb）")
    return backend


class UsbTransport:
    """1 回の ``write`` が 1 回の USB 転送になる送信路。"""

    def __init__(self, device):
        self.device = device

    @classmethod
    def open(cls) -> "UsbTransport":
        import usb.core
        import usb.util

        device = usb.core.find(idVendor=VID, idProduct=PID, backend=_libusb_backend())
        if device is None:
            raise DeviceNotFound(f"{VID:04x}:{PID:04x} が接続されていません")
        try:
            device.set_configuration()
        except usb.core.USBError:
            pass  # 構成済み
        try:
            if device.is_kernel_driver_active(INTERFACE):
                device.detach_kernel_driver(INTERFACE)
        except (NotImplementedError, usb.core.USBError):
            pass
        usb.util.claim_interface(device, INTERFACE)
        return cls(device)

    def write(self, data: bytes) -> None:
        self.device.write(EP_OUT, data, timeout=WRITE_TIMEOUT_MS)

    def close(self) -> None:
        import usb.util

        try:
            usb.util.release_interface(self.device, INTERFACE)
        finally:
            usb.util.dispose_resources(self.device)


class TuringRevA:
    def __init__(self, transport, flipped: bool = False):
        self.transport = transport
        self.orientation = Orientation.REVERSE_LANDSCAPE if flipped else Orientation.LANDSCAPE
        self.width, self.height = NATIVE_HEIGHT, NATIVE_WIDTH

    def _send_pixels(self, frame: bytes) -> None:
        for start in range(0, len(frame), CHUNK):
            self.transport.write(frame[start:start + CHUNK])

    def resync(self) -> None:
        """前のプロセスが画素の途中で止まっていても、数え残しを埋めて同期を戻す。

        パネルは DISPLAY_BITMAP の後、幅×高さ分の画素を数え終えるまで、届いたものを
        すべて画素として扱う。全画面分の黒を送れば、どの数え残しでも埋まる。
        同期していた場合は、画面が黒くなるだけである。
        """
        self.transport.write(encode_command(Command.DISPLAY_BITMAP, 0, 0, NATIVE_WIDTH - 1, NATIVE_HEIGHT - 1))
        self._send_pixels(bytes(NATIVE_WIDTH * NATIVE_HEIGHT * 2))

    def initialize(self, brightness: int) -> None:
        self.resync()
        self.transport.write(encode_orientation(self.orientation))
        self.set_brightness(brightness)

    def set_brightness(self, percent: int) -> None:
        self.transport.write(encode_command(Command.SET_BRIGHTNESS, brightness_level(percent)))

    def show_frame(self, frame: bytes) -> None:
        if len(frame) != self.width * self.height * 2:
            raise ValueError(f"画素数が合いません: {len(frame)} バイト")
        self.transport.write(encode_command(Command.DISPLAY_BITMAP, 0, 0, self.width - 1, self.height - 1))
        self._send_pixels(frame)

    def show(self, image: Image.Image) -> None:
        if image.size != (self.width, self.height):
            raise ValueError(f"画像の大きさが合いません: {image.size}")
        self.show_frame(to_rgb565le(image))

    def close(self) -> None:
        self.transport.close()
