import unittest
from tools.kb21_tff_compare import compare, render


def source():
    return {
        "schema": "kb21-official-tff-superlig-v1",
        "league_id": "tur.1", "days": ["2026-10-17"],
        "official_url": "https://www.tff.org/?pageID=198",
        "status": "OFFICIAL_TFF_MATCHWEEK_PARTIAL_FOR_REVIEW",
        "errors": [], "unconfirmed_zero_dates": [],
        "by_day": {"2026-10-17": [{
            "home": "GENÇLERBİRLİĞİ", "away": "GALATASARAY A.Ş.",
            "kickoff_utc": "2026-10-17T13:00:00+00:00",
            "kickoff_warsaw": "2026-10-17T15:00:00+02:00",
        }]},
    }


def queue(time="2026-10-17T15:00:00+02:00"):
    return {"days": ["2026-10-17"], "fixtures": [{
        "fixture_id": "tur.1:10", "fixture": "Genclerbirligi - Galatasaray",
        "date_warsaw": "2026-10-17", "kickoff": time,
    }]}


class TFFComparisonTests(unittest.TestCase):
    def test_turkish_aliases_and_timezone_match_without_signoff(self):
        report = compare(queue(), source())
        self.assertEqual(report["days"]["2026-10-17"]["matched"], 1)
        self.assertFalse(report["reviewer_signed"])
        self.assertEqual(report["calendar_gate"], "BLOCKED")
        self.assertIn("NO PLAY", render(report))

    def test_wrong_kickoff_stays_conflict(self):
        report = compare(queue("2026-10-17T15:45:00+02:00"), source())
        row = report["days"]["2026-10-17"]
        self.assertEqual(row["matched"], 0)
        self.assertEqual(row["statuses"]["START_TIME_CONFLICT"], 1)

    def test_bad_fixture_capture_not_accepted_as_match(self):
        bad = source()
        bad["status"] = "OFFICIAL_TFF_UNAVAILABLE_OR_INCOMPLETE"
        bad["errors"] = ["incomplete matchweek"]
        report = compare(queue(), bad)
        self.assertEqual(report["days"]["2026-10-17"]["matched"], 0)
        self.assertEqual(report["days"]["2026-10-17"]["statuses"]["UNRELIABLE_TFF_MATCHWEEK"], 1)

    def test_wrong_scope_rejected(self):
        bad = source()
        bad["days"] = ["2026-10-18"]
        with self.assertRaises(ValueError):
            compare(queue(), bad)


if __name__ == "__main__":
    unittest.main()
