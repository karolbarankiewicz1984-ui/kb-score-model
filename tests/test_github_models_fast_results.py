import unittest
from github_models.fast_final_parser import parse_final, parse_stats
from github_models.fast_final_collect import collect

HISTORY = [{"fixture_id":"prior-1","league":"Premier League","country_code":"ENG",
    "home":"Arsenal","away":"Chelsea","home_goals":1,"away_goals":1,
    "completed_at_utc":"2026-10-01T18:00:00Z","published_at_utc":"2026-10-03T00:00:00Z"}]
MATCH = {"fixture":{"id":12345,"date":"2026-11-06T20:00:00Z","status":{"short":"FT"}},
         "league":{"name":"Premier League","country":"England"},
         "teams":{"home":{"id":10,"name":"Arsenal"},"away":{"id":11,"name":"Chelsea"}},
         "goals":{"home":2,"away":1},
         "score":{"fulltime":{"home":2,"away":1}}}
OBSERVED = "2026-11-07T09:00:00Z"

class FastResultsTests(unittest.TestCase):
    def test_frozen_scores_are_not_backdated(self):
        row = parse_final(MATCH,HISTORY,OBSERVED)
        self.assertEqual(row["match_date"],"2026-11-06")
        self.assertEqual(row["completed_at_utc"],OBSERVED)
        self.assertEqual(row["published_at_utc"],OBSERVED)
        self.assertEqual((row["home_goals"],row["away_goals"]),(2,1))
        self.assertEqual(row["source_provider"],"API-Football")
    def test_in_progress_is_not_settled(self):
        match={**MATCH,"fixture":{**MATCH["fixture"],"status":{"short":"2H"}}}
        with self.assertRaises(ValueError):
            parse_final(match,HISTORY,OBSERVED)
    def test_conflicting_scores_blocked(self):
        match={**MATCH,"score":{"fulltime":{"home":1,"away":1}}}
        with self.assertRaisesRegex(ValueError,"conflicting_final_score"):
            parse_final(match,HISTORY,OBSERVED)
    def test_stats_from_exact_provider_team_ids(self):
        response=[{"team":{"id":11},"statistics":[{"type":"Fouls","value":12},{"type":"Yellow Cards","value":3}]},
                  {"team":{"id":10},"statistics":[{"type":"Fouls","value":7},{"type":"Yellow Cards","value":1}]}]
        out=parse_stats(response,MATCH)
        self.assertEqual(out["fouls"],[7,12])
        self.assertEqual(out["cards"],[1,3])
        self.assertNotIn("corners",out)
    def test_missing_secret_leaves_history_untouched(self):
        rows,ev,meta=collect(HISTORY,[],"",["2026-11-06"])
        self.assertEqual(rows,HISTORY)
        self.assertEqual(ev,[])
        self.assertEqual(meta["status"],"missing_key")
    def test_observed_finals_added_only_for_settlement(self):
        response=[{"team":{"id":10},"statistics":[{"type":"Corner Kicks","value":4}]},
                  {"team":{"id":11},"statistics":[{"type":"Corner Kicks","value":7}]}]
        def get(endpoint,params,key):
            return ([MATCH] if endpoint=="fixtures" else response),"sha"
        rows,events,meta=collect(HISTORY,[],"test",["2026-11-06"],max_stats=4,getter=get)
        self.assertEqual(len(rows),2)
        self.assertEqual(events[0]["events"]["corners"],[4,7])
        self.assertEqual(meta["accepted_scores"],1)
    def test_identical_prior_final_does_not_duplicate(self):
        prior={**HISTORY[0],"match_date":"2026-11-06","home_goals":2,"away_goals":1}
        def get(endpoint,params,key):
            return ([MATCH] if endpoint=="fixtures" else []),"sha"
        rows,events,meta=collect([prior],[],"test",["2026-11-06"],max_stats=0,getter=get)
        self.assertEqual(rows,[prior])
        self.assertEqual(meta["corroborated_existing_scores"],1)

    def test_reviewed_provider_aliases_are_league_scoped(self):
        from github_models.reviewed_resolver import resolve_reviewed
        cases=[("Romanian Superliga","ROU","Petrolul Ploiesti","Petrolul"),
               ("Romanian Superliga","ROU","Arges Pitesti","FC Arges"),
               ("Russian Premier League","RUS","Lokomotiv","Lokomotiv Moscow"),
               ("2. Bundesliga","DEU","SpVgg Greuther Fürth","Greuther Furth"),
               ("Allsvenskan","SWE","Hammarby FF","Hammarby"),
               ("Austrian Bundesliga","AUT","Rapid Vienna","SK Rapid"),
               ("Ligue 2","FRA","RED Star FC 93","Red Star"),
               ("Ekstraklasa","POL","Cracovia Krakow","Cracovia")]
        for league,country,alias,target in cases:
            with self.subTest(alias=alias):
                history=[{"league":league,"country_code":country,"home":target,"away":"Other Team"}]
                fixture={"league":league,"country_code":country,"home":alias,"away":"Other Team"}
                self.assertEqual(resolve_reviewed(fixture,history)["home"],target)

if __name__ == "__main__":
    unittest.main()
