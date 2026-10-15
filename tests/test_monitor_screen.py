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


if __name__ == "__main__":
    unittest.main()
