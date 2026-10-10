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
        time_left = WIDTH - gauge.HEADER_INSET - gauge.font(gauge.FOOTNOTE, gauge.SMALL_WEIGHT).getlength("15:24 時点")
        gap = range(round(time_left - gauge.STATUS_GAP) + 2, round(time_left) - 2)
        self.assertFalse(inked & set(gap), "理由と時刻が重なっている")


class LargeGaugeTest(unittest.TestCase):
    """5.2 インチ（1280×720）。寸法と文字を 2.25 倍にし、増えた横幅をカードに回す。"""

    SIZE = (1280, 720)
    LAYOUT = gauge.Layout(*SIZE)

    def test_size_and_scale(self):
        self.assertEqual(gauge.render(snapshot(26, 74, 93), NOW, size=self.SIZE).size, self.SIZE)
        self.assertEqual(self.LAYOUT.k, 2.25)
        self.assertEqual(self.LAYOUT.pt(gauge.TITLE1), 63)
        left, top, right, bottom = gauge.card_box(2, self.LAYOUT)
        self.assertAlmostEqual(right, 1280 - 12 * 2.25)
        self.assertGreater(self.LAYOUT.card_width, gauge.CARD_WIDTH * 2.25)

    def test_ring_color_follows_severity(self):
        image = gauge.render(snapshot(26, 74, 93), NOW, size=self.SIZE)
        _label, ring_y, *_rest, content_height = gauge.content_rows(self.LAYOUT)
        radius, width = self.LAYOUT.px(gauge.RING_RADIUS), self.LAYOUT.px(gauge.RING_WIDTH)
        for index, expected in enumerate((gauge.BLUE, gauge.ORANGE, gauge.RED)):
            left, top, right, bottom = gauge.card_box(index, self.LAYOUT)
            x, y = (left + right) / 2 + radius - width / 2, top + (bottom - top - content_height) / 2 + ring_y
            pixel = image.getpixel((math.floor(x), math.floor(y)))
            with self.subTest(index=index):
                self.assertTrue(all(abs(a - b) <= 12 for a, b in zip(pixel, expected)), pixel)

    def test_card_content_is_vertically_centered(self):
        image = gauge.render(snapshot(26, 74, 93), NOW, size=self.SIZE)
        inset = math.ceil(self.LAYOUT.px(gauge.CARD_RADIUS))
        for index in range(3):
            left, top, right, bottom = (round(v) for v in gauge.card_box(index, self.LAYOUT))
            rows = ink_rows(image, left + inset, right - inset, top + 3, bottom - 3, gauge.CARD)
            above, below = rows[0] - top, bottom - 1 - rows[-1]
            with self.subTest(index=index):
                self.assertLessEqual(abs(above - below), 6, (above, below))

    def test_status_stays_inside_and_apart_from_time(self):
        image = gauge.render(snapshot(8, 4, 0), NOW, "ログイン切れ（Claude Code を起動すると戻ります）", size=self.SIZE)
        width, px = self.SIZE[0], self.LAYOUT.px
        inked = {x for x in range(width) for y in range(0, round(px(gauge.CARD_TOP)) - 4)
                 if image.getpixel((x, y)) != gauge.BACKGROUND}
        self.assertFalse({x for x in inked if x > width - px(gauge.HEADER_INSET) + 2}, "右の余白にはみ出している")
        small = gauge.font(self.LAYOUT.pt(gauge.FOOTNOTE), gauge.SMALL_WEIGHT)
        time_left = width - px(gauge.HEADER_INSET) - small.getlength("15:24 時点")
        gap = range(round(time_left - px(gauge.STATUS_GAP)) + 3, round(time_left) - 3)
        self.assertFalse(inked & set(gap), "理由と時刻が重なっている")

    def test_renders_missing_values_and_errors(self):
        empty = Snapshot((Meter("5時間", None, None), Meter("週次", None, None), Meter("Opus週次", None, None)), NOW)
        for args in ((empty, NOW, "通信できません"), (None, NOW, "通信できません", ("5時間", "週次", "Opus週次")),
                     (snapshot(140, -5, None), NOW), (snapshot(100, 0.4, 50), NOW)):
            with self.subTest(args=args[2:] if len(args) > 2 else args[0].meters[0].percent):
                self.assertEqual(gauge.render(*args, size=self.SIZE).size, self.SIZE)


def gemini(*percents):
    resets = (NOW + timedelta(hours=2), NOW + timedelta(days=3))
    return Snapshot(tuple(Meter(label, p, r) for label, p, r in zip(("5時間", "週次"), percents, resets)), NOW)


def near(pixel, color, tolerance=12):
    return all(abs(a - b) <= tolerance for a, b in zip(pixel, color))


class GeminiGaugeTest(unittest.TestCase):
    """Gemini を足した画面（案 B）。上の段に Claude Code の 3 枚、下の段に Gemini の 2 枚。"""

    SIZE = (1280, 720)
    LAYOUT = gauge.Layout(*SIZE)

    def lower_ring_top(self, index):
        px = self.LAYOUT.px
        width = (self.SIZE[0] - px(gauge.MARGIN) * 2 - px(gauge.CARD_GAP)) / 2
        left = px(gauge.MARGIN) + index * (width + px(gauge.CARD_GAP))
        cx = left + px(15) + px(gauge.LOWER_RING_RADIUS)
        cy = (px(gauge.LOWER_CARD_TOP) + self.SIZE[1] - px(gauge.MARGIN)) / 2
        return round(cx), round(cy - px(gauge.LOWER_RING_RADIUS) + px(gauge.LOWER_RING_WIDTH) / 2)

    def test_sizes(self):
        for size in ((1280, 720), (480, 320)):
            with self.subTest(size=size):
                self.assertEqual(gauge.render_with_gemini(snapshot(26, 74, 93), gemini(12, 38), NOW, size=size).size,
                                 size)

    def test_lower_rings_follow_severity(self):
        image = gauge.render_with_gemini(snapshot(26, 74, 93), gemini(12, 92), NOW, size=self.SIZE)
        for index, expected in enumerate((gauge.BLUE, gauge.RED)):
            with self.subTest(index=index):
                self.assertTrue(near(image.getpixel(self.lower_ring_top(index)), expected))

    def test_upper_card_content_is_vertically_centered(self):
        image = gauge.render_with_gemini(snapshot(26, 74, 93), gemini(12, 38), NOW, size=self.SIZE)
        inset = math.ceil(self.LAYOUT.px(gauge.CARD_RADIUS))
        bottom = round(self.LAYOUT.px(gauge.UPPER_CARD_BOTTOM))
        for index in range(3):
            left, top, right, _ = (round(v) for v in gauge.card_box(index, self.LAYOUT))
            rows = ink_rows(image, left + inset, right - inset, top + 3, bottom - 3, gauge.CARD)
            above, below = rows[0] - top, bottom - 1 - rows[-1]
            with self.subTest(index=index):
                self.assertLessEqual(abs(above - below), 6, (above, below))

    def test_icons_are_drawn_left_of_titles_only_when_given(self):
        green = Image.new("RGBA", (64, 64), (0, 200, 0, 255))
        icons = {"claude": green, "gemini": green}
        px = self.LAYOUT.px
        spots = [(round(px(gauge.HEADER_INSET) + px(gauge.ICON_SIZE) / 2), round(gauge._badge(self.LAYOUT, b)[1]))
                 for b in (gauge.HEADER_BASELINE, gauge.GEMINI_BASELINE)]
        with_icons = gauge.render_with_gemini(snapshot(26, 74, 93), gemini(12, 38), NOW, size=self.SIZE, icons=icons)
        without = gauge.render_with_gemini(snapshot(26, 74, 93), gemini(12, 38), NOW, size=self.SIZE)
        for spot in spots:
            with self.subTest(spot=spot):
                self.assertTrue(near(with_icons.getpixel(spot), (0, 200, 0)))
                self.assertFalse(near(without.getpixel(spot), (0, 200, 0)))
        plain = gauge.render(snapshot(26, 74, 93), NOW, size=self.SIZE, icons={"claude": green})
        self.assertTrue(near(plain.getpixel(spots[0]), (0, 200, 0)))

    def test_gemini_failure_shows_the_orange_badge_in_its_own_header(self):
        image = gauge.render_with_gemini(snapshot(26, 74, 93), None, NOW, gemini_status="Antigravity にログインしていません",
                                         size=self.SIZE)
        lower = gauge._badge(self.LAYOUT, gauge.GEMINI_BASELINE)
        upper = gauge._badge(self.LAYOUT, gauge.HEADER_BASELINE)
        self.assertTrue(near(image.getpixel((round(lower[0] - 8), round(lower[1]))), gauge.ORANGE))
        self.assertFalse(near(image.getpixel((round(upper[0] - 8), round(upper[1]))), gauge.ORANGE))

    def test_load_icons_trims_transparent_margins_and_skips_missing(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as folder:
            image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
            image.paste((255, 0, 0, 255), (20, 30, 60, 90))
            image.save(Path(folder) / "claude.png")
            icons = gauge.load_icons(folder)
        self.assertEqual(set(icons), {"claude"})
        self.assertEqual(icons["claude"].size, (40, 60))


if __name__ == "__main__":
    unittest.main()
