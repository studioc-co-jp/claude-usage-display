import unittest

from PIL import Image

from claude_usage_display.turing import (
    Command,
    Orientation,
    TuringRevA,
    brightness_level,
    encode_command,
    encode_orientation,
    to_rgb565le,
)


class FakeTransport:
    def __init__(self):
        self.writes: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> None:
        self.writes.append(bytes(data))

    def close(self) -> None:
        self.closed = True


class EncodeTest(unittest.TestCase):
    def test_full_screen_bitmap_header_landscape(self):
        # x=0, y=0, ex=479, ey=319 を 10 ビットずつ詰める
        self.assertEqual(encode_command(Command.DISPLAY_BITMAP, 0, 0, 479, 319), bytes((0, 0, 7, 125, 63, 197)))

    def test_full_screen_bitmap_header_portrait(self):
        self.assertEqual(encode_command(Command.DISPLAY_BITMAP, 0, 0, 319, 479), bytes((0, 0, 4, 253, 223, 197)))

    def test_coordinates_round_trip(self):
        for x, y, ex, ey in ((1, 2, 3, 4), (1023, 1023, 1023, 1023), (5, 600, 700, 9)):
            b = encode_command(Command.CLEAR, x, y, ex, ey)
            self.assertEqual((b[0] << 2) | (b[1] >> 6), x)
            self.assertEqual(((b[1] & 63) << 4) | (b[2] >> 4), y)
            self.assertEqual(((b[2] & 15) << 6) | (b[3] >> 2), ex)
            self.assertEqual(((b[3] & 3) << 8) | b[4], ey)

    def test_coordinate_out_of_range(self):
        with self.assertRaises(ValueError):
            encode_command(Command.CLEAR, 1024)

    def test_orientation_is_11_bytes(self):
        self.assertEqual(encode_orientation(Orientation.LANDSCAPE), bytes((0, 0, 0, 0, 0, 121, 102, 1, 224, 1, 64)))
        self.assertEqual(encode_orientation(Orientation.REVERSE_LANDSCAPE)[6], 103)
        self.assertEqual(encode_orientation(Orientation.PORTRAIT)[7:], bytes((1, 64, 1, 224)))

    def test_brightness(self):
        self.assertEqual(brightness_level(100), 0)
        self.assertEqual(brightness_level(0), 255)
        self.assertEqual(brightness_level(30), 178)
        with self.assertRaises(ValueError):
            brightness_level(101)

    def test_rgb565_little_endian(self):
        image = Image.new("RGB", (4, 1))
        image.putpixel((0, 0), (255, 0, 0))
        image.putpixel((1, 0), (0, 255, 0))
        image.putpixel((2, 0), (0, 0, 255))
        image.putpixel((3, 0), (255, 255, 255))
        self.assertEqual(to_rgb565le(image), bytes.fromhex("00f8" "e007" "1f00" "ffff"))


class TuringRevATest(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.display = TuringRevA(self.transport)

    def test_frame_is_header_then_64_aligned_chunks(self):
        self.display.show(Image.new("RGB", (480, 320), (10, 20, 30)))
        header, *chunks = self.transport.writes
        self.assertEqual(header, encode_command(Command.DISPLAY_BITMAP, 0, 0, 479, 319))
        self.assertEqual(sum(map(len, chunks)), 480 * 320 * 2)
        self.assertTrue(all(len(c) % 64 == 0 for c in chunks))

    def test_initialize_resyncs_then_sets_orientation_and_brightness(self):
        self.display.initialize(brightness=30)
        writes = self.transport.writes
        self.assertEqual(writes[0], encode_command(Command.DISPLAY_BITMAP, 0, 0, 319, 479))
        self.assertEqual(sum(map(len, writes[1:-2])), 320 * 480 * 2)
        self.assertEqual(writes[-2], encode_orientation(Orientation.LANDSCAPE))
        self.assertEqual(writes[-1], encode_command(Command.SET_BRIGHTNESS, 178))

    def test_wrong_size_is_rejected_before_sending(self):
        with self.assertRaises(ValueError):
            self.display.show(Image.new("RGB", (320, 480)))
        self.assertEqual(self.transport.writes, [])

    def test_flip_uses_reverse_landscape(self):
        TuringRevA(self.transport, flipped=True).initialize(brightness=30)
        self.assertEqual(self.transport.writes[-2][6], 103)


if __name__ == "__main__":
    unittest.main()
