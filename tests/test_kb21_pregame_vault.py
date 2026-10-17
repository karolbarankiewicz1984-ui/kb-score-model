"""Early KNVB/FPL snapshots are durable diagnostics, never automatic PLAY."""
import datetime as dt
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.kb21_pregame_vault import (
    SCHEMA, package, verify, match_before_whole_day_start, restore
)

DAY = "2026-10-18"
DAYS = [DAY, "2026-10-19", "2026-10-20"]


def knvb(captured="2026-10-18T04:00:00+00:00", kickoff="2026-10-18T10:15:00+00:00"):
    return {
        "schema": "kb21-official-knvb-eredivisie-v1", "league_id": "ned.1",
        "days": DAYS, "captured_at_utc": captured,
        "calendar_gate": "BLOCKED", "reviewer_signed": False,
        "full_calendar_verified": False,
        "status": "OFFICIAL_KNVB_PAGE_PARTIAL_FOR_REVIEW",
        "errors": [], "by_day": {
            DAYS[0]: [{"home": "ADO Den Haag", "away": "PSV",
                       "kickoff_utc": kickoff}],
            DAYS[1]: [], DAYS[2]: [],
        },
    }


def fpl(captured="2026-10-18T04:00:00+00:00"):
    return {
        "schema": "kb21-official-premier-league-fpl-v1", "league_id": "eng.1",
        "days": DAYS, "captured_at_utc": captured,
        "calendar_gate": "BLOCKED", "reviewer_signed": False,
        "full_calendar_verified": False, "season_full_380_catalogue": True,
        "errors": [], "by_day": {
            DAYS[0]: [{"home": "Arsenal", "away": "Chelsea",
                       "kickoff_utc": "2026-10-18T14:00:00+00:00",
                       "kickoff_provisional": False}],
            DAYS[1]: [], DAYS[2]: [],
        },
    }


def queue():
    return {
        "days": DAYS, "fixtures": [
            {"date_warsaw": DAY, "fixture_id": "ned.1:1",
             "fixture": "ADO Den Haag - PSV",
             "kickoff": "2026-10-18T12:15:00+02:00"},
            {"date_warsaw": DAY, "fixture_id": "eng.1:2",
             "fixture": "Arsenal - Chelsea",
             "kickoff": "2026-10-18T16:00:00+02:00"},
        ],
    }


def write_snapshots(root, knvb_doc=None, fpl_doc=None):
    for name, obj in [("knvb", knvb_doc), ("fpl", fpl_doc)]:
        if obj:
            Path(root, name + "-input.json").write_text(json.dumps(obj))
    return {name: Path(root, name + "-input.json")
            for name, obj in [("knvb", knvb_doc), ("fpl", fpl_doc)] if obj}


class EarlyVaultTests(unittest.TestCase):
    def test_package_and_verify_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = write_snapshots(tmp, knvb(), fpl())
            archive = Path(tmp, "archive")
            manifest = package(DAYS, src, archive,
                               dt.datetime(2026, 10, 18, 4, 5,
                                           tzinfo=dt.timezone.utc))
            self.assertEqual(manifest["schema"], SCHEMA)
            self.assertEqual(set(manifest["sources"]), {"knvb", "fpl"})
            self.assertFalse(manifest["official_day_completeness_verified"])
            self.assertEqual(manifest["prematch_status"],
                             "NOT_ESTABLISHED_UNTIL_INDEPENDENT_KICKOFF_CHECK")
            verified, docs = verify(archive)
            self.assertEqual(docs["knvb"]["by_day"][DAY][0]["away"], "PSV")
            self.assertIsNone(verified["human_approval"])
            with open(archive / "knvb.json", "a") as handle:
                handle.write(" ")
            with self.assertRaisesRegex(ValueError, "checksum"):
                verify(archive)

    def test_same_day_earlier_snapshot_matching_is_only_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = write_snapshots(tmp, knvb(), fpl())
            path = Path(tmp, "snapshot")
            package(DAYS, src, path, dt.datetime(2026, 10, 18, 4, 5,
                                                tzinfo=dt.timezone.utc))
            pairs = match_before_whole_day_start(queue(), [path])
        self.assertEqual(len(pairs), 2)
        self.assertTrue(all(
            r["status"] == "EARLY_SNAPSHOT_MATCHED_FOR_REVIEW"
            for r in pairs.values()))
        self.assertTrue(all(r["prematch_clock_review_only"] for r in pairs.values()))
        self.assertTrue(all(r["calendar_gate"] == "BLOCKED" for r in pairs.values()))

    def test_capture_after_first_start_does_not_retroactively_verify_later_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = write_snapshots(tmp, knvb("2026-10-18T12:00:00Z"),
                                  fpl("2026-10-18T12:00:00Z"))
            path = Path(tmp, "snapshot")
            package(DAYS, src, path, dt.datetime(2026, 10, 18, 12, 2,
                                                tzinfo=dt.timezone.utc))
            pairs = match_before_whole_day_start(queue(), [path])
        self.assertEqual({r["status"] for r in pairs.values()},
                         {"NO_ELIGIBLE_EARLY_OFFICIAL_CAPTURE"})

    def test_source_is_before_late_match_but_after_earliest_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            # The independent EPL match is at 14:00 UTC, but KNVB starts 10:15;
            # 11:00 UTC is too late for certification of the entire day.
            src = write_snapshots(tmp, fpl("2026-10-18T11:00:00Z"))
            path = Path(tmp, "snapshot")
            package(DAYS, src, path, dt.datetime(2026, 10, 18, 11, 2,
                                                tzinfo=dt.timezone.utc))
            results = match_before_whole_day_start(queue(), [path])
        self.assertEqual(results[(DAY, "eng.1:2")]["status"],
                         "NO_ELIGIBLE_EARLY_OFFICIAL_CAPTURE")

    def test_incomplete_independent_start_or_nonmatching_official_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = write_snapshots(tmp, knvb(kickoff="2026-10-18T10:30:00Z"))
            path = Path(tmp, "snapshot")
            package(DAYS, src, path, dt.datetime(2026, 10, 18, 4, 5,
                                                tzinfo=dt.timezone.utc))
            pairs = match_before_whole_day_start(queue(), [path])
            self.assertEqual(pairs[(DAY, "ned.1:1")]["status"],
                             "EARLY_ORGANIZER_KICKOFF_CONFLICT")
            changed = queue()
            changed["fixtures"][1]["kickoff"] = None
            result = match_before_whole_day_start(changed, [path])
            self.assertEqual(result[(DAY, "ned.1:1")]["status"],
                             "NO_SAFE_ENTIRE_DAY_KICKOFF_WINDOW")

    def test_reject_approved_source_scope_and_future_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = knvb()
            bad["calendar_gate"] = "PASS_MANUAL"
            source = write_snapshots(tmp, bad)
            with self.assertRaisesRegex(ValueError, "safety"):
                package(DAYS, source, Path(tmp, "output"))
            future = write_snapshots(tmp, knvb("2026-10-19T11:00:00+00:00"))
            with self.assertRaisesRegex(ValueError, "future"):
                package(DAYS, future, Path(tmp, "output"),
                        dt.datetime(2026, 10, 18, 4,
                                    tzinfo=dt.timezone.utc))

    def test_restore_ignores_foreign_branch_and_checks_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = write_snapshots(tmp, knvb())
            package(DAYS, inputs, Path(tmp, "pack"),
                    dt.datetime(2026, 10, 18, 4, 5,
                                tzinfo=dt.timezone.utc))
            zipped = io.BytesIO()
            with zipfile.ZipFile(zipped, "w") as z:
                for name in ("manifest.json", "knvb.json"):
                    z.write(Path(tmp, "pack", name), name)
            entries = json.dumps({"artifacts": [
                {"id": 11, "name": "kb21-early-organizer-11",
                 "created_at": "2026-10-18T04:05:00Z",
                 "expired": False,
                 "workflow_run": {"head_branch": "main"}},
                {"id": 12, "name": "kb21-early-organizer-12",
                 "created_at": "2026-10-18T04:05:00Z",
                 "expired": False,
                 "workflow_run": {"head_branch": "untrusted"}},
            ]}).encode()
            class Reply(io.BytesIO):
                pass
            def opener(req, timeout):
                return Reply(zipped.getvalue() if req.full_url.endswith("/11/zip")
                             else entries)
            restored = restore("user/repo", Path(tmp, "restored"),
                               "token", opener=opener,
                               now=dt.datetime(2026, 10, 18, 6,
                                               tzinfo=dt.timezone.utc))
            self.assertEqual(len(restored), 1)
            self.assertEqual(verify(restored[0])[1]["knvb"]["days"], DAYS)


if __name__ == "__main__":
    unittest.main()
