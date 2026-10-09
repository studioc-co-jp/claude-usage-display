import json
import unittest
from unittest import mock
from datetime import datetime, timezone
from pathlib import Path

from claude_usage_display import usage
from claude_usage_display.usage import parse_retry_after, parse_usage

FIXTURE = Path(__file__).parent / "fixtures" / "usage_response.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text())


class ParseUsageTest(unittest.TestCase):
    def test_three_meters_from_limits(self):
        session, weekly, fable = parse_usage(load_fixture())
        self.assertEqual((session.label, session.percent), ("5時間", 26.0))
        self.assertEqual((weekly.label, weekly.percent), ("週次", 3.0))
        self.assertEqual((fable.label, fable.percent), ("Fable週次", 0.0))
        self.assertEqual(session.resets_at, datetime(2026, 10, 5, 7, 29, 59, 962121, tzinfo=timezone.utc))
        self.assertEqual(fable.resets_at, datetime(2026, 10, 12, 1, 0, tzinfo=timezone.utc))

    def test_model_name_is_case_insensitive(self):
        *_, fable = parse_usage(load_fixture(), model="fable")
        self.assertEqual(fable.percent, 0.0)

    def test_unknown_model_has_no_value(self):
        *_, other = parse_usage(load_fixture(), model="Opus")
        self.assertEqual((other.label, other.percent, other.resets_at), ("Opus週次", None, None))

    def test_falls_back_to_legacy_windows_without_limits(self):
        body = load_fixture()
        del body["limits"]
        session, weekly, fable = parse_usage(body)
        self.assertEqual(session.percent, 26.0)
        self.assertEqual(weekly.percent, 3.0)
        self.assertIsNone(fable.percent)

    def test_limits_not_a_list_degrades_to_legacy_windows(self):
        body = load_fixture()
        body["limits"] = {"unexpected": "shape"}
        session, *_ = parse_usage(body)
        self.assertEqual(session.percent, 26.0)

    def test_active_entry_wins_among_duplicates(self):
        body = load_fixture()
        body["limits"] = [
            {"kind": "session", "percent": 10, "is_active": False},
            {"kind": "session", "percent": 55, "is_active": True},
        ]
        session, *_ = parse_usage(body)
        self.assertEqual(session.percent, 55.0)

    def test_boolean_is_not_a_percent(self):
        body = {"limits": [{"kind": "session", "percent": True}]}
        session, *_ = parse_usage(body)
        self.assertIsNone(session.percent)


class RetryAfterTest(unittest.TestCase):
    def test_seconds(self):
        self.assertEqual(parse_retry_after("120"), 120)

    def test_capped(self):
        self.assertEqual(parse_retry_after("999999"), 3600)

    def test_http_date(self):
        now = datetime(2026, 10, 5, 7, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(parse_retry_after("Mon, 05 Oct 2026 07:05:00 GMT", now), 300)

    def test_garbage(self):
        self.assertIsNone(parse_retry_after("soon"))
        self.assertIsNone(parse_retry_after(None))



class RateLimitTest(unittest.TestCase):
    def raise_429(self, headers):
        import email.message
        import urllib.error

        message = email.message.Message()
        for name, value in headers.items():
            message[name] = value
        error = urllib.error.HTTPError(usage.USAGE_URL, 429, "Too Many Requests", message, None)
        with mock.patch.object(usage.urllib.request, "urlopen", side_effect=error), \
                self.assertRaises(usage.UsageError) as raised:
            usage.fetch_raw("token-value")
        return raised.exception

    def test_429_keeps_retry_after_and_rate_limit_headers_for_the_log(self):
        error = self.raise_429({"Retry-After": "212", "anthropic-ratelimit-unified-status": "rejected",
                                "request-id": "req_123", "set-cookie": "secret"})
        self.assertTrue(error.rate_limited)
        self.assertEqual((error.message, error.retry_after), ("取得の間隔を空けています", 212))
        self.assertEqual(error.detail, "HTTP 429。Retry-After: 212 → 212 秒。anthropic-ratelimit-unified-status: rejected")
        self.assertNotIn("token-value", error.detail)

    def test_429_without_retry_after(self):
        error = self.raise_429({})
        self.assertIsNone(error.retry_after)
        self.assertEqual(error.detail, "HTTP 429。Retry-After: なし")


if __name__ == "__main__":
    unittest.main()
