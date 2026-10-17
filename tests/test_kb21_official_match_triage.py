"""Crosschecks remain per-fixture diagnostic, even when two clocks agree."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.kb21_official_match_triage import collect

DAYS = ["2026-10-17", "2026-10-18"]
QUEUE = {
    "days": DAYS,
    "fixtures": [
        {"date_warsaw": DAYS[0], "fixture_id": "eng.1:11",
         "fixture": "Arsenal - Brighton", "kickoff": "2026-10-17T15:00:00+02:00"},
        {"date_warsaw": DAYS[0], "fixture_id": "esp.1:12",
         "fixture": "Real Betis - Barcelona", "kickoff": "2026-10-17T18:00:00+02:00"},
        {"date_warsaw": DAYS[1], "fixture_id": "uefa.europa:13",
         "fixture": "Rennes - Juventus", "kickoff": "2026-10-18T18:00:00+02:00"},
    ],
}


def put(folder, filename, rows_by_day):
    Path(folder, filename).write_text(json.dumps({
        "calendar_gate": "BLOCKED", "days": {
            day: {"comparisons": rows_by_day.get(day, [])} for day in DAYS
        },
    }), encoding="utf-8")


class OfficialPerFixtureTriageTests(unittest.TestCase):
    def test_distinguishes_exact_time_conflict_from_agreement(self):
        with tempfile.TemporaryDirectory() as path:
            put(path, "official-fpl-vs-espn.json", {
                DAYS[0]: [{
                    "espn_fixture_id": "eng.1:11",
                    "status": "MATCHED_FOR_REVIEW",
                    "fpl_kickoff": "2026-10-17T15:00:00+02:00",
                }],
            })
            put(path, "official-laliga-vs-espn.json", {
                DAYS[0]: [{
                    "candidate_id": "esp.1:12",
                    "status": "KICKOFF_CONFLICT",
                    "organizer_kickoff": "2026-10-17T18:30:00+02:00",
                }],
            })
            result = collect(QUEUE, path)
        premier = result[(DAYS[0], "eng.1:11")]
        spain = result[(DAYS[0], "esp.1:12")]
        self.assertEqual(premier["organizer_comparator_status"], "MATCHED_FOR_REVIEW")
        self.assertEqual(spain["organizer_comparator_status"], "KICKOFF_CONFLICT")
        self.assertEqual(spain["official_kickoff_claim"], "2026-10-17T18:30:00+02:00")
        self.assertFalse(spain["kickoff_evidence_validated_by_signoff"])
        self.assertEqual(result[(DAYS[1], "uefa.europa:13")]["organizer_comparator_status"],
                         "COMPARATOR_NOT_AVAILABLE")

    def test_uefa_date_only_never_becomes_approved_kickoff(self):
        with tempfile.TemporaryDirectory() as path:
            put(path, "official-uefa-europa-vs-espn.json", {
                DAYS[1]: [{
                    "fixture_id": "uefa.europa:13",
                    "status": "DATE_TEAMS_ONLY_KICKOFF_UNVERIFIED",
                    "time_comparison_performed": False,
                }],
            })
            result = collect(QUEUE, path)
        hint = result[(DAYS[1], "uefa.europa:13")]
        self.assertIsNone(hint["official_kickoff_claim"])
        self.assertFalse(hint["kickoff_evidence_validated_by_signoff"])

    def test_reject_comparator_unknown_or_misdated_game(self):
        with tempfile.TemporaryDirectory() as path:
            put(path, "official-fpl-vs-espn.json", {
                DAYS[1]: [{"espn_fixture_id": "eng.1:11",
                           "status": "MATCHED_FOR_REVIEW"}],
            })
            with self.assertRaisesRegex(ValueError, "unknown or misdated"):
                collect(QUEUE, path)

    def test_refuse_signed_comparator_and_duplicates(self):
        with tempfile.TemporaryDirectory() as path:
            put(path, "official-laliga-vs-espn.json", {
                DAYS[0]: [{"candidate_id": "esp.1:12", "status": "KICKOFF_CONFLICT"},
                          {"candidate_id": "esp.1:12", "status": "MATCHED_FOR_REVIEW"}],
            })
            with self.assertRaisesRegex(ValueError, "duplicates fixture"):
                collect(QUEUE, path)
            file = Path(path, "official-laliga-vs-espn.json")
            doc = json.loads(file.read_text())
            doc["calendar_gate"] = "PASS_MANUAL"
            file.write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError, "Invalid/signed"):
                collect(QUEUE, path)


if __name__ == "__main__":
    unittest.main()
