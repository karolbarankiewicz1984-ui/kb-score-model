import io
import json
import unittest
from tools.kb21_football_data_org import fetch,coverage

class FakeResponse:
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self,*args): return self.payload.read(*args)

class IndependentAdapterTests(unittest.TestCase):
    def test_snapshot_preserves_distinct_ids_without_verifying(self):
        def opener(request,timeout):
            self.assertEqual(request.get_header("X-auth-token"),"test-token")
            self.assertIn("dateFrom=2030-01-01",request.full_url)
            response=FakeResponse()
            response.payload=io.BytesIO(json.dumps({"matches":[{
                "id":17,"utcDate":"2030-01-01T12:00:00Z","status":"SCHEDULED",
                "homeTeam":{"id":100,"name":"A"},"awayTeam":{"id":200,"name":"B"},
                "competition":{"code":"PL","name":"Premier League"}}]}).encode())
            return response
        result=fetch("2030-01-01","test-token",opener)
        self.assertEqual(result["fixtures"][0]["home_team_id"],100)
        self.assertTrue(result["provider_ids_are_not_api_football_ids"])
        self.assertEqual(result["kb_n_effect"],0)
        self.assertEqual(result["status"],"INDEPENDENT_SNAPSHOT_UNMATCHED")
    def test_subscription_coverage(self):
        def opener(request,timeout):
            self.assertTrue(request.full_url.endswith("/v4/competitions"))
            response=FakeResponse()
            response.payload=io.BytesIO(json.dumps({"competitions":[{"id":2021,"code":"PL","name":"Premier League","area":{"name":"England"},"plan":"TIER_ONE"}]}).encode())
            return response
        result=coverage("test-token",opener)
        self.assertEqual(result["competition_count"],1)
        self.assertEqual(result["competitions"][0]["code"],"PL")
        self.assertEqual(result["kb_n_effect"],0)
    def test_competition_filter(self):
        def opener(request,timeout):
            self.assertIn("competitions=PL%2CPD",request.full_url)
            response=FakeResponse()
            response.payload=io.BytesIO(b'{"matches":[]}')
            return response
        result=fetch("2030-01-01","token",opener,competition_codes=["PL","PD"])
        self.assertEqual(result["requested_competitions"],["PL","PD"])
        self.assertEqual(result["fixtures"],[])
    def test_reject_bad_date(self):
        with self.assertRaises(ValueError):
            fetch("not-a-date","token")
if __name__=="__main__":unittest.main()
