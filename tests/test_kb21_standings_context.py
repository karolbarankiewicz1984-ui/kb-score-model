"""League-table evidence may inform research, never impersonate KB21 ELO/P(model)."""
from copy import deepcopy
from datetime import timedelta
import unittest

from tests.test_kb21_single_source_form import base_calendar, TeamsClient, NOW
from tools.kb21_single_source_form import build_source_pack
from tools.kb21_standings_context import parse_standings, build, render_day


def table_row(team_id, rank, played, wins, draws, losses):
    assert wins+draws+losses == played
    return {
        "rank":rank,"team":{"id":team_id,"name":f"Team {team_id}"},
        "points":3*wins+draws,"goalsDiff":wins-losses,
        "all":{"played":played,"win":wins,"draw":draws,"lose":losses},
        "home":{"played":played,"win":wins,"draw":draws,"lose":losses},
        "away":{"played":0,"win":0,"draw":0,"lose":0},
    }


def response(rows=None, league=39, season=2026, groups=None):
    return {
        "get":"standings",
        "parameters":{"league":str(league),"season":str(season)},
        "errors":[],"results":1,
        "response":[{"league":{"id":league,"season":season,
                    "standings":groups if groups is not None else [rows or []]}}],
    }


class StandingsClient:
    def __init__(self, rows=None, headers=None, broken=False):
        self.rows=rows or [table_row(1,1,8,7,0,1),
                           table_row(2,5,8,3,2,3),
                           table_row(1001,8,8,2,1,5)]
        self.headers=headers or {"x-ratelimit-requests-remaining":"400"}
        self.broken=broken
        self.calls=[]
    def get(self, base, key, endpoint, **params):
        self.calls.append((base,key,endpoint,params))
        if endpoint!="standings" or set(params)!={"league","season"}:
            raise ValueError("Only league/season standings allowed")
        if self.broken:
            raise RuntimeError("Provider inaccessible")
        return response(self.rows,params["league"],params["season"]),self.headers


def inputs(now=NOW):
    manifest,calendars=base_calendar()
    forms=build_source_pack(manifest,calendars,TeamsClient(),"key",now=now)
    form_manifest={k:v for k,v in forms.items() if k!="days"}
    data={x["day"]:x for x in forms["days"]}
    return manifest,calendars,form_manifest,data


class StandingsTests(unittest.TestCase):
    def test_valid_table_points_ppg_and_exact_provider_identity(self):
        d,_=parse_standings(response([
            table_row(1,1,8,7,0,1),table_row(2,5,8,3,2,3)]),39,2026)
        self.assertEqual(d[1]["points_per_game"],2.625)
        self.assertEqual(d[2]["points_per_game"],1.375)
        self.assertEqual(d[1]["rank"],1)
        self.assertEqual(d[2]["home"]["played"],8)
        self.assertIsNone(d[2]["away"]["points_per_game"])

    def test_reject_provider_error_wrong_league_and_duplicate_team(self):
        a=response([table_row(1,1,8,7,0,1)])
        a["errors"]={"provider":"plan"}
        self.assertEqual(parse_standings(a,39,2026)[1],"PROVIDER_ERROR")
        self.assertEqual(parse_standings(response(),40,2026)[1],
                         "WRONG_LEAGUE_OR_SEASON")
        b=response([table_row(1,1,8,7,0,1),table_row(1,2,8,3,2,3)])
        self.assertEqual(parse_standings(b,39,2026)[1],
                         "MALFORMED_PROVIDER_RESPONSE")
        self.assertEqual(parse_standings(response([]),39,2026)[1],
                         "STANDINGS_NOT_AVAILABLE")

    def test_malformed_stats_are_not_converted_into_strength(self):
        b=response([table_row(1,1,8,7,0,1)])
        b["response"][0]["league"]["standings"][0][0]["all"]["played"]=12
        self.assertEqual(parse_standings(b,39,2026)[1],
                         "MALFORMED_PROVIDER_RESPONSE")

    def test_only_one_call_per_unique_league_across_two_days(self):
        m,cs,fm,fs=inputs()
        client=StandingsClient()
        doc=build(m,cs,fm,fs,client,"key",now=NOW+timedelta(minutes=2))
        self.assertEqual(len(client.calls),1)
        self.assertEqual(doc["standings_calls"],1)
        self.assertEqual(doc["verified_table_pairs"],2)
        self.assertEqual(doc["candidate_matches"],2)
        self.assertFalse(doc["register_writes"])
        self.assertEqual(doc["automatic_p_model_count"],0)
        self.assertEqual(doc["automatic_str_qual_match_count"],0)
        self.assertFalse(doc["safe_to_publish_play"])
        for day in doc["days_output"]:
            entry=day["matches"][0]
            self.assertEqual(entry["status"],"CURRENT_SEASON_TABLE_CONTEXT")
            self.assertEqual(entry["home"]["team_id"],1)
            self.assertEqual(entry["away"]["team_id"],2)
            self.assertEqual(entry["current_rank_gap"],4)
            self.assertEqual(entry["current_ppg_gap_home_minus_away"],1.25)
            self.assertIsNone(entry["original_p_model"])
            self.assertIsNone(entry["elo"])
            self.assertIsNone(entry["xg"])
            self.assertIsNone(entry["str_35"])
            self.assertIsNone(entry["decision"])
            self.assertIn("NIE ELO",render_day(day))

    def test_prior_opponent_current_ppg_is_not_historical_strength(self):
        m,cs,fm,fs=inputs()
        for row in fs["2026-10-18"]["matches"][0]["history"]["home"]["sport_evidence"]["previous_ft_matches"][:5]:
            row.update(opponent_team_id=1001,history_league_id=39,history_season=2026)
        doc=build(m,cs,fm,fs,StandingsClient(),"key",now=NOW+timedelta(minutes=1))
        context=doc["days_output"][0]["matches"][0]["recent_opponent_context"]["home"]
        self.assertEqual(context["qualified_last_five"],5)
        self.assertEqual(context["mean_current_opponent_ppg"],0.875)
        self.assertIn("NOT point-in-time",context["warning"])

    def test_non_domestic_competitions_do_not_query_table(self):
        m,cs,fm,fs=inputs()
        for day in m["dates"]:
            event=cs[day]["candidates"][0]
            event["league"]="UEFA Champions League"
            event["country"]="World"
            fs[day]["matches"][0]["league"]="UEFA Champions League"
        client=StandingsClient()
        result=build(m,cs,fm,fs,client,"key",now=NOW+timedelta(minutes=1))
        self.assertEqual(client.calls,[])
        self.assertEqual(result["verified_table_pairs"],0)
        self.assertTrue(all(x["status"]=="NOT_A_DOMESTIC_TABLE_MATCH"
                            for d in result["days_output"] for x in d["matches"]))

    def test_forecast_started_no_late_table_context(self):
        m,cs,fm,fs=inputs()
        now=NOW+timedelta(hours=10)
        res=build(m,cs,fm,fs,StandingsClient(),"key",now=now)
        self.assertEqual(res["days_output"][0]["matches"][0]["status"],
                         "NO_LATE_SNAPSHOT_AFTER_KICKOFF")

    def test_missing_team_never_joins_by_name_or_weak_similarity(self):
        m,cs,fm,fs=inputs()
        client=StandingsClient([table_row(1,1,8,7,0,1)])
        r=build(m,cs,fm,fs,client,"key",now=NOW+timedelta(minutes=2))
        self.assertEqual(r["verified_table_pairs"],0)
        self.assertEqual(r["days_output"][0]["matches"][0]["status"],
                         "ONE_OR_BOTH_TEAMS_MISSING_FROM_STANDINGS")

    def test_provider_failure_is_diagnostic_not_fake_value(self):
        m,cs,fm,fs=inputs()
        client=StandingsClient(broken=True)
        doc=build(m,cs,fm,fs,client,"key",now=NOW+timedelta(minutes=2))
        self.assertEqual(doc["standings_calls"],1)
        self.assertEqual(doc["verified_table_pairs"],0)
        self.assertEqual(doc["days_output"][0]["matches"][0]["status"],
                         "STANDINGS_REQUEST_FAILED")

    def test_quota_reserve_and_global_budget(self):
        m,cs,fm,fs=inputs()
        client=StandingsClient(headers={"x-ratelimit-requests-remaining":"25"})
        r=build(m,cs,fm,fs,client,"key",now=NOW+timedelta(minutes=2),
                max_calls=1,reserve=25)
        self.assertEqual(r["standings_calls"],1)
        self.assertEqual(r["daily_api_remaining"],25)
        for bad in (0,17,False):
            with self.assertRaisesRegex(ValueError,"capped standings budget"):
                build(m,cs,fm,fs,client,"key",now=NOW,max_calls=bad)

    def test_wrong_form_id_and_odds_rejected(self):
        m,cs,fm,fs=inputs()
        changed=deepcopy(fs)
        changed["2026-10-18"]["matches"][0]["home_team_id"]=999
        with self.assertRaisesRegex(ValueError,"identical"):
            build(m,cs,fm,changed,StandingsClient(),"key",now=NOW)
        changed=deepcopy(fs)
        changed["2026-10-18"]["matches"][0]["odds"]=1.8
        with self.assertRaisesRegex(ValueError,"identical"):
            build(m,cs,fm,changed,StandingsClient(),"key",now=NOW)

    def test_refuse_form_time_in_future(self):
        m,cs,fm,fs=inputs()
        fm["generated_at_utc"]=(NOW+timedelta(hours=4)).isoformat()
        with self.assertRaisesRegex(ValueError,"future-dated"):
            build(m,cs,fm,fs,StandingsClient(),"key",now=NOW)

if __name__=="__main__":
    unittest.main()
