import unittest
from datetime import datetime, timedelta, timezone

from claude_usage_display.render import (
    ACCENT,
    CRITICAL,
    HEIGHT,
    MARGIN_X,
    STATUS_GAP,
    SURFACE,
    WARNING,
    WIDTH,
    fit_font,
    font,
    format_reset,
    render,
    severity_color,
)
from claude_usage_display.usage import Meter, Snapshot

NOW = datetime(2026, 10, 5, 6, 24, tzinfo=timezone.utc)  # JST 15:24


class FormatResetTest(unittest.TestCase):
    def test_same_day_shows_time_and_remaining(self):
        self.assertEqual(format_reset(NOW + timedelta(hours=1, minutes=5), NOW), "リセット 16:29（あと1時間05分）")

    def test_under_an_hour(self):
        self.assertEqual(format_reset(NOW + timedelta(minutes=7), NOW), "リセット 15:31（あと7分）")

    def test_next_day_shows_date_even_within_24_hours(self):
        self.assertEqual(format_reset(NOW + timedelta(hours=10), NOW), "リセット 10/6(火) 01:24（あと10時間00分）")

    def test_days_ahead(self):
        resets = datetime(2026, 10, 12, 0, 59, 59, tzinfo=timezone.utc)
        self.assertEqual(format_reset(resets, NOW), "リセット 10/12(月) 09:59（あと6日18時間）")

    def test_past_and_missing(self):
        self.assertEqual(format_reset(NOW - timedelta(minutes=1), NOW), "リセット済み（次の取得で更新）")
        self.assertEqual(format_reset(None, NOW), "リセット時刻なし")


class SeverityTest(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(severity_color(69.9), ACCENT)
        self.assertEqual(severity_color(70), WARNING)
        self.assertEqual(severity_color(90), CRITICAL)


class RenderTest(unittest.TestCase):
    def test_size_and_mode(self):
        snapshot = Snapshot((Meter("5時間", 26, NOW), Meter("週次", 3, NOW), Meter("Fable週次", 0, NOW)), NOW)
        image = render(snapshot, NOW)
        self.assertEqual((image.size, image.mode), ((WIDTH, HEIGHT), "RGB"))

    def test_renders_without_snapshot_and_with_error(self):
        image = render(None, NOW, "通信できません")
        self.assertEqual(image.size, (WIDTH, HEIGHT))

    def test_over_100_percent_does_not_overflow(self):
        snapshot = Snapshot((Meter("5時間", 140, NOW), Meter("週次", -5, NOW), Meter("Fable週次", None, None)), NOW)
        render(snapshot, NOW)

    def test_status_line_stays_inside_and_apart_from_time(self):
        snapshot = Snapshot((Meter("5時間", 26, NOW), Meter("週次", 3, NOW), Meter("Fable週次", 0, NOW)), NOW)
        time_left = WIDTH - MARGIN_X - font(14, 3).getlength("15:24 時点")
        for status in ("ログイン切れ（Claude Code を起動すると戻ります）",  # いちばん長い実際の文言
                       "ログイン切れ（Claude Code を起動すると戻ります）。再試行中"):  # 縮めて収める長さ
            with self.subTest(status=status):
                image = render(snapshot, NOW, status)
                inked = {x for x in range(WIDTH) for y in range(HEIGHT - 26, HEIGHT)
                         if image.getpixel((x, y)) != SURFACE}
                self.assertFalse({x for x in inked if x > WIDTH - MARGIN_X + 1}, "右の余白にはみ出している")
                gap = range(round(time_left - STATUS_GAP) + 2, round(time_left) - 2)
                self.assertFalse(inked & set(gap), "理由と時刻が重なっている")

    def test_fit_font_shrinks_only_when_needed(self):
        self.assertEqual(fit_font("短い", 448, 14).size, 14)
        long_text = "長" * 40
        fitted = fit_font(long_text, 448, 14)
        self.assertLess(fitted.size, 14)
        self.assertLessEqual(fitted.getlength(long_text), 448)


if __name__ == "__main__":
    unittest.main()
