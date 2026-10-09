"""TURZX の新しい世代（5.2 インチ、USB ``1cbe:0050``）への送信。

通信の仕様は次の 3 つから得た事実に基づき、コードは流用せずに書いている。

- mathoudebine/turing-smart-screen-python ``library/lcd/lcd_comm_turing_usb.py``（GPL-3.0。仕様だけを読む）
  機種ごとの PID と解像度、明るさの命令（14）と値の換算、画像を縦長に回して送ること、1 MiB の上限
- nuitsjp/token-dashboard ``internal/turzx/``（MIT。9.2 インチ ``1cbe:0092`` を WinUSB で動かす実装）
  見出しの並び、応答の確かめ方、前のプロセスの読み残しを捨てる手順
- phstudy/turing-smart-screen-cli ``src/turingscreencli/transport.py``（MIT。テストの答え合わせの値に使う）

rev A（``turing.py``）と違い、シリアル（CDC）ではなくベンダー独自のインターフェース 0 を使い、
1 回の書き込みに「暗号化した 512 バイトの見出し＋中身（PNG・JPEG など）」をまとめて送る。
1 枚ごとに完結するので、rev A のように画素の数え違いで同期が崩れることはない。
送るたびに応答を 1 つ読み、命令番号・``C8``・見出しの時刻が返ってきたかを確かめる。

見出し（512 バイト）
  0..503    DES-CBC（鍵・IV とも ``slv3tuzx``）で暗号化した 504 バイト。平文は
            0: 命令番号、2..3: ``1A 6D``、4..7: その日の 0 時からのミリ秒（リトルエンディアン）、
            8..: 命令ごとの値（画像は中身の長さをビッグエンディアン 4 バイト、明るさは 1 バイト）
  504..509  0
  510..511  ``A1 1A``
応答: 0: 命令番号、1: ``C8``、2..5: 見出しの時刻（リトルエンディアン）

macOS の実機ではまだ確かめていない（2026-10-09 時点。docs/handover.md §5-9）。
"""

from __future__ import annotations

import io
import struct
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta

from PIL import Image

from .turing import DeviceNotFound, _libusb_backend

VID = 0x1CBE
# PID: (名前, 本来の幅, 本来の高さ)。本来の向きは縦長で、横向きの画像は回してから送る
MODELS = {0x0050: ("5.2 インチ", 720, 1280)}

INTERFACE = 0
TIMEOUT_MS = 5000
DRAIN_TIMEOUT_MS = 100
DRAIN_LIMIT = 16
MAX_PAYLOAD = 1 << 20  # 1 回に送れる中身の上限（1 MiB）

DES_KEY = b"slv3tuzx"
HEADER_SIZE = 512
CMD_SYNC = 10
CMD_BRIGHTNESS = 14
CMD_JPEG = 101
CMD_PNG = 102
RESPONSE_OK = 0xC8

JPEG_QUALITIES = (90, 80, 70, 60, 50)


class ResponseError(Exception):
    pass


def milliseconds_since_midnight(now: datetime) -> int:
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return (now - midnight) // timedelta(milliseconds=1)


def encode_header(command: int, timestamp: int, args: bytes = b"") -> bytes:
    if len(args) > 504 - 8:
        raise ValueError(f"命令の値が長すぎます: {len(args)} バイト")
    from Crypto.Cipher import DES

    plain = bytearray(504)
    plain[0] = command
    plain[2:4] = b"\x1a\x6d"
    plain[4:8] = struct.pack("<I", timestamp)
    plain[8:8 + len(args)] = args
    encrypted = DES.new(DES_KEY, DES.MODE_CBC, iv=DES_KEY).encrypt(bytes(plain))
    return encrypted + bytes(6) + b"\xa1\x1a"


def check_response(command: int, timestamp: int, response: bytes) -> None:
    if (len(response) < 6 or response[0] != command or response[1] != RESPONSE_OK
            or struct.unpack_from("<I", response, 2)[0] != timestamp):
        raise ResponseError(f"命令 {command} への応答が想定と違います: {response[:16].hex(' ')}")


def brightness_value(percent: int) -> int:
    """明るさ（0〜100%）をパネルの値（0〜102）にする。"""
    if not 0 <= percent <= 100:
        raise ValueError(f"明るさは 0〜100: {percent}")
    return percent * 102 // 100


def encode_image(image: Image.Image) -> tuple[int, bytes]:
    """PNG で送り、1 MiB を超えるときだけ JPEG にする。命令番号と中身を返す。"""
    rgb = image.convert("RGB")
    buffer = io.BytesIO()
    rgb.save(buffer, format="PNG")
    if buffer.tell() <= MAX_PAYLOAD:
        return CMD_PNG, buffer.getvalue()
    for quality in JPEG_QUALITIES:
        buffer = io.BytesIO()
        rgb.save(buffer, format="JPEG", quality=quality)  # Pillow の既定はベースライン JPEG
        if buffer.tell() <= MAX_PAYLOAD:
            return CMD_JPEG, buffer.getvalue()
    raise ValueError(f"画像を {MAX_PAYLOAD} バイト以下にできません")


class TurzxUsbTransport:
    """インターフェース 0 のバルク OUT に書き、バルク IN から応答を読む送信路。"""

    def __init__(self, device, ep_out: int, ep_in: int):
        self.device = device
        self.ep_out = ep_out
        self.ep_in = ep_in

    @classmethod
    def open(cls) -> tuple["TurzxUsbTransport", int]:
        """つながっている機種を開き、送信路と PID を返す。"""
        import usb.core
        import usb.util

        backend = _libusb_backend()
        for pid in MODELS:
            device = usb.core.find(idVendor=VID, idProduct=pid, backend=backend)
            if device is not None:
                break
        else:
            raise DeviceNotFound(f"{VID:04x}:" + "/".join(f"{pid:04x}" for pid in MODELS) + " が接続されていません")
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
        bulk = [e for e in device.get_active_configuration()[(INTERFACE, 0)]
                if usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK]
        ins = [e.bEndpointAddress for e in bulk if usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN]
        outs = [e.bEndpointAddress for e in bulk if usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT]
        if not ins or not outs:
            usb.util.release_interface(device, INTERFACE)
            usb.util.dispose_resources(device)
            raise RuntimeError(f"インターフェース {INTERFACE} にバルクの IN・OUT が見つかりません")
        return cls(device, outs[0], ins[0]), pid

    def write(self, data: bytes) -> None:
        self.device.write(self.ep_out, data, timeout=TIMEOUT_MS)

    def read(self, timeout_ms: int = TIMEOUT_MS) -> bytes:
        # 512 バイトの応答の後に、長さ 0 のパケットが続くことがある（token-dashboard の read）
        for _ in range(4):
            data = bytes(self.device.read(self.ep_in, 512, timeout=timeout_ms))
            if data:
                return data
        raise ResponseError("長さ 0 の応答が続きました")

    def drain(self) -> None:
        """前のプロセスが読まずに残した応答を捨てる。"""
        import usb.core

        for _ in range(DRAIN_LIMIT):
            try:
                self.read(DRAIN_TIMEOUT_MS)
            except usb.core.USBTimeoutError:
                return
        raise ResponseError("読み残しの応答が消えません")

    def close(self) -> None:
        import usb.util

        try:
            usb.util.release_interface(self.device, INTERFACE)
        finally:
            usb.util.dispose_resources(self.device)


class TurzxUsb:
    """横向きの画像を受け取り、縦長に回して送る。"""

    def __init__(self, transport, pid: int = 0x0050, flipped: bool = False,
                 clock: Callable[[], datetime] = datetime.now):
        self.transport = transport
        self.name, native_width, native_height = MODELS[pid]
        self.width, self.height = native_height, native_width
        self.rotation = Image.Transpose.ROTATE_90 if flipped else Image.Transpose.ROTATE_270
        self.clock = clock
        self.history: deque[tuple[int, bytes]] = deque(maxlen=8)  # (命令番号, 応答)。確認画面で見せる

    def _exchange(self, command: int, args: bytes = b"", payload: bytes = b"") -> bytes:
        timestamp = milliseconds_since_midnight(self.clock())
        self.transport.write(encode_header(command, timestamp, args) + payload)
        response = self.transport.read()
        self.history.append((command, response))
        check_response(command, timestamp, response)
        return response

    def initialize(self, brightness: int) -> None:
        self.transport.drain()
        self._exchange(CMD_SYNC)
        self.set_brightness(brightness)

    def set_brightness(self, percent: int) -> None:
        self._exchange(CMD_BRIGHTNESS, bytes((brightness_value(percent),)))

    def show(self, image: Image.Image) -> None:
        if image.size != (self.width, self.height):
            raise ValueError(f"画像の大きさが合いません: {image.size}")
        command, data = encode_image(image.transpose(self.rotation))
        self._exchange(command, struct.pack(">I", len(data)), data)

    def close(self) -> None:
        self.transport.close()
