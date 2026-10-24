"""Offline tests: no API calls, no GitHub writes, no model changes."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.kb21_calendar_health import check, markdown

DAYS = ["2026-10-24", "2026-10-25"]


def fixture(fid, lid=39, country="England", inscope=True, status="NS", name="Premier League"):
    return {"fixture_id": fid, "league_id": lid, "league": name,
            "country": country, "in_kb21_scope": inscope, "status": status}


def write(folder, daily=None, time="2026-10-24T08:25:00+00:00"):
    root = Path(folder)
    manifest = {"dates": DAYS, "single_source_gate": "PASS_SOURCE",
                "provider_count": 1, "generated_at_utc": time}
    (root / "SINGLE_SOURCE_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    for day in DAYS:
        events = (daily or {}).get(day, [fixture(11 if day == DAYS[0] else 12)])
        data = {"date": day, "single_source_gate": "PASS_SOURCE",
                "provider_total_events": len(events), "provider_events": events,
                "in_scope_provider_events": sum(bool(e["in_kb21_scope"]) for e in events),
                "candidates": [e for e in events if e["in_kb21_scope"] and e["status"] == "NS"],
                "pre_match_fixtures": sum(e["in_kb21_scope"] and e["status"] == "NS" for e in events)}
        (root / ("KB21_API_CALENDAR_" + day + ".json")).write_text(
            json.dumps(data), encoding="utf-8")


class CalendarHealthTests(unittest.TestCase):
    def test_valid_source_is_only_diagnostic(self):
        with tempfile.TemporaryDirectory() as td:
            write(td)
            x = check(td)
            self.assertEqual(x["status"], "PASS")
            self.assertFalse(x["safe_to_publish_play"])
            self.assertFalse(x["register_writes"])
            self.assertEqual(x["original_kb21_n_effect"], 0)
            self.assertIn("API-Football", markdown(x))

    def test_renamed_known_id_excluded_from_old_filter_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, {DAYS[0]: [fixture(101, lid=39, inscope=False, name="English Top Division")]})
            x = check(td)
            self.assertEqual(x["status"], "FAIL")
            self.assertEqual(x["excluded_known_id"][0]["fixture_id"], 101)

    def test_unknown_id_and_wrong_country_are_not_false_errors(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, {DAYS[0]: [
                fixture(100, lid=999, inscope=False),
                fixture(101, lid=39, country="Turkey", inscope=False)]})
            self.assertEqual(check(td)["status"], "PASS")

    def test_valid_empty_day_and_late_run_warn_instead_of_inventing_games(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, {DAYS[0]: []}, time="2026-10-24T10:20:00+00:00")
            x = check(td)
            self.assertEqual(x["status"], "WARN")
            self.assertEqual(len(x["warnings"]), 2)

    def test_missing_provider_fixture_compared_to_prior_run_warns(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as prev:
            write(td, {DAYS[0]: [fixture(1), fixture(2)]})
            write(prev, {DAYS[0]: [fixture(1), fixture(2), fixture(3),
                                  fixture(4), fixture(5), fixture(6)]})
            x = check(td, prev)
            self.assertEqual(x["status"], "WARN")
            self.assertEqual(x["previous_comparison"]["missing"], 4)

    def test_bad_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            write(td)
            (Path(td) / "SINGLE_SOURCE_MANIFEST.json").write_text(
                '{"single_source_gate":"BLOCKED"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                check(td)


if __name__ == "__main__":
    unittest.main()
