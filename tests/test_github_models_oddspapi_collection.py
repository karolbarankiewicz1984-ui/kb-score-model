"""Collector response-shape and spending guards; no network calls."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from github_models.oddspapi_collect import extract_batch, _quota_state, _cache_catalog


class CollectorTests(unittest.TestCase):
    def test_documented_batch_shapes(self):
        game={"fixtureId":"id1","bookmakerOdds":{}}
        for payload in (game,[game],{"fixtures":[game]},{"data":[game]},{"id1":game}):
            with self.subTest(payload=type(payload).__name__):
                self.assertEqual(extract_batch(payload),[game])
        self.assertEqual(extract_batch({}),[])
        with self.assertRaisesRegex(ValueError,"unknown_shape"):
            extract_batch({"unknown_data":"something"})
        with self.assertRaisesRegex(ValueError,"list_schema"):
            extract_batch([{"bookmakerOdds":{}}])

    def test_polish_books_only_and_hard_limit(self):
        sub={"subscription_id":"a","is_active":True,"request_limit":250,
             "request_count":190,"bookmakers":{"superbet.pl":{}},"sport_ids":[10]}
        account={"current_subscription_id":"a","subscriptions":[sub]}
        state,sts=_quota_state(account,3)
        self.assertEqual(state["request_count"],190)
        self.assertFalse(sts)
        sub["request_count"]=198
        with self.assertRaisesRegex(RuntimeError,"reserve_guard"):
            _quota_state(account,3)
        sub["request_count"]=10
        sub["bookmakers"]={"efortuna.pl":{}}
        with self.assertRaisesRegex(RuntimeError,"polish_superbet"):
            _quota_state(account,1)

    def test_monthly_market_cache_reuses_catalog_without_provider(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"2026-11"/"markets.json"
            items=[{"marketId":i,"sportId":10} for i in range(120)]
            with patch("github_models.oddspapi_collect.api_get",return_value=items) as api:
                got,changed=_cache_catalog(path)
                self.assertTrue(changed)
                self.assertEqual(len(got),120)
                got,changed=_cache_catalog(path)
                self.assertFalse(changed)
                self.assertEqual(len(got),120)
                self.assertEqual(api.call_count,1)


if __name__=="__main__":
    unittest.main()
