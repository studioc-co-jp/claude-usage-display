import math
import unittest
from datetime import datetime, timedelta, timezone

from PIL import Image

from claude_usage_display import gauge
from claude_usage_display.render import HEIGHT, WIDTH
from claude_usage_display.turing import to_rgb565le
from claude_usage_display.usage import Meter, Snapshot

NOW = datetime(2026, 10, 5, 6, 24, tzinfo=timezone.utc)  # JST 15:24


def snapshot(*percents):
    resets = (NOW + timedelta(hours=1, minutes=5), NOW + timedelta(days=6, hours=17), NOW + timedelta(days=6, hours=17))
    labels = ("5時間", "週次", "Fable週次")
    return Snapshot(tuple(Meter(label, p, r) for label, p, r in zip(labels, percents, resets)), NOW)


def ink_rows(image, left, right, top, bottom, background):
    """範囲の中で、背景以外の色がある行の y。"""
    return [y for y in range(top, bottom)
            if any(image.getpixel((x, y)) != background for x in range(left, right))]


class ResetLinesTest(unittest.TestCase):
    def test_same_day_drops_leading_zero(self):
        self.assertEqual(gauge.reset_lines(NOW + timedelta(minutes=96), NOW), ("17:00", "あと1時間36分"))
        morning = datetime(2026, 10, 4, 22, 0, tzinfo=timezone.utc)  # JST 7:00
        self.assertEqual(gauge.reset_lines(morning + timedelta(hours=2, minutes=5), morning)[0], "9:05")

    def test_other_day_shows_date_and_weekday(self):
        self.assertEqual(gauge.reset_lines(NOW + timedelta(days=6, hours=17), NOW),
                         ("10/12(月) 8:24", "あと6日17時間"))

    def test_missing_and_past(self):
        self.assertEqual(gauge.reset_lines(None, NOW), ("--", ""))
        self.assertEqual(gauge.reset_lines(NOW, NOW), ("リセット済み", "次の取得で更新"))


class GaugeRenderTest(unittest.TestCase):
    def test_size_and_mode(self):
        image = gauge.render(snapshot(26, 74, 93), NOW)
        self.assertEqual((image.size, image.mode), ((WIDTH, HEIGHT), "RGB"))

    def test_card_color_survives_rgb565(self):
        frame = to_rgb565le(Image.new("RGB", (1, 1), gauge.CARD))
        value = frame[0] | frame[1] << 8
        r, g, b = value >> 11, (value >> 5) & 63, value & 31
        self.assertEqual(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)), gauge.CARD)

    def test_ring_color_follows_severity(self):
        image = gauge.render(snapshot(26, 74, 93), NOW)
        label_y, ring_y, *_rest, content_height = gauge.content_rows()
        for index, expected in enumerate((gauge.BLUE, gauge.ORANGE, gauge.RED)):
            left, top, right, bottom = gauge.card_box(index)
            cx = (left + right) / 2
            cy = top + (bottom - top - content_height) / 2 + ring_y
            # 3 時の位置（どの値でも 25% を超えていれば塗られている）
            x, y = cx + gauge.RING_RADIUS - gauge.RING_WIDTH / 2, cy
            pixel = image.getpixel((math.floor(x), math.floor(y)))
            with self.subTest(index=index):
                self.assertTrue(all(abs(a - b) <= 12 for a, b in zip(pixel, expected)), pixel)

    def test_card_content_is_vertically_centered(self):
        for snap in (snapshot(26, 74, 93), snapshot(0, 0, 0)):
            image = gauge.render(snap, NOW)
            for index in range(3):
                left, top, right, bottom = (round(v) for v in gauge.card_box(index))
                # 角の丸みを避けて内側だけを見る
                rows = ink_rows(image, left + gauge.CARD_RADIUS, right - gauge.CARD_RADIUS,
                                top + 2, bottom - 2, gauge.CARD)
                above, below = rows[0] - top, bottom - 1 - rows[-1]
                with self.subTest(index=index):
                    self.assertLessEqual(abs(above - below), 3, (above, below))

    def test_renders_missing_values_and_errors(self):
        empty = Snapshot((Meter("5時間", None, None), Meter("週次", None, None), Meter("Opus週次", None, None)), NOW)
        for args in ((empty, NOW, "通信できません"), (None, NOW, "通信できません", ("5時間", "週次", "Opus週次")),
                     (snapshot(140, -5, None), NOW), (snapshot(100, 0.4, 50), NOW)):
            with self.subTest(args=args[2:] if len(args) > 2 else args[0].meters[0].percent):
                self.assertEqual(gauge.render(*args).size, (WIDTH, HEIGHT))

    def test_status_stays_inside_and_apart_from_time(self):
        image = gauge.render(snapshot(8, 4, 0), NOW, "ログイン切れ（Claude Code を起動すると戻ります）")
        header = range(0, gauge.CARD_TOP - 2)
        inked = {x for x in range(WIDTH) for y in header if image.getpixel((x, y)) != gauge.BACKGROUND}
        self.assertFalse({x for x in inked if x > WIDTH - gauge.HEADER_INSET + 1}, "右の余白にはみ出している")
        time_left = WIDTH - gauge.HEADER_INSET - gauge.font(gauge.FOOTNOTE, 3).getlength("15:24 時点")
        gap = range(round(time_left - gauge.STATUS_GAP) + 2, round(time_left) - 2)
        self.assertFalse(inked & set(gap), "理由と時刻が重なっている")


if __name__ == "__main__":
    unittest.main()
