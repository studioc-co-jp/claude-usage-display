import unittest
from datetime import timedelta

from claude_usage_display import monitor_screen as ms
from claude_usage_display import server_monitor as sm
from claude_usage_display.gauge import BACKGROUND, ORANGE, RED
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
        self.assertTrue(near(image.getpixel((20 + 52 + 48 - 5, 44 + 68)), (255, 255, 255)))
        self.assertFalse(near(image.getpixel((250 + 52 + 48 - 5, 44 + 68)), (255, 255, 255)))

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


if __name__ == "__main__":
    unittest.main()
