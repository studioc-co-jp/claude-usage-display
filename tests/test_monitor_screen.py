import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from PIL import Image

from claude_usage_display import monitor_screen as ms
from claude_usage_display import server_monitor as sm
from claude_usage_display.gauge import BACKGROUND, ICON_GAP, ICON_SIZE, ORANGE, RED
from claude_usage_display.render import SMALL_WEIGHT, font
from tests.test_server_monitor import NOW, config, status


def near(pixel, color, tolerance=12):
    return all(abs(a - b) <= tolerance for a, b in zip(pixel, color))


class MonitorScreenTest(unittest.TestCase):
    def render(self, st, error=None):
        cfg = config()
        return ms.render(st, sm.assess(st, cfg, NOW) if st else None, cfg, error)

    def test_normal_is_black(self):
        image = self.render(status())
        self.assertEqual(image.size, (480, 320))
        self.assertEqual(image.getpixel((2, 300)), BACKGROUND)

    def test_alert_turns_the_whole_screen_red_and_the_alerting_ring_white(self):
        image = self.render(status(values=(92, 61, 47, 3)))
        self.assertEqual(image.getpixel((2, 300)), RED)
        # CPU（左上）のリングの 3 時の位置は白、メモリ（右上）は薄い色
        cx, cy, radius, width = ms.LANDSCAPE.ring
        self.assertTrue(near(image.getpixel((round(20 + cx + radius - width / 2), 44 + cy)), (255, 255, 255)))
        self.assertFalse(near(image.getpixel((round(250 + cx + radius - width / 2), 44 + cy)), (255, 255, 255)))

    def test_landscape_puts_the_number_inside_the_ring(self):
        # 2026-10-15 に、数字をリングの右からリングの中へ移した。リングの内側に数字の白があり、右には無い
        image = self.render(status(values=(11, 61, 47, 3)))
        cx, cy, radius, width = ms.LANDSCAPE.ring
        inside = [image.getpixel((20 + x, 44 + y)) for x in range(round(cx - 20), round(cx + 20))
                  for y in range(round(cy - 15), round(cy + 15))]
        self.assertTrue(any(near(p, (255, 255, 255), 40) for p in inside))
        label_x, label_y, _, _ = ms.LANDSCAPE.label
        _, threshold_y, _, threshold_size = ms.LANDSCAPE.threshold
        right = [image.getpixel((20 + x, 44 + y)) for x in range(label_x, 220)
                 for y in range(round(label_y + 2), round(threshold_y - threshold_size))]
        self.assertTrue(all(p == BACKGROUND for p in right))

    def test_landscape_stamp_stays_right_of_the_pill(self):
        # 2026-10-15 に時刻を 13→16 ピクセルにした。帯（アラートの白い地）に時刻がかからない
        start = 480 - ms.LANDSCAPE.inset - font(ms.LANDSCAPE.stamp_size, SMALL_WEIGHT).getlength("00:00 更新")
        self.assertGreater(start, ms.LANDSCAPE.pill[2])

    def test_landscape_threshold_stays_left_of_the_divider(self):
        threshold_x, _, _, threshold_size = ms.LANDSCAPE.threshold
        end = ms.LANDSCAPE.cells[0][0] + threshold_x + font(threshold_size, SMALL_WEIGHT).getlength("しきい値 85%")
        self.assertLess(end, ms.LANDSCAPE.dividers[0][0])

    def test_job_incidents_show_an_orange_dot_on_black(self):
        incidents = (sm.Incident("job", "nightly-backup", "直近の実行が失敗", None),)
        image = self.render(status(incidents=incidents))
        self.assertEqual(image.getpixel((2, 300)), BACKGROUND)
        header = [image.getpixel((x, 20)) for x in range(116, 364)]
        self.assertTrue(any(near(p, ORANGE) for p in header))

    def test_missing_status_and_fetch_errors_still_render(self):
        self.assertEqual(self.render(None, "通信できません").size, (480, 320))
        self.assertEqual(self.render(status(values=(None, 61, 47, 3)), "通信できません").getpixel((2, 300)), RED)
        stale = status(age=timedelta(minutes=10))
        self.assertEqual(self.render(stale).getpixel((2, 300)), RED)

    def test_portrait(self):
        cfg = config()
        normal, alert = status(), status(values=(92, 61, 47, 3))
        image = ms.render(normal, sm.assess(normal, cfg, NOW), cfg, portrait=True)
        self.assertEqual((image.size, image.getpixel((2, 470))), ((320, 480), BACKGROUND))
        image = ms.render(alert, sm.assess(alert, cfg, NOW), cfg, portrait=True)
        self.assertEqual(image.getpixel((2, 470)), RED)
        # CPU（左上の区画）のリングの 3 時の位置は白、メモリ（右上）は薄い色
        cx, cy, radius, width = ms.PORTRAIT.ring
        self.assertTrue(near(image.getpixel((round(cx + radius - width / 2), 80 + cy)), (255, 255, 255)))
        self.assertFalse(near(image.getpixel((round(160 + cx + radius - width / 2), 80 + cy)), (255, 255, 255)))

    def test_portrait_splits_two_or_more_alerts_into_two_lines(self):
        cfg = config()
        below_one_line = (40, ms.PORTRAIT.pill[3] + 8)  # 1 行の帯の下、2 行の帯の中
        one = status(values=(92, 61, 47, 3))
        self.assertEqual(len(sm.assess(one, cfg, NOW).alerts), 1)
        image = ms.render(one, sm.assess(one, cfg, NOW), cfg, portrait=True)
        self.assertEqual(image.getpixel(below_one_line), RED)
        two = status(values=(92, 90, 47, 3))
        self.assertEqual(len(sm.assess(two, cfg, NOW).alerts), 2)
        image = ms.render(two, sm.assess(two, cfg, NOW), cfg, portrait=True)
        self.assertEqual(image.getpixel(below_one_line), (255, 255, 255))


class LocalScreenTest(unittest.TestCase):
    """この Mac の状態の画面（local）が使う、下の行の量・色の決め打ち・見出しの文言（2026-10-15）。"""

    def render(self, **overrides):
        from claude_usage_display import local_monitor as lm
        from tests.test_local_monitor import NOW as LOCAL_NOW
        from tests.test_local_monitor import sample

        reading = lm.build(sample(**overrides), LOCAL_NOW)
        cfg = sm.MonitorConfig(title="Mac mini", region="-", keychain_service="-", metrics=lm.SPECS)
        return ms.render(reading.status, sm.Assessment((), reading.warnings, frozenset()), cfg, note=reading.note)

    def test_cpu_has_a_second_line_below_the_first(self):
        image = self.render()
        x, y = ms.LANDSCAPE.cells[0]
        threshold_x, threshold_y, _, size = ms.LANDSCAPE.threshold
        second = [image.getpixel((x + threshold_x + dx, y + threshold_y + ms.DETAIL_LINE - dy))
                  for dx in range(0, 60) for dy in range(1, size)]
        self.assertTrue(any(p != BACKGROUND for p in second))
        # メモリは 1 行だけ（2 行目の位置は空いている）
        x, y = ms.LANDSCAPE.cells[1]
        second = [image.getpixel((x + threshold_x + dx, y + threshold_y + ms.DETAIL_LINE - dy))
                  for dx in range(0, 60) for dy in range(1, size)]
        self.assertTrue(all(p == BACKGROUND for p in second))

    def test_memory_ring_follows_the_pressure_level(self):
        cx, cy, radius, width = ms.LANDSCAPE.ring
        x, y = ms.LANDSCAPE.cells[1]
        at_twelve = (round(x + cx), round(y + cy - radius + width / 2))  # 弧の始まり（12 時）
        self.assertTrue(near(self.render(memory=30, pressure=2).getpixel(at_twelve), ORANGE))
        self.assertTrue(near(self.render(memory=30, pressure=4).getpixel(at_twelve), RED))
        self.assertFalse(near(self.render(memory=95, pressure=1).getpixel(at_twelve), ORANGE))

    def test_note_is_shown_with_a_green_dot_and_warnings_replace_it(self):
        header = lambda image: [image.getpixel((px, round(ms.LANDSCAPE.dot_y))) for px in range(116, 364)]
        self.assertTrue(any(near(p, ms.GREEN) for p in header(self.render())))
        warned = header(self.render(pressure=2, swap_rate=1 << 20))
        self.assertTrue(any(near(p, ORANGE) for p in warned))
        self.assertFalse(any(near(p, ms.GREEN) for p in warned))
        # 段階 2 だけ（スワップの読み書きが無い）なら、見出しは緑のまま。リングの色は別に黄色になる
        quiet = header(self.render(pressure=2, swap_rate=0.0))
        self.assertTrue(any(near(p, ms.GREEN) for p in quiet))


class HeaderTest(unittest.TestCase):
    def test_logo_sits_left_of_the_title_on_black_and_red(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            Image.new("RGBA", (40, 40), (0, 255, 0, 255)).save(f, format="PNG")
        self.addCleanup(Path(f.name).unlink)
        cfg = sm.MonitorConfig(**{**sm.load_config(str(Path(sm.__file__).parents[1] / "monitor.example.toml")).__dict__,
                                  "logo": f.name})
        for portrait in (False, True):
            layout = ms.PORTRAIT if portrait else ms.LANDSCAPE
            for st in (status(), status(values=(92, 61, 47, 3))):
                with self.subTest(portrait=portrait, red=st.metrics[0].value > 80):
                    image = ms.render(st, sm.assess(st, cfg, NOW), cfg, portrait=portrait)
                    center = (layout.inset + ICON_SIZE // 2, round(layout.title_baseline - ms.LOGO_RISE))
                    self.assertTrue(near(image.getpixel(center), (0, 255, 0)))
                    # 名前は、ロゴの枠と間の分だけ右から始まる
                    left = layout.inset + ICON_SIZE + ICON_GAP
                    row = range(layout.title_baseline - 12, layout.title_baseline)
                    background = image.getpixel((left - 2, layout.title_baseline - 6))
                    ink = [x for x in range(left - ICON_GAP + 1, left + 6)
                           if any(image.getpixel((x, y)) != background for y in row)]
                    self.assertTrue(ink and ink[0] >= left - 1, ink)

    def test_landscape_pill_moves_right_of_a_long_title(self):
        # 帯の左端（116）にかかる名前。直す前は、末尾が白い帯に隠れていた
        cfg = config(title="example.com")
        st = status(values=(92, 61, 47, 3))
        image = ms.render(st, sm.assess(st, cfg, NOW), cfg)
        end = ms.LANDSCAPE.inset + font(15, 6).getlength("example.com")
        self.assertGreater(end, ms.LANDSCAPE.pill[0])
        middle = (ms.LANDSCAPE.pill[1] + ms.LANDSCAPE.pill[3]) // 2
        gap = [image.getpixel((x, middle)) for x in range(round(end) + 2, round(end) + ms.TITLE_GAP - 1)]
        self.assertTrue(all(near(p, RED) for p in gap), gap)


class HiddenTitleTest(unittest.TestCase):
    """異常の文言を大きく出す設定（large_alerts = true）。異常のあるときだけ、見出しの名前を出さず、行いっぱいに出す。"""

    WIDTH = 296

    def test_short_text_stays_on_one_line_at_the_big_size(self):
        lines, f = ms._big_lines("監視の障害 1 件", self.WIDTH, SMALL_WEIGHT)
        self.assertEqual(lines, ["監視の障害 1 件"])
        self.assertEqual(f.size, ms.BIG_SIZE)

    def test_name_and_reason_are_split_on_two_lines(self):
        lines, f = ms._big_lines("example job: 直近の実行が失敗", self.WIDTH, SMALL_WEIGHT)
        self.assertEqual(lines, ["example job", "直近の実行が失敗"])
        self.assertLessEqual(f.size, ms.BIG_SMALL)

    def test_more_alerts_are_split_before_the_count_of_others(self):
        lines, f = ms._big_lines("トップ HTTP 503（期待 200）　ほか 1 件", self.WIDTH, 6)
        self.assertEqual(lines, ["トップ HTTP 503（期待 200）", "ほか 1 件"])
        self.assertTrue(all(f.getlength(line) <= self.WIDTH for line in lines))

    def test_job_count_is_split_before_the_bracket(self):
        lines, _ = ms._big_lines("ジョブ障害 2 件（nightly-backup ほか）", self.WIDTH, SMALL_WEIGHT)
        self.assertEqual(lines, ["ジョブ障害 2 件", "nightly-backup ほか"])

    def test_text_that_cannot_be_split_is_cut_with_an_ellipsis(self):
        lines, f = ms._big_lines("あ" * 60, self.WIDTH, SMALL_WEIGHT)
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[1].endswith("…"))
        self.assertTrue(all(f.getlength(line) <= self.WIDTH for line in lines))
        self.assertEqual(f.size, ms.BIG_MIN)

    def test_title_is_hidden_only_while_there_is_an_alert(self):
        normal, red = status(), status(values=(92, 61, 47, 3))
        incidents = (sm.Incident("job", "nightly-backup", "直近の実行が失敗", None),)
        warned = status(incidents=incidents)
        shown, large = config(title="example.com"), config(title="example.com", large_alerts=True)
        left = ms.LANDSCAPE.inset

        def title_ink(cfg, st):  # 名前があった位置（ロゴの無い設定なので左端）に、黒（または赤）以外の画素があるか
            image = ms.render(st, sm.assess(st, cfg, NOW), cfg)
            ground = image.getpixel((2, 300))
            return any(not near(image.getpixel((x, 20)), ground) for x in range(left, left + 60))

        # 異常が無いときは、設定があっても名前を出す
        self.assertTrue(title_ink(large, normal))
        # 異常のあるときだけ、名前を出さない（設定が無ければ出したまま）
        self.assertFalse(title_ink(large, warned))
        self.assertTrue(title_ink(shown, warned))
        # 赤の画面は、白い帯が名前の位置まで広がる（設定が無ければ、名前の右から始まる）
        wide = ms.render(red, sm.assess(red, large, NOW), large)
        narrow = ms.render(red, sm.assess(red, shown, NOW), shown)
        self.assertTrue(near(wide.getpixel((left + 30, 8)), (255, 255, 255)))
        self.assertFalse(near(narrow.getpixel((left + 30, 8)), (255, 255, 255)))

    def test_warning_is_drawn_larger_on_two_lines(self):
        incidents = (sm.Incident("job", "nightly-backup", "直近の実行が失敗", None),)
        st = status(incidents=incidents)
        large = config(title="example.com", large_alerts=True)
        image = ms.render(st, sm.assess(st, large, NOW), large)
        # 異常の文言（オレンジ）は、見出しの高さの外（35 ピクセルより下）にも、2 行目として出る
        rows = [y for y in range(0, 56) if any(near(image.getpixel((x, y)), ORANGE, 40) for x in range(120, 360))]
        self.assertGreater(max(rows) - min(rows), 30)

    def test_default_is_off(self):
        self.assertFalse(config().large_alerts)
        self.assertTrue(config(large_alerts=True).large_alerts)

    def test_portrait_ignores_the_setting(self):
        st = status(values=(92, 61, 47, 3))
        hidden = config(title="example.com", large_alerts=True)
        shown = config(title="example.com")
        a = ms.render(st, sm.assess(st, hidden, NOW), hidden, portrait=True)
        b = ms.render(st, sm.assess(st, shown, NOW), shown, portrait=True)
        self.assertEqual(a.tobytes(), b.tobytes())


if __name__ == "__main__":
    unittest.main()
