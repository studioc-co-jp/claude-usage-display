import subprocess
import unittest

from claude_usage_display import presence

# ioreg -c IOHIDSystem -d 4 の出力のうち、使う行の形（値は作ったもの）
IOREG_TEXT = """+-o Root  <class IORegistryEntry>
  +-o IOHIDSystem  <class IOHIDSystem>
    | |   "HIDIdleTime" = 43066081208
"""


class IdleTest(unittest.TestCase):
    def test_reads_nanoseconds_as_seconds(self):
        self.assertAlmostEqual(presence.parse_idle_seconds(IOREG_TEXT), 43.066081208)
        self.assertIsNone(presence.parse_idle_seconds("+-o Root"))

    def test_runs_ioreg_and_gives_up_quietly(self):
        calls = []

        def run(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, IOREG_TEXT, "")

        self.assertAlmostEqual(presence.idle_seconds(run), 43.066081208)
        self.assertEqual(calls, [presence.IOREG])

        def broken(args, **kwargs):
            raise OSError("ioreg がありません")

        self.assertIsNone(presence.idle_seconds(broken))


class PresenceTest(unittest.TestCase):
    def test_away_after_the_given_minutes(self):
        idle = [599.0, 600.0]
        detector = presence.Presence(10, read=lambda: idle.pop(0))
        self.assertEqual([detector.away(), detector.away()], [False, True])

    def test_zero_minutes_never_reads(self):
        detector = presence.Presence(0, read=lambda: self.fail("読まない"))
        self.assertFalse(detector.enabled)
        self.assertFalse(detector.away())

    def test_unreadable_idle_keeps_the_display_on_and_is_logged_once(self):
        detector = presence.Presence(10, read=lambda: None)
        with self.assertLogs(presence.log, "WARNING") as logs:
            self.assertFalse(detector.away())
            self.assertFalse(detector.away())
        self.assertEqual(len(logs.records), 1)


if __name__ == "__main__":
    unittest.main()
