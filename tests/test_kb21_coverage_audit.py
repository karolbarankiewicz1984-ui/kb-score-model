import unittest
from tools.kb21_coverage_audit import audit

class CoverageAuditTests(unittest.TestCase):
    def test_supported_and_unsupported_are_separate(self):
        api={"date":"2030-01-01","candidates":[
            {"league_country":"England","league":"Premier League"},
            {"league_country":"Europe","league":"UEFA Europa League"},
            {"league_country":"England","league":"Premier League"}]}
        coverage={"competitions":[{"code":"PL"}]}
        result=audit(api,coverage)
        self.assertEqual(result["candidate_count"],3)
        self.assertEqual(result["by_coverage"]["SUPPORTED_BY_PROVIDER"],2)
        self.assertEqual(result["by_coverage"]["NO_VERIFIED_PROVIDER_MAPPING"],1)
        self.assertEqual(result["kb_n_effect"],0)
    def test_known_but_not_subscribed(self):
        api={"date":"2030-01-01","candidates":[{"league_country":"Spain","league":"La Liga"}]}
        result=audit(api,{"competitions":[{"code":"PL"}]})
        self.assertEqual(result["by_coverage"]["NOT_IN_PROVIDER_COVERAGE"],1)

if __name__=="__main__":
    unittest.main()
