import unittest
from copy import deepcopy
from github_models.panel_links import panel_links, key

class PanelLinkTests(unittest.TestCase):
    def setUp(self):
        self.freeze="2026-11-24T12:00:00Z"
        self.fixtures={"generated_at_utc":self.freeze,"fixtures":[{"fixture_id":"f","kickoff_utc":"2026-11-24T20:00:00Z"}]}
        self.row={"fixture_id":"f","market":"goals","line":2.5,"selection":"over","model":"m","variant":"A","probability":0.75}
        self.forecasts={"abc":{"candidates":[self.row]},"shadow":{"candidates":[]}}
        self.quote={**self.row,"model_id":"m","p_model":0.75,"price":1.2,"bookmaker":"superbet.pl","settlement_verified":True,"source_market_id":"a","source_outcome_id":"b","odds_fixture_id":"q","forecast_frozen_at_utc":self.freeze,"odds_captured_at_utc":"2026-11-24T13:00:00Z"}
        self.odds={"abc_comparisons":{"comparisons":[self.quote]},"shadow_comparisons":{"rows":[]}}
        self.results={"exact_shadow_outcomes":[]}

    def link(self):
        return panel_links(self.fixtures,self.forecasts,self.odds,self.results)["rows"][0]

    def test_exact(self):
        row=self.link()
        self.assertEqual(row["quote_status"],"archived_research_quote")
        self.assertFalse(row["top_eligible"])
        self.assertIsNone(row["quality_score"])

    def test_wrong_line_model_probability_or_time(self):
        for field,value in [("line",3.5),("model_id","other"),("p_model",0.5),("odds_captured_at_utc","2026-11-24T20:00:00Z"),("odds_captured_at_utc","2026-11-24T11:00:00Z"),("settlement_verified",False),("source_market_id",None),("bookmaker","other")]:
            with self.subTest(field=field):
                old=self.quote[field];self.quote[field]=value
                self.assertIsNone(self.link()["quote"])
                self.quote[field]=old

    def test_low_price(self):
        self.quote["price"]=1.19
        self.assertEqual(self.link()["quote_status"],"below_minimum_odds")

    def test_ambiguity(self):
        self.odds["abc_comparisons"]["comparisons"].append({**self.quote,"price":1.3})
        self.assertEqual(self.link()["quote_status"],"ambiguous_quote")
        self.assertIsNone(self.link()["quote"])

    def test_duplicate_forecast(self):
        self.forecasts["abc"]["candidates"].append(deepcopy(self.row))
        with self.assertRaisesRegex(ValueError,"duplicate_forecast_identity"): self.link()

    def test_categorical(self):
        row={"fixture_id":"f","market":"1X2","selection":"1"}
        self.assertEqual(key(row),key({**row,"line":0}))
        with self.assertRaises(ValueError): key({**row,"line":1})

if __name__=="__main__": unittest.main()
