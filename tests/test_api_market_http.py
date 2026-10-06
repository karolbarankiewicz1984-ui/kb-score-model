"""API outage and rate-limit regressions; fake clock and no network."""
import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import api_market_http as http


def response(payload=None, headers=None):
    result = io.BytesIO(json.dumps(payload or {"response": [1], "errors": []}).encode())
    result.headers = headers or {}
    return result


def failure(code, headers=None):
    return urllib.error.HTTPError("https://example.test/fixtures", code, "test", headers or {}, None)


class ApiHttpTests(unittest.TestCase):
    def setUp(self):
        self.clock = 100.0
        self.sleeps = []
        def sleep(seconds):
            self.sleeps.append(seconds)
            self.clock += seconds
        for target, kwargs in (("time.monotonic", {"side_effect": lambda: self.clock}),
                               ("time.sleep", {"side_effect": sleep}),
                               ("sys.stderr", {"new": io.StringIO()})):
            patcher = patch("api_market_http." + target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = http.ApiClient()

    def get(self):
        return self.client.get("https://example.test", "test-key", "fixtures", date="2030-01-02")

    def test_http_429_waits_then_returns_real_success(self):
        with patch.object(http.urllib.request, "urlopen", side_effect=[failure(429, {"Retry-After": "90"}), response()]) as call:
            payload, _ = self.get()
        self.assertEqual(call.call_count, 2)
        self.assertEqual(payload["response"], [1])
        self.assertGreaterEqual(sum(self.sleeps), 90)

    def test_json_rate_limit_is_retried_not_treated_as_empty_data(self):
        with patch.object(http.urllib.request, "urlopen", side_effect=[response({"errors": {"rateLimit": "Too many requests"}, "response": []}), response()]):
            self.assertEqual(self.get()[0]["response"], [1])
        self.assertGreaterEqual(sum(self.sleeps), 60)

    def test_requests_are_paced_and_adjust_to_provider_limit(self):
        with patch.object(http.urllib.request, "urlopen", side_effect=[response(headers={"X-RateLimit-Limit": "10"}), response()]):
            self.get()
            self.get()
        self.assertGreaterEqual(sum(self.sleeps), 7.5)

    def test_minute_exhaustion_waits_but_daily_exhaustion_stops(self):
        with patch.object(http.urllib.request, "urlopen", side_effect=[response(headers={"X-RateLimit-Remaining": "0", "x-ratelimit-requests-remaining": "2"}), response(headers={"x-ratelimit-requests-remaining": "0"})]) as call:
            self.get()
            self.assertEqual(self.get()[0]["response"], [1])
            with self.assertRaisesRegex(http.ApiLimitError, "daily"):
                self.get()
        self.assertEqual(call.call_count, 2)
        self.assertGreaterEqual(sum(self.sleeps), 61)

    def test_daily_limit_http_error_is_not_retried(self):
        with patch.object(http.urllib.request, "urlopen", side_effect=failure(429, {"x-ratelimit-requests-remaining": "0"})) as call:
            with self.assertRaisesRegex(http.ApiLimitError, "daily"):
                self.get()
        self.assertEqual(call.call_count, 1)

    def test_rate_limit_retries_are_bounded_and_stop_followup_requests(self):
        with patch.object(http.urllib.request, "urlopen", side_effect=[failure(429) for _ in range(4)]) as call:
            for _ in range(2):
                with self.assertRaisesRegex(http.ApiLimitError, "after 4 attempts"):
                    self.get()
        self.assertEqual(call.call_count, 4)

    def test_transient_server_error_is_retried(self):
        with patch.object(http.urllib.request, "urlopen", side_effect=[failure(503), response()]):
            self.assertEqual(self.get()[0]["response"], [1])

    def test_auth_and_validation_errors_are_not_hidden(self):
        with patch.object(http.urllib.request, "urlopen", side_effect=failure(401)) as call:
            with self.assertRaises(urllib.error.HTTPError):
                self.get()
        self.assertEqual(call.call_count, 1)
        payload = {"errors": {"date": "Invalid date"}, "response": []}
        with patch.object(http.urllib.request, "urlopen", return_value=response(payload)) as call:
            self.assertEqual(self.get()[0], payload)
        self.assertEqual(call.call_count, 1)


if __name__ == "__main__":
    unittest.main()
