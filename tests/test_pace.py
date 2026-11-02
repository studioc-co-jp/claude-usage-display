import unittest
from datetime import datetime, timedelta, timezone

from claude_usage_display import gauge, pace
from claude_usage_display.render import font
from claude_usage_display.usage import Meter, Snapshot

NOW = datetime(2026, 11, 3, 13, 10, tzinfo=timezone.utc)  # JST 22:10
SIZE = (1280, 720)


def snapshot(session=26.0, weekly=74.0, scoped=93.0):
    return Snapshot((Meter("5時間", session, NOW + timedelta(hours=1, minutes=5)),
                     Meter("週次", weekly, NOW + timedelta(days=3, hours=5)),
                     Meter("Fable週次", scoped, NOW + timedelta(days=3, hours=5))), NOW)


def near(pixel, color, tolerance=12):
    return all(abs(a - b) <= tolerance for a, b in zip(pixel, color))


def bar_row(index):
    """棒の縦の中ほど（ピクセル）。"""
    return round(pace.ROWS[index] + sum(pace.BAR) / 2)


class PaceTest(unittest.TestCase):
    def test_elapsed_is_the_share_of_the_window_that_has_passed(self):
        # 5時間は 23:15 にリセット → 18:15 から 3 時間 55 分（78%）。週次は 3 日 5 時間後 → 7 日のうち 54%
        session, weekly, _ = snapshot().meters
        self.assertAlmostEqual(pace.elapsed(session, pace.WINDOWS[0], NOW), 235 / 300)
        self.assertAlmostEqual(pace.elapsed(weekly, pace.WINDOWS[1], NOW), 1 - (3 * 24 + 5) / (7 * 24))
        self.assertIsNone(pace.elapsed(Meter("5時間", None, None), pace.WINDOWS[0], NOW))
        self.assertEqual(pace.elapsed(Meter("5時間", 1, NOW - timedelta(minutes=1)), pace.WINDOWS[0], NOW), 1.0)
        self.assertEqual(pace.elapsed(Meter("週次", 1, NOW + timedelta(days=8)), pace.WINDOWS[1], NOW), 0.0)

    def test_bars_are_filled_to_the_percent_and_marked_at_the_elapsed_share(self):
        image = pace.render(snapshot(), NOW, size=SIZE)
        self.assertEqual(image.size, SIZE)
        left, right = pace.MARGIN, SIZE[0] - pace.MARGIN
        y = bar_row(0)
        blue = gauge.layout_for(SIZE).blue
        self.assertTrue(near(image.getpixel((round(left + (right - left) * 0.20), y)), blue))  # 26% の手前は塗る
        self.assertFalse(near(image.getpixel((round(left + (right - left) * 0.40), y)), blue))  # 26% より先は地
        mark = round(left + (right - left) * 235 / 300)
        self.assertTrue(near(image.getpixel((mark, y)), (255, 255, 255), 30))  # 経過 78% の位置に白い目印
        above = round(pace.ROWS[0] + pace.BAR[0] - pace.MARK[1] / 2)
        self.assertTrue(near(image.getpixel((mark, above)), (255, 255, 255), 30))  # 目印は棒の上にはみ出す
        self.assertTrue(near(image.getpixel((round(left + (right - left) * 0.5), bar_row(1))), gauge.ORANGE))  # 74%

    def test_only_session_and_weekly_are_drawn(self):
        # Fable を使っていないので 2 項目だけ（2026-11-03 ユーザーの指示）。3 段目の位置は黒のまま
        image = pace.render(snapshot(), NOW, size=SIZE)
        below = [image.getpixel((x, 700)) for x in range(pace.MARGIN, SIZE[0] - pace.MARGIN, 10)]
        self.assertTrue(all(p == gauge.BACKGROUND for p in below))

    def test_missing_values_and_fetch_errors_still_render(self):
        gone = Snapshot((Meter("5時間", None, None), Meter("週次", 9, NOW + timedelta(days=6))), NOW)
        image = pace.render(gone, NOW, "5時間の枠がなくなりました", size=SIZE)
        badge = gauge._badge(gauge.layout_for(SIZE), gauge.HEADER_BASELINE)
        self.assertTrue(near(image.getpixel((round(badge[0]) - 10, round(badge[1]))), gauge.ORANGE, 40))  # 「!」の横
        row = [image.getpixel((x, bar_row(0))) for x in range(pace.MARGIN + 40, SIZE[0] - pace.MARGIN - 40, 20)]
        self.assertFalse(any(min(p) > 200 for p in row))  # 値もリセットも無い段には、目印を出さない
        self.assertEqual(pace.render(None, NOW, "通信できません", size=SIZE).size, SIZE)

    def test_long_texts_do_not_overlap(self):
        # 名前と「経過 100%」は数字「100%」の左、下の行は左右で重ならない
        name, unit, number = font(pace.NAME[1], 6), gauge.rounded(pace.UNIT), gauge.rounded(pace.NUMBER[1])
        pace_end = pace.MARGIN + name.getlength("5時間") + pace.PACE_GAP + font(pace.PACE_SIZE, 3).getlength("経過 100%")
        number_start = SIZE[0] - pace.MARGIN - unit.getlength("%") - pace.UNIT_GAP - number.getlength("100")
        self.assertLess(pace_end + 40, number_start)
        line = font(pace.LINE[1], 6)
        reset_end = pace.MARGIN + line.getlength("リセット 12/31(木) 23:59")
        remain_start = SIZE[0] - pace.MARGIN - line.getlength("あと6日23時間")  # 残り時間もリセットと同じ字
        self.assertLess(reset_end + 40, remain_start)

    def test_unit_is_smaller_than_half_of_the_number(self):
        # 2026-11-03、「% はもう少し小さく」（ユーザーの指示。数字 140 に対して 70 → 50）
        self.assertLess(pace.UNIT, pace.NUMBER[1] / 2)

    def test_scales_to_the_small_screen(self):
        self.assertEqual(pace.render(snapshot(), NOW, size=(480, 320)).size, (480, 320))
