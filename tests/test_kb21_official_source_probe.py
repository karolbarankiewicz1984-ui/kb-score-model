import io
import unittest
import urllib.error
from datetime import datetime, timezone

from tools.kb21_official_source_probe import (
    MAX_SAMPLE, OFFICIAL_PAGES, _related_host, collect, probe
)


class FakeResponse(io.BytesIO):
    status = 200
    headers = {"Content-Type": "text/html; charset=UTF-8"}

    def __init__(self, data=b"<html>Official schedule page</html>", target=None):
        super().__init__(data)
        self.target = target

    def geturl(self):
        return self.target or "https://www.premierleague.com/en/matches/premier-league/2026-27?cl=-1&co=8"


def now():
    return datetime(2026, 10, 17, 11, 0, tzinfo=timezone.utc)


class OrganizerProbeTests(unittest.TestCase):
    def test_http_200_never_confirms_organizer_calendar(self):
        url = OFFICIAL_PAGES["eng.1"]
        check = probe("eng.1", url, opener=lambda req, timeout: FakeResponse(), clock=now)
        self.assertEqual(check["status"], "HTTP_ACCESSIBLE_SAMPLE")
        self.assertEqual(check["sample_bytes"], len(b"<html>Official schedule page</html>"))
        self.assertEqual(check["observed_at_utc"], "2026-10-17T11:00:00+00:00")
        self.assertEqual(len(check["sample_sha256"]), 64)
        self.assertFalse(check["fixture_list_extracted"])
        self.assertFalse(check["full_day_verified"])
        self.assertFalse(check["reviewer_signed"])
        self.assertEqual(check["calendar_gate"], "BLOCKED")

    def test_cross_host_redirect_not_trusted(self):
        url = OFFICIAL_PAGES["eng.1"]
        check = probe("eng.1", url,
                      opener=lambda req, timeout: FakeResponse(target="https://unexpected.example/"),
                      clock=now)
        self.assertEqual(check["status"], "CROSS_HOST_REDIRECT_REQUIRES_REVIEW")
        self.assertTrue(_related_host("https://www.uefa.com/", "https://uefa.com/"))
        self.assertFalse(_related_host("https://uefa.com/", "https://example.com/"))

    def test_bounded_truncated_sample_is_not_full_fixture_capture(self):
        url = OFFICIAL_PAGES["eng.1"]
        check = probe("eng.1", url,
                      opener=lambda req, timeout: FakeResponse(data=b"x" * (MAX_SAMPLE + 400)),
                      clock=now)
        self.assertEqual(check["sample_bytes"], MAX_SAMPLE)
        self.assertTrue(check["sample_truncated"])
        self.assertEqual(check["status"], "HTTP_ACCESSIBLE_PARTIAL_SAMPLE")
        self.assertFalse(check["full_day_verified"])

    def test_failures_are_diagnostics_never_approvals(self):
        url = OFFICIAL_PAGES["eng.1"]

        def http_error(req, timeout):
            raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)

        check = probe("eng.1", url, opener=http_error, clock=now)
        self.assertEqual(check["status"], "HTTP_ERROR")
        self.assertEqual(check["http_status"], 403)

        def timeout(req, timeout):
            raise TimeoutError("No response")

        check = probe("eng.1", url, opener=timeout, clock=now)
        self.assertEqual(check["status"], "FETCH_FAILED")
        self.assertEqual(check["error_category"], "TimeoutError")

    def test_all_14_organizer_entry_urls_checked_for_each_scope(self):
        def opener(req, timeout):
            # Retain requested host so we test every trusted source.
            return FakeResponse(target=req.full_url)
        report = collect(["2026-10-17", "2026-10-18"], opener=opener, clock=now)
        self.assertEqual(len(report["sources"]), len(OFFICIAL_PAGES))
        self.assertEqual(report["status_counts"]["HTTP_ACCESSIBLE_SAMPLE"], len(OFFICIAL_PAGES))
        self.assertEqual(report["calendar_gate"], "BLOCKED")
        self.assertFalse(report["any_fixture_list_verified"])
        self.assertFalse(report["all_organizers_authenticated"])

    def test_invalid_scope_rejected(self):
        with self.assertRaises(ValueError):
            collect(["2026-10-17", "2026-10-17"])
        with self.assertRaises(ValueError):
            collect(["2026-10-17", "2026-10-18", "2026-10-19", "2026-10-20"])


if __name__ == "__main__":
    unittest.main()
