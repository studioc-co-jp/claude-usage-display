import unittest
from datetime import datetime, timedelta, timezone

from claude_usage_display import local_monitor as lm

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=timezone.utc)  # JST 18:00
GIB = 2 ** 30


def sample(**overrides):
    values = dict(cpu=29.3, performance=13.2, efficiency=40.4, memory=44, memory_total=32 * GIB, pressure=1, swap=0,
                  disk=(494_384_795_648, 167_220_789_603), ssd=(4_000_109_887_488, 2_392_104_269_419), thermal=0,
                  smart="Verified", last_backup=datetime(2026, 10, 14, 23, 33, tzinfo=timezone.utc))  # JST 8:33
    values.update(overrides)
    return lm.Sample(**values)


class TextTest(unittest.TestCase):
    def test_capacity_has_no_spaces_around_the_slash(self):
        # 空白を入れると、左の列の「327 / 494 GB」が区切り線を越える（2026-10-15）
        self.assertEqual(lm.capacity_text(494_384_795_648, 167_220_789_603), "327/494 GB")
        self.assertEqual(lm.capacity_text(4_000_109_887_488, 2_392_104_269_419), "1.6/4.0 TB")

    def test_backup_line(self):
        today = datetime(2026, 10, 14, 23, 33, tzinfo=timezone.utc)      # JST 10/15 8:33
        yesterday = datetime(2026, 10, 14, 0, 19, tzinfo=timezone.utc)   # JST 10/14 9:19（32 時間 41 分前）
        stale = datetime(2026, 10, 12, 23, 33, tzinfo=timezone.utc)      # JST 10/13 8:33（2 日前）
        cases = ((today, False, None, ("バックアップ 8:33", None)),
                 (yesterday, False, None, ("バックアップ 10/14 9:19", None)),
                 (stale, False, None, (None, "バックアップ 10/13（2 日前）")),
                 (stale, True, 0.42, ("バックアップ中 42%", None)),
                 (stale, True, None, ("バックアップ中", None)),
                 (None, False, None, (None, "バックアップの時刻を読めません")))
        for last, running, percent, expected in cases:
            with self.subTest(last=last, running=running):
                self.assertEqual(lm.backup_line(last, running, percent, NOW), expected)


class BuildTest(unittest.TestCase):
    def test_four_rings_with_amounts(self):
        reading = lm.build(sample(), NOW)
        metrics = reading.status.metrics
        self.assertEqual([m.spec.label for m in metrics], ["CPU", "メモリ", "ディスク", "SSD"])
        self.assertEqual([m.spec.threshold for m in metrics], [80, 85, 90, 90])
        self.assertEqual([m.detail for m in metrics],
                         [("性能 13%", "効率 40%"), ("14.1/32 GB",), ("327/494 GB",), ("1.6/4.0 TB",)])
        self.assertAlmostEqual(metrics[2].value, 66.18, places=2)
        self.assertIsNone(reading.status.monitor)
        self.assertEqual((reading.note, reading.warnings), ("バックアップ 8:33", ()))

    def test_memory_color_follows_the_pressure_level_not_the_percentage(self):
        # macOS の逼迫の判定は割合を使わない（xnu vm_pageout.c）。割合が低くても、段階が上がれば色を変える
        for pressure, tint in ((1, "normal"), (2, "warning"), (4, "critical")):
            with self.subTest(pressure=pressure):
                self.assertEqual(lm.build(sample(memory=30, pressure=pressure), NOW).status.metrics[1].tint, tint)
        self.assertEqual(lm.build(sample(memory=95, pressure=1), NOW).status.metrics[1].tint, "normal")
        self.assertIsNone(lm.build(sample(), NOW).status.metrics[0].tint)  # CPU はしきい値で決める

    def test_missing_volumes_and_cpu_kinds(self):
        reading = lm.build(sample(disk=None, ssd=None, performance=None, efficiency=None), NOW)
        cpu, _, disk, ssd = reading.status.metrics
        self.assertEqual(cpu.detail, ())
        self.assertEqual((disk.value, disk.detail), (None, ("読めません",)))
        self.assertEqual((ssd.value, ssd.detail), (None, ("未接続",)))

    def test_warnings_in_order(self):
        reading = lm.build(sample(pressure=4, swap=round(4.2 * GIB), thermal=2, smart="Failing",
                                  last_backup=datetime(2026, 10, 12, 23, 33, tzinfo=timezone.utc)), NOW)
        self.assertEqual(reading.warnings, ("メモリ危険　スワップ 4.2 GB", "熱で性能を制限しています",
                                            "内蔵 SSD の SMART: Failing", "バックアップ 10/13（2 日前）"))
        self.assertIsNone(reading.note)
        self.assertEqual(lm.build(sample(pressure=2, swap=0), NOW).warnings, ("メモリ逼迫　スワップ 0.0 GB",))
        self.assertEqual(lm.build(sample(thermal=1), NOW).warnings, ())  # Moderate はまだ出さない
        self.assertEqual(lm.build(sample(smart=None, thermal=None), NOW).warnings, ())  # 読めないときは出さない

    def test_demo_samples(self):
        self.assertEqual(lm.build(lm.demo_sample("normal", NOW), NOW).warnings, ())
        warning = lm.build(lm.demo_sample("warning", NOW), NOW)
        self.assertEqual(warning.warnings, ("メモリ逼迫　スワップ 4.2 GB",))
        self.assertEqual(warning.status.metrics[1].tint, "warning")


class CpuTest(unittest.TestCase):
    def test_usage_is_split_by_core_kind(self):
        before = [(0, 0, 0, 0)] * 4
        # E の 2 つは 50%、P の 2 つは 100% と 0%
        after = [(30, 20, 50, 0), (40, 10, 50, 0), (90, 10, 0, 0), (0, 0, 100, 0)]
        self.assertEqual(lm.cpu_usage(before, after, ["E", "E", "P", "P"]), (50.0, 50.0, 50.0))
        after = [(30, 20, 50, 0), (40, 10, 50, 0), (90, 10, 0, 0), (90, 10, 0, 0)]
        self.assertEqual(lm.cpu_usage(before, after, ["E", "E", "P", "P"]), (75.0, 100.0, 50.0))
        self.assertEqual(lm.cpu_usage(before, after, None), (75.0, None, None))
        self.assertEqual(lm.cpu_usage(before, after, ["E", "P"]), (75.0, None, None))  # 数が合わなければ分けない

    def test_counter_wraparound(self):
        before = [(2 ** 32 - 10, 0, 2 ** 32 - 10, 0)]
        after = [(10, 0, 10, 0)]
        self.assertEqual(lm.cpu_usage(before, after, None), (50.0, None, None))

    def test_reads_this_mac(self):
        reader_host = lm._libc.mach_host_self()
        ticks = lm.cpu_ticks(reader_host)
        self.assertGreater(len(ticks), 0)
        self.assertTrue(all(len(t) == 4 for t in ticks))


class ParseTest(unittest.TestCase):
    def test_cpu_kinds(self):
        text = "\n".join(f'  +-o cpu{i}@{i}  <class IOPlatformDevice>\n  |     "cluster-type" = <"{k}">'
                         for i, k in enumerate("EEEEEEPPPP"))
        self.assertEqual(lm.parse_cpu_kinds(text), list("EEEEEEPPPP"))
        self.assertIsNone(lm.parse_cpu_kinds(""))
        self.assertIsNone(lm.parse_cpu_kinds('  +-o cpu1@1\n  "cluster-type" = <"E">'))  # cpu0 が無い

    def test_backup_destination_and_snapshots(self):
        # 2026-10-16 に launchd から実行した tmutil destinationinfo と diskutil apfs listSnapshots の形
        info = ("====================================================\nName          : backup\nKind          : Local\n"
                "Mount Point   : /Volumes/backup\nID            : A5588DE8-A588-4031-AFE9-AAC834E9AE46\n")
        self.assertEqual(lm.parse_destination_mounts(info), ["/Volumes/backup"])
        self.assertEqual(lm.parse_destination_mounts("Name : backup\nKind : Local\n"), [])  # 外れているとき
        snapshots = ("|   Name:        com.apple.TimeMachine.2026-10-14-091707.backup\n"
                     "|   Name:        com.apple.TimeMachine.2026-10-15-083315.backup\n"
                     "    Name:        com.apple.TimeMachine.2026-10-16-062646.backup\n")
        self.assertEqual(lm.parse_backup_snapshots(snapshots), datetime(2026, 10, 16, 6, 26, 46).astimezone(timezone.utc))
        self.assertIsNone(lm.parse_backup_snapshots("No snapshots for disk5s1\n"))

    def test_volumes(self):
        total, free = lm.volume("/")
        self.assertGreater(total, free)
        self.assertGreater(free, 0)
        self.assertIsNone(lm.volume("/Volumes/claude-usage-display-no-such-volume"))


if __name__ == "__main__":
    unittest.main()
