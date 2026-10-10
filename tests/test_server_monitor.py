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


def status(values=(23, 61, 47, 3), age=timedelta(minutes=1), incidents=(), state_age=timedelta(seconds=30), cfg=None):
    cfg = cfg or config()
    metrics = tuple(sm.MetricValue(spec, value, None if value is None else NOW - age)
                    for spec, value in zip(cfg.metrics, values))
    return sm.ServerStatus(metrics, sm.MonitorState(tuple(incidents), NOW - state_age), NOW)


class ConfigTest(unittest.TestCase):
    def test_example_is_valid(self):
        cfg = sm.load_config(str(EXAMPLE))
        self.assertEqual([m.label for m in cfg.metrics], ["CPU", "メモリ", "ディスク", "スワップ"])
        self.assertEqual(cfg.metrics[0].dimensions, (("cpu", "cpu-total"),))
        self.assertEqual(cfg.metrics[0].threshold, 80)
        self.assertEqual(cfg.state_stale, timedelta(seconds=300))
        self.assertEqual(cfg.display_name(sm.Incident("http", "top", "", None)), "トップ")
        self.assertEqual(cfg.display_name(sm.Incident("tls", "example.com", "", None)), "証明書 example.com")

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
        self.assertEqual(result.alerts, ("メモリの値が届いていません", "CPU 92%（しきい値 80%）"))
        self.assertEqual(result.alerting_metrics, {"CPU", "メモリ"})
        self.assertTrue(sm.assess(status(age=timedelta(minutes=6)), config(), NOW).red)

    def test_site_turns_red_but_jobs_only_warn(self):
        incidents = (sm.Incident("job", "nightly-backup", "直近の実行が失敗", None),
                     sm.Incident("ledger", "ledger", "違う", None),
                     sm.Incident("http", "top", "HTTP 503（期待 200）", None))
        result = sm.assess(status(values=(92, 61, 47, 3), incidents=incidents), config(), NOW)
        self.assertEqual(result.alerts, ("トップ HTTP 503（期待 200）", "CPU 92%（しきい値 80%）"))
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
            "Datapoints": [{"Timestamp": NOW - timedelta(minutes=1), "Average": 11.0}]}
        s3 = mock.Mock()
        s3.get_object.return_value = {"Body": io.BytesIO(b'{"http:top": {"alerting": true, "reason": "x"}}'),
                                      "LastModified": NOW - timedelta(seconds=20)}
        result = self.fetch_with(cloudwatch, s3)
        self.assertEqual([m.value for m in result.metrics], [11.0] * 4)
        self.assertEqual(result.monitor.incidents[0].name, "top")
        first = cloudwatch.get_metric_statistics.call_args_list[0].kwargs
        self.assertEqual((first["MetricName"], first["Dimensions"], first["Period"]),
                         ("cpu_usage_active", [{"Name": "cpu", "Value": "cpu-total"}], 60))

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
