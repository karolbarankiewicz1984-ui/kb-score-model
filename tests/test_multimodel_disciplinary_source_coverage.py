"""Secondary event coverage is not licensed official Opta evidence."""
import unittest
from github_models.disciplinary_source_coverage import audit_events

NOW="2026-11-23T19:00:00Z"
def event(fid="m1",fouls=(12,14),cards=(2,3),source="football-data.co.uk"):
    return {"source_provider":source,"fixture_id":fid,"league":"Serie B",
            "country_code":"ITA","home":"Alpha","away":"Beta",
            "match_date":"2026-11-20",
            "completed_at_utc":"2026-11-22T00:00:00Z",
            "published_at_utc":"2026-11-23T09:00:00Z",
            "events":{"fouls":list(fouls),"cards":list(cards)}}
def scope():
    return {"schema":"multimodel-non-pl-opta-evidence-scope-v1",
            "verified_non_pl_opta_per_team_fouls":0,
            "promotion_gate":{
               "minimum_football_data_vs_independent_opta_non_pl_matches":30}}
def manifest():
    return {"sources":[{"status":"ok"},{"status":"error"}]}

class Coverage(unittest.TestCase):
    def test_real_secondary_totals_remain_unsafe_for_superbet(self):
        a=audit_events([event()],manifest(),scope(),as_of_utc=NOW)
        self.assertEqual(a["fouls"]["aggregate_pair_matches"],1)
        self.assertEqual(a["cards"]["aggregate_pair_matches"],1)
        self.assertEqual(a["league_coverage"][0]["country_code"],"ITA")
        self.assertEqual(a["source_manifest_ok"],1)
        self.assertFalse(a["fouls"]["compatible_with_official_superbet"])
        self.assertFalse(a["cards"]["compatible_with_official_superbet"])
        self.assertFalse(a["market_promotion_allowed"])
        self.assertFalse(a["official_opta_event_level_source_observed"])
        self.assertEqual(a["paid_oddspapi_calls"],0)

    def test_conflicting_duplicate_foul_values_not_counted(self):
        a=audit_events([event(),event(fouls=(7,19))],
                       manifest(),scope(),as_of_utc=NOW)
        self.assertEqual(a["unique_secondary_fixture_rows"],1)
        self.assertEqual(a["fouls"]["aggregate_pair_matches"],0)
        self.assertEqual(a["cards"]["aggregate_pair_matches"],1)
        self.assertEqual(a["excluded_reasons"]["fouls_duplicate_conflict"],1)

    def test_future_and_opta_label_never_inflates_secondary_pairs(self):
        fake=event(fid="m2",source="OPTA-official-event-data")
        later=event(fid="m3")
        later["published_at_utc"]="2026-11-24T00:00:00Z"
        a=audit_events([event(),fake,later],manifest(),scope(),as_of_utc=NOW)
        self.assertEqual(a["fouls"]["aggregate_pair_matches"],1)
        self.assertEqual(a["excluded_reasons"]["different_source_not_opted_in"],1)
        self.assertEqual(a["excluded_reasons"]["future_or_invalid_publication"],1)

    def test_forged_opta_scope_count_cannot_silently_unblock(self):
        forged=scope();forged["verified_non_pl_opta_per_team_fouls"]=30
        with self.assertRaisesRegex(ValueError,"new_opta_evidence_requires"):
            audit_events([],manifest(),forged,as_of_utc=NOW)

if __name__=="__main__":
    unittest.main()
