"""Current source, independent audit PDF and three-day A5 regression."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from github_models.three_day_a5 import summarize, build as build_three
from github_models.audit_only_pdf import build as build_audit, _validate
from github_models.report_freshness import StaleReportError


NOW = datetime(2026,11,24,13,0,tzinfo=timezone.utc)


def freeze_fixture():
    return {
        "schema": "github-models-fixture-queue-v1",
        "generated_at_utc": "2026-11-24T11:00:00Z",
        "dates": ["2026-11-24","2026-11-25","2026-11-26",
                  "2026-11-27","2026-11-28","2026-11-29","2026-11-30"],
        "fixtures": [
            {"fixture_id": "started", "home": "Old", "away": "Past",
             "league": "A", "kickoff_utc":"2026-11-24T12:00:00Z"},
            {"fixture_id": "upcoming", "home":"Home", "away":"Away",
             "league":"A", "kickoff_utc":"2026-11-24T16:00:00Z"},
            {"fixture_id":"tomorrow", "home":"Team X", "away":"Team Y",
             "league":"B", "kickoff_utc":"2026-11-25T15:00:00Z"},
            {"fixture_id":"dayafter", "home":"Team Z", "away":"Team W",
             "league":"C", "kickoff_utc":"2026-11-26T15:00:00Z"},
        ],
        "missing_dates":[], "invalid_dates":[], "partial_dates":[],
    }


def selected():
    return {
        "input_cutoff_utc": "2026-11-24T11:00:00Z",
        "candidates": [
            {"fixture_id":"started","market":"goals","selection":"over",
             "line":1.5,"model":"elo","variant":"A","probability_min":.80},
            {"fixture_id":"upcoming","market":"goals","selection":"over",
             "line":1.5,"model":"elo","variant":"A","probability_min":.86},
            {"fixture_id":"upcoming","market":"goals","selection":"over",
             "line":1.5,"model":"elo","variant":"B","probability_min":.86},
            {"fixture_id":"tomorrow","market":"1X2","selection":"1",
             "model":"elo","variant":"C","probability_min":.81},
        ],
    }


def audit_data():
    replay = {
        "schema": "github-models-oddspapi-frozen-audit-v1",
        "as_of_utc":"2026-11-24T05:00:00Z",
        "archives_processed":7, "status_counts":{"settled":20,"unresolved":3,"pending_future":40},
        "settled_selection_quotes":20, "unique_settled_fixtures":4,
        "settled_fixture_ids":["a","b","c","d"],
        "unresolved_by_market":{"corners":3},
    }
    shadow={
        "schema":"multimodel-priced-shadow-outcomes-v1",
        "status":{"settled":8,"pending":16},
        "archived_oddspapi_collections":2,
        "market_summary":{"btts":{"settled":4,"hit_rate":.5,"brier":.21},
                          "handicap":{"settled":4,"hit_rate":.25,"brier":.19}},
    }
    ready={
        "schema":"multimodel-calibration-readiness-v1",
        "abc_settled_quotes":20, "abc_distinct_settled_fixtures":4,
        "shadow_settled_quotes":8,"shadow_distinct_settled_fixtures":3,
        "combined_distinct_fixtures_exact":4,"fixtures_remaining_to_100_review":96,
        "calibration_authorized":False,"holdout_evidence_available":False,
        "model_weights_changed":False,
    }
    return replay,shadow,ready


class CurrentCycle(unittest.TestCase):
    def test_three_days_only_and_started_removed(self):
        m=summarize(freeze_fixture(),selected(),now_utc=NOW)
        self.assertEqual([x["date"] for x in m["reports"]],
                         ["2026-11-24","2026-11-25","2026-11-26"])
        self.assertEqual(m["reports"][0]["excluded_started_candidates"],1)
        self.assertEqual(m["reports"][0]["fixtures_with_candidates"],1)
        self.assertEqual(m["reports"][0]["raw_eligible_candidates"],1)
        self.assertEqual(m["reports"][0]["fixtures"][0]["market_rows"][0]["variants"],"A/B")
        self.assertEqual(m["reports"][1]["fixtures_with_candidates"],1)
        self.assertEqual(m["reports"][2]["fixtures_with_candidates"],0)
        self.assertFalse(m["odds_verified"])

    def test_three_pdf_are_real_a5_and_no_fake_bet_pricing(self):
        with tempfile.TemporaryDirectory() as path:
            m=build_three(freeze_fixture(),selected(),path,now_utc=NOW)
            files=sorted(Path(path).glob("MULTIMODEL_*.pdf"))
            self.assertEqual(len(files),3)
            for f in files:
                self.assertEqual(f.read_bytes()[:5],b"%PDF-")
                self.assertGreater(f.stat().st_size,1000)
            self.assertEqual(m["paid_api_calls"],0)

    def test_today_source_not_yesterday(self):
        q=freeze_fixture()
        q["generated_at_utc"]="2026-11-23T11:00:00Z"
        with self.assertRaisesRegex(StaleReportError,"no_fresh_abc_queue"):
            summarize(q,selected(),now_utc=NOW)

    def test_future_candidate_with_other_freeze_rejected(self):
        rows=selected()
        rows["input_cutoff_utc"]="2026-11-23T11:00:00Z"
        with self.assertRaisesRegex(StaleReportError,"abc_candidates_queue_cutoff_mismatch"):
            summarize(freeze_fixture(),rows,now_utc=NOW)

    def test_source_date_shift_does_not_create_yesterday_picks(self):
        q=freeze_fixture()
        q["dates"][0]="2026-11-23"
        with self.assertRaisesRegex(StaleReportError,"abc_queue_three_dates_mismatch"):
            summarize(q,selected(),now_utc=NOW)

    def test_no_conflicting_selection_silently_merged(self):
        rows=selected()
        rows["candidates"][2]["probability_min"] = .75
        with self.assertRaisesRegex(StaleReportError,"conflicting_abc_candidates_same_market"):
            summarize(freeze_fixture(),rows,now_utc=NOW)

    def test_missing_future_snapshot_creates_honest_empty_day(self):
        q=freeze_fixture()
        q["missing_dates"]=["2026-11-26"]
        m=summarize(q,selected(),now_utc=NOW)
        self.assertEqual(m["reports"][2]["source_status"],"source_missing")
        self.assertFalse(m["reports"][2]["fixtures"])

    def test_readonly_audit_independent_of_current_market_data(self):
        r,s,g=audit_data()
        with tempfile.TemporaryDirectory() as d:
            m=build_audit(r,s,g,Path(d)/"audit.pdf",now_utc=NOW,source_run="123")
            self.assertEqual(m["abc_settled"],20)
            self.assertEqual(m["abc_fixtures"],4)
            self.assertEqual(m["shadow_settled"],8)
            self.assertEqual(m["exact_union"],4)
            self.assertFalse(m["current_betting_recommendations"])
            self.assertEqual((Path(d)/"audit.pdf").read_bytes()[:5],b"%PDF-")

    def test_audit_rejects_inconsistent_samples(self):
        r,s,g=audit_data()
        g["abc_distinct_settled_fixtures"]=7
        with self.assertRaisesRegex(ValueError,"replay_calibration_fixture_count_mismatch"):
            _validate(r,s,g,now=NOW)

    def test_audit_not_future_or_auto_calibration(self):
        r,s,g=audit_data()
        g["calibration_authorized"]=True
        with self.assertRaisesRegex(ValueError,"unexpected_automated_calibration"):
            _validate(r,s,g,now=NOW)
        g["calibration_authorized"]=False
        r["as_of_utc"]="2026-11-25T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"future_audit"):
            _validate(r,s,g,now=NOW)

    def test_live_abc_source_guard_rejects_old_freeze_and_writes_evidence(self):
        import json
        import os
        import subprocess
        import sys
        from textwrap import dedent
        from zoneinfo import ZoneInfo
        workflow=(Path(__file__).resolve().parents[1] /
                  ".github/workflows/github-models-v2-daily-audit.yml").read_text(encoding="utf-8")
        marker="- name: Verify Warsaw-day frozen ABC queue and preserve source health"
        self.assertIn(marker,workflow)
        body=workflow.split(marker,1)[1].split("python - <<'PY'",1)[1].split("PY",1)[0]
        script=dedent(body)
        compile(script,"workflow_abc_source_guard.py","exec")
        now=datetime.now(timezone.utc)
        local=now.astimezone(ZoneInfo("Europe/Warsaw")).date()
        q={"schema":"github-models-fixture-queue-v1",
           "generated_at_utc":now.isoformat(),
           "dates":[str(local+timedelta(days=i)) for i in range(7)],
           "fixtures":[]}
        with tempfile.TemporaryDirectory() as folder:
            work=Path(folder)
            src=work/"reports/github_models/queues"/(str(local)+".json")
            src.parent.mkdir(parents=True)
            src.write_text(json.dumps(q),encoding="utf-8")
            env=dict(os.environ,FROZEN_AT=now.isoformat())
            run=subprocess.run([sys.executable,"-c",script],env=env,cwd=folder,
                               text=True,capture_output=True)
            self.assertEqual(run.returncode,0,run.stderr+run.stdout)
            out=work/"reports/github_models/coverage"/("CYCLE_SOURCE_HEALTH_"+str(local)+".json")
            evidence=json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(evidence["status"],"NO_TODAY_FIXTURES_BUT_FUTURE_DATES_VALID")
            self.assertEqual(evidence["paid_oddspapi_calls"],0)
            prior=now-timedelta(days=1)
            q["generated_at_utc"]=prior.isoformat()
            src.write_text(json.dumps(q),encoding="utf-8")
            stale=subprocess.run([sys.executable,"-c",script],cwd=folder,
                                 env=dict(os.environ,FROZEN_AT=prior.isoformat()),
                                 text=True,capture_output=True)
            self.assertNotEqual(stale.returncode,0)
            self.assertIn("ABC_SOURCE_BLOCKED",stale.stderr+stale.stdout)

    def test_collector_day_gate_runs_before_paid_calls(self):
        root=Path(__file__).resolve().parents[1]
        y=(root/".github/workflows/oddspapi-daily.yml").read_text()
        self.assertIn("warsaw_day",y)
        self.assertIn("no_paid_api_calls",y)
        self.assertIn("6*3600",y)
        self.assertLess(y.index("Select complete recent forecast queue"), y.index("Collect only Superbet.pl"))
        self.assertLess(y.index("no_paid_api_calls"),y.index("Collect only Superbet.pl"))

    def test_independent_audit_and_three_day_workflows_are_readonly(self):
        root=Path(__file__).resolve().parents[1]
        for filename in ("multimodel-independent-audit-pdf.yml","multimodel-three-day-a5.yml"):
            s=(root/".github/workflows"/filename).read_text()
            self.assertIn("workflow_run:",s)
            self.assertIn("actions: read",s)
            self.assertNotIn("ODDSPAPI_API_KEY",s)
            self.assertNotIn("PITCHAPI_API_KEY",s)


if __name__=="__main__":
    unittest.main()
