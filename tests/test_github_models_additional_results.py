import csv
import io
import unittest

from github_models.additional_results import (
    ADDITIONAL_SOURCES, audit_additional_csv, parse_additional_csv, source_url,
)


class AdditionalResultsTests(unittest.TestCase):
    observed = "2026-11-06T08:43:05.832478+00:00"

    def row(self, source="POL", **changes):
        spec = ADDITIONAL_SOURCES[source]
        result = dict(Country=spec["country"], League=spec["source_league"],
                      Season="2026", Date="01/11/2026", Time="18:00", Home="Home", Away="Away",
                      HG="2", AG="1", Res="H", B365CH="1.90")
        return dict(result, **changes)

    def csv(self, rows):
        text = io.StringIO()
        fields = list(self.row())
        writer = csv.DictWriter(text, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        return text.getvalue()

    def audit(self, rows, source="POL", **options):
        return audit_additional_csv(self.csv(rows), source_code=source,
                                   observed_at_utc=options.pop("observed_at_utc", self.observed), **options)

    def test_all_observed_feed_schemas_and_unique_country_competitions(self):
        self.assertEqual(len(ADDITIONAL_SOURCES), 11)
        names = set()
        for code, spec in ADDITIONAL_SOURCES.items():
            with self.subTest(source=code):
                report = self.audit([self.row(code)], source=code)
                self.assertEqual(report["accepted_count"], 1)
                parsed = report["accepted"][0]
                self.assertEqual(parsed["league"], spec["league"])
                self.assertEqual(parsed["country_code"], spec["country_code"])
                self.assertEqual(parsed["source_url"], f"https://www.football-data.co.uk/new/{code}.csv")
                names.add(parsed["league"])
        self.assertEqual(len(names), 11)
        for code, unsafe in (("AUT", "Bundesliga"), ("BRA", "Serie A"), ("RUS", "Premier League")):
            self.assertNotEqual(ADDITIONAL_SOURCES[code]["league"], unsafe)

    def test_first_observation_and_completion_bound_are_preserved_without_odds_or_events(self):
        parsed = parse_additional_csv(self.csv([self.row(Home="Łódź", Away="Gdańsk")]),
                                      source_code="POL", observed_at_utc=self.observed)[0]
        self.assertEqual(parsed["fixture_id"], "fdco:new:POL:2026-11-01:Łódź:Gdańsk")
        self.assertEqual(parsed["match_date"], "2026-11-01")
        self.assertEqual(parsed["completed_at_utc"], "2026-11-03T00:00:00Z")
        self.assertEqual(parsed["published_at_utc"], self.observed)
        self.assertEqual(parsed["status"], "FINISHED")
        self.assertEqual(parsed["source_provider"], "football-data.co.uk")
        self.assertFalse({"events", "odds", "B365CH", "kickoff_utc"} & set(parsed))

    def test_availability_boundary_uses_aware_observation_and_never_future_results(self):
        record = self.row(Date="04/11/2026")
        equal = self.audit([record], observed_at_utc="2026-11-06T00:00:00Z")
        self.assertEqual(equal["accepted_count"], 0)
        self.assertEqual(equal["rejection_reasons"], {"completion_not_verified_before_observation": 1})
        after = self.audit([record], observed_at_utc="2026-11-06T01:00:01+01:00")
        self.assertEqual(after["accepted_count"], 1)
        self.assertEqual(after["accepted"][0]["published_at_utc"], "2026-11-06T01:00:01+01:00")
        future = self.audit([self.row(Date="07/11/2026")])
        self.assertEqual(future["accepted_count"], 0)
        with self.assertRaisesRegex(ValueError, "timezone_required"):
            self.audit([record], observed_at_utc="2026-11-06T08:00:00")

    def test_country_league_and_argentine_cup_cannot_cross_match(self):
        bad_brazil = self.audit([self.row("BRA", Country="Italy"), self.row("BRA", League="Serie B")], source="BRA")
        self.assertEqual(bad_brazil["accepted_count"], 0)
        self.assertEqual(bad_brazil["rejection_reasons"], {"source_country_conflict": 1, "unsupported_source_league": 1})
        argentina = self.audit([self.row("ARG", League="Copa De La Liga Profesional"),
                                self.row("ARG", League="Liga Profesional ")], source="ARG")
        self.assertEqual(argentina["accepted_count"], 1)
        self.assertEqual(argentina["rejection_reasons"], {"unsupported_source_league": 1})

    def test_recent_scope_uses_real_declared_season_and_consistent_match_year(self):
        report = self.audit([
            self.row(Season="2022/2023", Date="01/03/2023"),
            self.row(Season="2023/2024", Date="01/03/2024", Home="Winter"),
            self.row(Season="2023", Date="01/03/2023", Home="Calendar"),
            self.row(Season="2023/2026"), self.row(Season="2026/2025"),
            self.row(Season="2023", Date="01/03/2026"), self.row(Season="unknown"),
        ])
        self.assertEqual({row["home"] for row in report["accepted"]}, {"Winter", "Calendar"})
        self.assertEqual(report["rejected_count"], 5)
        self.assertEqual(report["rejection_reasons"]["season_before_requested_scope"], 1)
        self.assertEqual(report["rejection_reasons"]["match_date_outside_declared_season"], 1)

    def test_missing_fractional_negative_and_inconsistent_final_scores_are_rejected(self):
        report = self.audit([
            self.row(HG=""), self.row(HG="-1"), self.row(HG="1.5"), self.row(HG="NaN"),
            self.row(Res=""), self.row(Res="postponed"), self.row(Res="D"),
            self.row(HG="1", AG="1", Res="D", Home="Draw"),
            self.row(HG="0", AG="3", Res="A", Home="Away win"),
        ])
        self.assertEqual(report["accepted_count"], 2)
        self.assertEqual(report["rejection_reasons"], {
            "final_result_score_conflict": 1, "final_result_status_missing_or_invalid": 2,
            "missing_or_invalid_final_score": 4,
        })

    def test_identical_duplicates_count_once_and_conflicting_fixture_is_excluded(self):
        record = self.row()
        report = self.audit([record, record, self.row(Home="Conflicting"),
                             self.row(Home="Conflicting", HG="3")])
        self.assertEqual(report["accepted_count"], 1)
        self.assertEqual(report["rejection_reasons"], {"conflicting_duplicate_fixture": 2, "duplicate_fixture": 1})
        self.assertEqual(report["input_records"], report["accepted_count"] + report["rejected_count"])

    def test_ambiguous_headers_fail_while_real_empty_trailing_headers_are_allowed(self):
        text = self.csv([self.row()])
        lines = text.splitlines()
        trailing = "\n".join(line + ",," for line in lines)
        self.assertEqual(len(parse_additional_csv(trailing, source_code="POL", observed_at_utc=self.observed)), 1)
        duplicate = text.replace("Home,Away", "Home,Home")
        with self.assertRaisesRegex(ValueError, "headers"):
            parse_additional_csv(duplicate, source_code="POL", observed_at_utc=self.observed)

    def test_unknown_sources_invalid_scope_and_missing_teams_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "unsupported_additional_source"):
            source_url("Australia")
        for value in (True, "2023", 0):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "invalid_min_season_year"):
                self.audit([self.row()], min_season_year=value)
        report = self.audit([self.row(Home=""), self.row(Home="Away")])
        self.assertEqual(report["accepted_count"], 0)
        self.assertEqual(report["rejection_reasons"], {"invalid_team_identity": 2})


if __name__ == "__main__":
    unittest.main()
