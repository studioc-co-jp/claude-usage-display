import hashlib
import io
import random
import struct
import unittest
from datetime import datetime

from Crypto.Cipher import DES
from PIL import Image

from claude_usage_display.turzx_usb import (
    CMD_BRIGHTNESS,
    CMD_JPEG,
    CMD_PNG,
    CMD_SYNC,
    DES_KEY,
    MAX_PAYLOAD,
    ResponseError,
    TurzxUsb,
    brightness_value,
    check_response,
    encode_header,
    encode_image,
    milliseconds_since_midnight,
)

TIMESTAMP = 3_723_004  # 01:02:03.004
NOW = datetime(2026, 10, 9, 1, 2, 3, 4_000)


def decrypt(header: bytes) -> bytes:
    return DES.new(DES_KEY, DES.MODE_CBC, iv=DES_KEY).decrypt(header[:504])


class FakeTransport:
    """見出しを復号し、本物と同じ形の応答（命令番号・C8・時刻）を返す送信路。"""

    def __init__(self, wrong_status: bool = False):
        self.writes: list[bytes] = []
        self.drained = False
        self.closed = False
        self.wrong_status = wrong_status

    def write(self, data: bytes) -> None:
        self.writes.append(bytes(data))

    def read(self) -> bytes:
        plain = decrypt(self.writes[-1])
        status = 0x00 if self.wrong_status else 0xC8
        return bytes((plain[0], status)) + plain[4:8] + bytes(506)

    def drain(self) -> None:
        self.drained = True

    def close(self) -> None:
        self.closed = True

    def commands(self) -> list[int]:
        return [decrypt(w)[0] for w in self.writes]


class HeaderTest(unittest.TestCase):
    def test_matches_independent_implementation(self):
        # phstudy/turing-smart-screen-cli（MIT）の build_command_packet_header と encrypt_command_packet で、
        # 時刻を 3,723,004 ミリ秒に固定して作った見出しの SHA-256（2026-10-09 に生成）
        expected = {
            (CMD_BRIGHTNESS, bytes((30,))): "a28c3007d717258c577e17bff2f568ec8ebef227482f279472ed1859aa8f5bde",
            (CMD_PNG, struct.pack(">I", 123456)): "86acbac6e0ac1fab647fb5010b44325f51bdba0f6a89c62d1369d24e3971ee1f",
            (CMD_SYNC, b""): "0c8df4e9b47c2dce77a5104f6e8c11e22c15a64323437b7b7a439befe34018d5",
        }
        for (command, args), digest in expected.items():
            with self.subTest(command=command):
                self.assertEqual(hashlib.sha256(encode_header(command, TIMESTAMP, args)).hexdigest(), digest)

    def test_fields_and_trailer(self):
        header = encode_header(CMD_PNG, TIMESTAMP, struct.pack(">I", 3))
        self.assertEqual(len(header), 512)
        self.assertEqual(header[504:], bytes(6) + b"\xa1\x1a")
        plain = decrypt(header)
        self.assertEqual(plain[:4], bytes((CMD_PNG, 0, 0x1A, 0x6D)))
        self.assertEqual(struct.unpack_from("<I", plain, 4)[0], TIMESTAMP)
        self.assertEqual(struct.unpack_from(">I", plain, 8)[0], 3)
        self.assertEqual(plain[12:], bytes(492))

    def test_timestamp_is_milliseconds_since_local_midnight(self):
        self.assertEqual(milliseconds_since_midnight(NOW), TIMESTAMP)
        self.assertEqual(milliseconds_since_midnight(datetime(2026, 10, 9)), 0)

    def test_response_check(self):
        ok = bytes((CMD_PNG, 0xC8)) + struct.pack("<I", TIMESTAMP)
        check_response(CMD_PNG, TIMESTAMP, ok)
        for command, timestamp, response in ((CMD_SYNC, TIMESTAMP, ok), (CMD_PNG, TIMESTAMP + 1, ok),
                                             (CMD_PNG, TIMESTAMP, ok[:5]), (CMD_PNG, TIMESTAMP, ok[:1] + b"\x00" + ok[2:])):
            with self.subTest(response=response.hex()), self.assertRaises(ResponseError):
                check_response(command, timestamp, response)

    def test_brightness(self):
        self.assertEqual([brightness_value(p) for p in (0, 30, 50, 100)], [0, 30, 51, 102])
        for percent in (-1, 101):
            with self.assertRaises(ValueError):
                brightness_value(percent)


class EncodeImageTest(unittest.TestCase):
    def test_flat_image_is_png(self):
        command, data = encode_image(Image.new("RGB", (720, 1280), (33, 32, 33)))
        self.assertEqual(command, CMD_PNG)
        self.assertEqual(Image.open(io.BytesIO(data)).format, "PNG")

    def test_falls_back_to_jpeg_under_the_limit(self):
        noise = Image.frombytes("RGB", (720, 1280), random.Random(1).randbytes(720 * 1280 * 3))
        command, data = encode_image(noise)
        self.assertEqual(command, CMD_JPEG)
        self.assertLessEqual(len(data), MAX_PAYLOAD)
        self.assertEqual(Image.open(io.BytesIO(data)).size, (720, 1280))


class TurzxUsbTest(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.display = TurzxUsb(self.transport, clock=lambda: NOW)

    def test_landscape_size(self):
        self.assertEqual((self.display.width, self.display.height), (1280, 720))

    def test_initialize_drains_then_syncs_then_sets_brightness(self):
        self.display.initialize(brightness=30)
        self.assertTrue(self.transport.drained)
        self.assertEqual(self.transport.commands(), [CMD_SYNC, CMD_BRIGHTNESS])
        self.assertEqual(decrypt(self.transport.writes[1])[8], 30)
        self.assertEqual(len(self.transport.writes[0]), 512)

    def test_image_is_rotated_to_portrait_and_sent_with_its_length(self):
        image = Image.new("RGB", (1280, 720))
        image.putpixel((0, 0), (255, 0, 0))  # 横向きの左上
        self.display.show(image)
        sent = self.transport.writes[-1]
        plain = decrypt(sent)
        self.assertEqual(plain[0], CMD_PNG)
        self.assertEqual(struct.unpack_from(">I", plain, 8)[0], len(sent) - 512)
        portrait = Image.open(io.BytesIO(sent[512:])).convert("RGB")
        self.assertEqual(portrait.size, (720, 1280))
        self.assertEqual(portrait.getpixel((719, 0)), (255, 0, 0))  # 時計回りに 90 度回すと右上に来る

    def test_flip_rotates_the_other_way(self):
        transport = FakeTransport()
        image = Image.new("RGB", (1280, 720))
        image.putpixel((0, 0), (255, 0, 0))
        TurzxUsb(transport, flipped=True, clock=lambda: NOW).show(image)
        portrait = Image.open(io.BytesIO(transport.writes[-1][512:])).convert("RGB")
        self.assertEqual(portrait.getpixel((0, 1279)), (255, 0, 0))

    def test_portrait_is_sent_without_rotation(self):
        transport = FakeTransport()
        display = TurzxUsb(transport, clock=lambda: NOW, portrait=True)
        self.assertEqual((display.width, display.height), (720, 1280))
        image = Image.new("RGB", (720, 1280))
        image.putpixel((0, 0), (255, 0, 0))
        display.show(image)
        sent = Image.open(io.BytesIO(transport.writes[-1][512:])).convert("RGB")
        self.assertEqual((sent.size, sent.getpixel((0, 0))), ((720, 1280), (255, 0, 0)))

    def test_wrong_size_is_rejected_before_sending(self):
        with self.assertRaises(ValueError):
            self.display.show(Image.new("RGB", (480, 320)))
        self.assertEqual(self.transport.writes, [])

    def test_unexpected_response_raises_and_is_kept_for_inspection(self):
        display = TurzxUsb(FakeTransport(wrong_status=True), clock=lambda: NOW)
        with self.assertRaises(ResponseError):
            display.initialize(brightness=30)
        command, response = display.history[-1]
        self.assertEqual((command, response[1]), (CMD_SYNC, 0x00))


if __name__ == "__main__":
    unittest.main()
