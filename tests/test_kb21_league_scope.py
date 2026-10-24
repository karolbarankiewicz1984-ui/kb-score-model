"""Protect KB21 competition scope and original scoring boundaries."""
import unittest

from tools.kb21_api_prematch import in_scope
from tools.kb21_league_scope import (
    DOMESTIC_IDS, INTERNATIONAL_IDS, scope_method,
)
from tools.kb21_calendar_health import (
    DOMESTIC_IDS as HEALTH_DOMESTIC_IDS,
    INTERNATIONAL_IDS as HEALTH_INTERNATIONAL_IDS,
)
from tools.kb21_single_source_calendar import _event
from datetime import datetime, timezone


def fixture(lid, name, country):
    return {"league": {"id": lid, "name": name, "country": country}}


class LeagueScopeTests(unittest.TestCase):
    def test_known_league_id_survives_provider_display_name_change(self):
        item = fixture(39, "English Premier Division (renamed)", "England")
        self.assertTrue(in_scope(item))
        self.assertEqual(scope_method(item), "LEAGUE_ID")
        self.assertTrue(in_scope(fixture(848, "UEFA club competition renamed", "World")))

    def test_known_id_country_mismatch_fails_closed(self):
        item = fixture(39, "Premier League", "Turkey")
        self.assertFalse(in_scope(item))
        self.assertEqual(scope_method(item), "ID_COUNTRY_CONFLICT")

    def test_name_fallback_only_for_supported_name(self):
        self.assertTrue(in_scope(fixture(999, "Premier League", "England")))
        self.assertEqual(scope_method(fixture(999, "Premier League", "England")),
                         "NAME_FALLBACK")
        self.assertFalse(in_scope(fixture(999, "Second Division", "England")))
        self.assertFalse(in_scope(fixture(39, "Second Division", "Turkey")))

    def test_missing_or_malformed_id_is_guarded(self):
        self.assertTrue(in_scope(fixture(None, "Ekstraklasa", "Poland")))
        self.assertFalse(in_scope(fixture(True, "Something", "England")))
        self.assertFalse(in_scope({"league": None}))
        self.assertFalse(in_scope({}))

    def test_health_checker_and_collector_use_same_league_ids(self):
        self.assertEqual(DOMESTIC_IDS, HEALTH_DOMESTIC_IDS)
        self.assertEqual(INTERNATIONAL_IDS, HEALTH_INTERNATIONAL_IDS)

    def test_single_source_calendar_includes_renamed_id_but_no_play(self):
        data = {
            "fixture": {
                "id": 901, "date": "2026-10-25T14:00:00+01:00",
                "status": {"short": "NS", "long": "Not Started"}},
            "league": {"id": 39, "name": "Renamed top league",
                       "country": "England", "season": 2026},
            "teams": {"home": {"id": 1, "name": "Team A"},
                      "away": {"id": 2, "name": "Team B"}},
        }
        row = _event(data, "2026-10-25",
                     datetime(2026, 10, 24, 9, tzinfo=timezone.utc))
        self.assertTrue(row["in_kb21_scope"])
        self.assertTrue(row["eligible_for_prematch_research"])
        self.assertEqual(row["candidate_status"], "CANDIDATE")
        self.assertEqual(row["provider"], "API-Football")


if __name__ == "__main__":
    unittest.main()
