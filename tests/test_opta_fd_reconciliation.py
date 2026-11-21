import json
import unittest
from pathlib import Path

from github_models.opta_fd_reconciliation import reconcile

BENCH=Path("research/multimodel/opta_fd_benchmark_20261121.json")


class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.benchmark=json.loads(BENCH.read_text(encoding="utf-8"))
        cls.archived=[]
        for c in cls.benchmark["rows"]:
            cls.archived.append({
                "source_record_id": c["source_record_id"],
                "source_provider": "football-data.co.uk",
                "league_code": "E0", "match_date": c["match_date"],
                "events": {
                    "fouls": c["verified_opta_fouls_home_away"],
                    "cards": c["verified_opta_yellow_home_away"],
                },
            })

    def test_evidence_schema_and_sample(self):
        s=reconcile(self.benchmark,self.archived)
        self.assertEqual(s["pair_compared"],31)
        self.assertEqual(s["fouls_disagreement_matches"],0)
        self.assertEqual(s["yellow_disagreement_matches"],0)
        self.assertFalse(s["superbet_settlement_equivalence_proven"])
        self.assertTrue(s["red_cards_not_reconstructible_as_superbet_bookings"])

    def test_difference_is_reported_not_hidden(self):
        a=json.loads(json.dumps(self.archived))
        a[0]["events"]["fouls"][0]+=1
        s=reconcile(self.benchmark,a)
        self.assertEqual(s["fouls_disagreement_matches"],1)
        self.assertEqual(s["yellow_disagreement_matches"],0)
        self.assertEqual(s["rows"][0]["fouls_difference"],[1,0])

    def test_missing_or_duplicate_is_fatal(self):
        with self.assertRaises(ValueError):
            reconcile(self.benchmark,self.archived[:-1])
        with self.assertRaises(ValueError):
            reconcile(self.benchmark,self.archived+[self.archived[0]])

    def test_other_league_is_fatal(self):
        x=json.loads(json.dumps(self.archived))
        x[1]["league_code"]="D1"
        with self.assertRaises(ValueError):
            reconcile(self.benchmark,x)


if __name__=="__main__":
    unittest.main()
