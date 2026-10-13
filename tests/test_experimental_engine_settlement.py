import unittest
from tools.experimental_engine_settle import settle
from tools.experimental_engine_audit import audit

class SettlementTests(unittest.TestCase):
    def test_regulation_time_and_calibration(self):
        p={"date":"2026-10-13","status":"EXPERIMENT_ONLY","register_writes":False,
           "matches":[{"fixture_id":12,"snapshot_utc":"2026-10-13T10:00:00Z",
                       "markets":{"over_2_5":.65,"btts_yes":.55}}]}
        f=[{"fixture":{"id":12,"status":{"short":"AET"}},
            "score":{"fulltime":{"home":1,"away":1},"extratime":{"home":1,"away":0}}}]
        result=settle(p,f)
        self.assertEqual(result["rows"][0]["status"],"SETTLED")
        self.assertFalse(result["rows"][0]["events"][0]["occurred"])
        self.assertTrue(result["rows"][0]["events"][1]["occurred"])
        summary=audit([result])
        self.assertEqual(summary["markets"]["over_2_5"]["n"],1)
        self.assertEqual(summary["markets"]["over_2_5"]["hits"],0)
        self.assertEqual(summary["kb_n_effect"],0)
    def test_missing_results_pending(self):
        p={"date":"2026-10-13","status":"EXPERIMENT_ONLY","register_writes":False,
           "matches":[{"fixture_id":13,"snapshot_utc":"2026-10-13T10:00:00Z",
                       "markets":{"over_2_5":.5}}]}
        self.assertEqual(settle(p,[])["rows"][0]["status"],"PENDING")
if __name__=="__main__":unittest.main()
