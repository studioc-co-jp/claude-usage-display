import io
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from claude_usage_display import server_monitor as sm

NOW = datetime(2026, 10, 10, 3, 0, tzinfo=timezone.utc)  # JST 12:00
EXAMPLE = Path(__file__).resolve().parent.parent / "monitor.example.toml"


def config(**overrides):
    base = sm.load_config(str(EXAMPLE))
    return sm.MonitorConfig(**{**base.__dict__, **overrides})


def status(values=(23, 61, 47, 3), age=timedelta(minutes=1), incidents=(), state_age=timedelta(seconds=30), cfg=None,
           streaks=None):
    """``streaks`` を省くと、しきい値以上の値は datapoints 回続いている（アラームの条件を満たす）ものとして作る。"""
    cfg = cfg or config()
    if streaks is None:
        streaks = [spec.datapoints if value is not None and value >= spec.threshold else 0
                   for spec, value in zip(cfg.metrics, values)]
    metrics = tuple(sm.MetricValue(spec, value, None if value is None else NOW - age, streak)
                    for spec, value, streak in zip(cfg.metrics, values, streaks))
    return sm.ServerStatus(metrics, sm.MonitorState(tuple(incidents), NOW - state_age), NOW)


class ConfigTest(unittest.TestCase):
    def test_example_is_valid(self):
        cfg = sm.load_config(str(EXAMPLE))
        self.assertEqual([m.label for m in cfg.metrics], ["CPU", "メモリ", "ディスク", "スワップ"])
        self.assertEqual(cfg.metrics[0].dimensions, (("cpu", "cpu-total"),))
        self.assertEqual(cfg.metrics[0].threshold, 80)
        # アラームと同じ条件: CPU・メモリは 1 分×5、ディスクは 1 回、スワップは 5 分×3
        self.assertEqual([(m.period, m.datapoints) for m in cfg.metrics], [(60, 5), (60, 5), (60, 1), (300, 3)])
        self.assertEqual(cfg.state_stale, timedelta(seconds=300))
        self.assertEqual(cfg.display_name(sm.Incident("http", "top", "", None)), "トップ")
        self.assertEqual(cfg.display_name(sm.Incident("tls", "example.com", "", None)), "証明書 example.com")

    def test_period_and_datapoints_are_checked(self):
        text = EXAMPLE.read_text()
        for bad in ("period = 90", "period = 30", "datapoints = 0"):
            broken = text.replace("period = 60\ndatapoints = 5   # 5 分続いたら", bad, 1)
            self.assertNotEqual(broken, text)
            with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
                f.write(broken)
            self.addCleanup(Path(f.name).unlink)
            with self.subTest(bad=bad), self.assertRaises(sm.ConfigError):
                sm.load_config(f.name)

    def test_needs_four_metrics_and_an_existing_file(self):
        text = EXAMPLE.read_text()
        three = text[:text.rindex("[[metrics]]")]
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write(three)
        self.addCleanup(Path(f.name).unlink)
        with self.assertRaises(sm.ConfigError):
            sm.load_config(f.name)
        with self.assertRaises(sm.ConfigError):
            sm.load_config("/nonexistent/monitor.toml")


class ParseTest(unittest.TestCase):
    def test_latest_datapoint(self):
        points = [{"Timestamp": NOW - timedelta(minutes=3), "Average": 10.0},
                  {"Timestamp": NOW - timedelta(minutes=1), "Average": 12.5}]
        self.assertEqual(sm.latest(points), (12.5, NOW - timedelta(minutes=1)))
        self.assertEqual(sm.latest([]), (None, None))

    def test_over_streak_counts_only_the_latest_unbroken_run(self):
        def points(*pairs):
            return [{"Timestamp": NOW - timedelta(minutes=m), "Average": v} for m, v in pairs]

        self.assertEqual(sm.over_streak(points((1, 85), (2, 90), (3, 81), (4, 70), (5, 95)), 80, 60), 3)
        self.assertEqual(sm.over_streak(points((1, 79), (2, 90)), 80, 60), 0)       # いちばん新しい値が下回る
        self.assertEqual(sm.over_streak(points((1, 90), (3, 90), (4, 90)), 80, 60), 1)  # 間が空いたら続いていない
        self.assertEqual(sm.over_streak(points((5, 95), (10, 95), (15, 95)), 90, 300), 3)
        self.assertEqual(sm.over_streak([], 80, 60), 0)

    def test_state_keeps_only_alerting_entries(self):
        since = (NOW - timedelta(hours=1)).timestamp()
        document = {"_meta": {"started": 1}, "http:top": {"alerting": True, "reason": "HTTP 503", "since": since},
                    "http:login": {"alerting": False, "fails": 1}, "ledger": {"alerting": True, "reason": "違う"}}
        state = sm.parse_state(document, NOW)
        self.assertEqual([(i.kind, i.name) for i in state.incidents], [("http", "top"), ("ledger", "ledger")])
        self.assertEqual(state.incidents[0].since, NOW - timedelta(hours=1))


class AssessTest(unittest.TestCase):
    def test_normal(self):
        result = sm.assess(status(), config(), NOW)
        self.assertFalse(result.red)
        self.assertEqual(result.warnings, ())

    def test_threshold_and_missing_values_turn_red(self):
        result = sm.assess(status(values=(92, None, 47, 3)), config(), NOW)
        self.assertEqual(result.alerts, ("メモリの値が届いていません", "CPU 92%（80% 以上が 5 分）"))
        self.assertEqual(result.alerting_metrics, {"CPU", "メモリ"})
        self.assertTrue(sm.assess(status(age=timedelta(minutes=6)), config(), NOW).red)

    def test_a_short_spike_does_not_turn_the_screen_red(self):
        # CPU 92% が 4 分続いただけ（アラームは 5 分）。画面は赤にしないが、リングはしきい値以上の色
        result = sm.assess(status(values=(92, 61, 47, 3), streaks=(4, 0, 0, 0)), config(), NOW)
        self.assertFalse(result.red)
        self.assertEqual(sm.warning_tint(92, 80), "critical")
        self.assertTrue(sm.assess(status(values=(92, 61, 47, 3), streaks=(5, 0, 0, 0)), config(), NOW).red)

    def test_a_single_datapoint_is_enough_where_the_alarm_needs_one(self):
        # ディスクは datapoints 1。スワップは 5 分の平均が 3 回で、2 回では赤にしない
        result = sm.assess(status(values=(23, 61, 91, 95), streaks=(0, 0, 1, 2)), config(), NOW)
        self.assertEqual(result.alerts, ("ディスク 91%（しきい値 90%）",))
        self.assertIn("スワップ 95%（90% 以上が 15 分）",
                      sm.assess(status(values=(23, 61, 47, 95), streaks=(0, 0, 0, 3)), config(), NOW).alerts)

    def test_a_long_period_is_not_stale_after_five_minutes(self):
        # スワップは 5 分ごとの平均なので、いちばん新しい点が 6 分前でも届いている
        cfg = config()
        metrics = tuple(sm.MetricValue(spec, 3.0, NOW - (timedelta(minutes=6) if spec.period == 300 else timedelta(minutes=1)), 0)
                        for spec in cfg.metrics)
        self.assertFalse(sm.assess(sm.ServerStatus(metrics, None, NOW), cfg, NOW).red)

    def test_site_turns_red_but_jobs_only_warn(self):
        incidents = (sm.Incident("job", "nightly-backup", "直近の実行が失敗", None),
                     sm.Incident("ledger", "ledger", "違う", None),
                     sm.Incident("http", "top", "HTTP 503（期待 200）", None))
        result = sm.assess(status(values=(92, 61, 47, 3), incidents=incidents), config(), NOW)
        self.assertEqual(result.alerts, ("トップ HTTP 503（期待 200）", "CPU 92%（80% 以上が 5 分）"))
        self.assertEqual(result.warnings, ("ジョブ障害 1 件・監視の障害 1 件",))

    def test_stopped_monitor_comes_first(self):
        result = sm.assess(status(values=(92, 61, 47, 3), state_age=timedelta(minutes=6)), config(), NOW)
        self.assertEqual(result.alerts[0], "監視が止まっています（11:54 から）")

    def test_tint(self):
        self.assertEqual([sm.warning_tint(v, 80) for v in (64, 65, 79, 80)], ["normal", "warning", "warning", "critical"])


class ReaderTest(unittest.TestCase):
    def test_credentials_come_from_keychain(self):
        attrs = mock.Mock(stdout='keychain: "x"\n    "acct"<blob>="AKIAEXAMPLE"\n')
        secret = mock.Mock(stdout="secret/value+1\n")
        with mock.patch.object(sm.subprocess, "run", side_effect=[attrs, secret]):
            self.assertEqual(sm.read_credentials("svc"), ("AKIAEXAMPLE", "secret/value+1"))
        with mock.patch.object(sm.subprocess, "run", side_effect=sm.subprocess.CalledProcessError(44, "security")):
            with self.assertRaises(sm.FetchError):
                sm.read_credentials("svc")

    def fetch_with(self, cloudwatch, s3):
        reader = sm.AwsReader(config(state_bucket="bucket", state_key="state/status.json"))
        with mock.patch.object(reader, "_connect", return_value=(cloudwatch, s3)):
            return reader.fetch(NOW)

    def test_fetch_reads_metrics_and_state(self):
        cloudwatch = mock.Mock()
        cloudwatch.get_metric_statistics.return_value = {
            "Datapoints": [{"Timestamp": NOW - timedelta(minutes=2), "Average": 95.0},
                           {"Timestamp": NOW - timedelta(minutes=1), "Average": 11.0}]}
        s3 = mock.Mock()
        s3.get_object.return_value = {"Body": io.BytesIO(b'{"http:top": {"alerting": true, "reason": "x"}}'),
                                      "LastModified": NOW - timedelta(seconds=20)}
        result = self.fetch_with(cloudwatch, s3)
        self.assertEqual([m.value for m in result.metrics], [11.0] * 4)
        self.assertEqual([m.streak for m in result.metrics], [0] * 4)  # いちばん新しい 11% で途切れる
        self.assertEqual(result.monitor.incidents[0].name, "top")
        calls = [c.kwargs for c in cloudwatch.get_metric_statistics.call_args_list]
        self.assertEqual((calls[0]["MetricName"], calls[0]["Dimensions"], calls[0]["Period"]),
                         ("cpu_usage_active", [{"Name": "cpu", "Value": "cpu-total"}], 60))
        # スワップは 5 分ごとの平均を、3 回続いたかが分かる範囲（5 分×5）で読む
        self.assertEqual((calls[3]["Period"], calls[3]["EndTime"] - calls[3]["StartTime"]), (300, timedelta(minutes=25)))
        self.assertEqual(calls[0]["EndTime"] - calls[0]["StartTime"], timedelta(minutes=10))

    def test_errors_are_short_messages(self):
        from botocore.exceptions import ClientError, EndpointConnectionError

        denied = ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "GetObject")
        for error, message in ((denied, "AWS の鍵か権限が合いません"),
                               (EndpointConnectionError(endpoint_url="https://x"), "通信できません")):
            cloudwatch = mock.Mock()
            cloudwatch.get_metric_statistics.side_effect = error
            with self.subTest(message=message), self.assertRaises(sm.FetchError) as raised:
                self.fetch_with(cloudwatch, mock.Mock())
            self.assertEqual(raised.exception.message, message)


if __name__ == "__main__":
    unittest.main()
