"""Attach six partial official source snapshots to an UNSIGNED KB21 review draft.

Four UEFA league-phase articles carry only date/club hints (no verified
timezone); Belgium shows an undated selected round; European Qualifiers have
historical edition information only. These MUST NOT enter a signed fixture
inventory or be misinterpreted as proof of an empty day.

The draft is never promoted, validated, signed, or used as PLAY evidence.
"""
import argparse
import copy
import json
from pathlib import Path

from tools.kb21_fixture_crosscheck import _instant
from tools.kb21_official_uefa_articles import SOURCES as UEFA_URLS
from tools.kb21_official_belgium import SOURCE as BELGIUM_URL
from tools.kb21_official_uefa_qualifiers_cycle import (
    SOURCE as QUALIFIERS_URL, EDITION,
)

SOURCES = {
    **{league: ("kb21-official-uefa-league-phase-v1", url,
                "DATE_CLUB_ONLY_UNVERIFIED_KICKOFF")
       for league, url in UEFA_URLS.items()},
    "bel.1": ("kb21-official-belgium-selected-round-v1",
              BELGIUM_URL, "UNDATED_SELECTED_ROUND_ONLY"),
    "fifa.worldq.uefa": ("kb21-official-uefa-2026-qualifiers-cycle-v1",
                        QUALIFIERS_URL, "HISTORICAL_EDITION_CONTEXT_ONLY"),
}


def attach(draft, sources):
    if (not isinstance(draft, dict) or not isinstance(draft.get("days"), dict)
            or draft.get("approval") is not None):
        raise ValueError("Expected unsigned manual organizer draft")
    days = sorted(draft["days"])
    if not 1 <= len(days) <= 3:
        raise ValueError("Expected one to three organizer review days")
    daily_approvals = draft.get("daily_approvals") or {}
    if (not isinstance(daily_approvals, dict)
            or any(value is not None for value in daily_approvals.values())):
        raise ValueError("Refuse partial evidence overlay on signed daily reviews")
    out = copy.deepcopy(draft)
    counts = {}
    for league, src in sources.items():
        if league not in SOURCES or not isinstance(src, dict):
            raise ValueError("Unexpected partial organizer evidence source")
        schema, url, kind = SOURCES[league]
        if (src.get("schema") != schema or src.get("league_id") != league
                or src.get("official_url") != url
                or set(src.get("days", [])) != set(days)
                or not isinstance(src.get("by_day"), dict)
                or set(src["by_day"]) != set(days)
                or src.get("calendar_gate") != "BLOCKED"
                or src.get("full_calendar_verified") is not False
                or src.get("kickoff_timezone_verified") is not False
                or src.get("reviewer_signed") is not False
                or _instant(src.get("captured_at_utc")) is None):
            raise ValueError("Partial organizer source identity/status/scope invalid")
        if league == "fifa.worldq.uefa":
            if (src.get("edition") != EDITION
                    or src.get("confirmed_zero_matches") is not False
                    or src.get("date_verified") is not False):
                raise ValueError("Qualifiers historical edition cannot attest a calendar")
        if league == "bel.1" and src.get("date_verified") is not False:
            raise ValueError("Belgian undated source cannot attest a date")
        if not isinstance(src.get("errors"), list):
            raise ValueError("Missing official fetch/parse error list")
        count = 0
        for day in days:
            slot = out["days"][day].get(league)
            if not isinstance(slot, dict):
                raise ValueError("Missing review slot for partial organizer source")
            if (slot.get("reviewer") or slot.get("captured_at")
                    or slot.get("full_day_checked") is True
                    or slot.get("confirmed_zero_matches") is True):
                raise ValueError("Refuse to add partial source hints to reviewed slot")
            if src["by_day"][day] != [] and league in {"bel.1", "fifa.worldq.uefa"}:
                raise ValueError("Undated or historical evidence cannot claim dated rows")
            hints = []
            if league in UEFA_URLS:
                rows = src["by_day"][day]
                if not isinstance(rows, list):
                    raise ValueError("UEFA official date/club rows must be list")
                for row in rows:
                    if (not isinstance(row, dict) or row.get("date_printed") != day
                            or row.get("league_id") != league
                            or row.get("kickoff_timezone_verified") is not False
                            or not isinstance(row.get("home"), str)
                            or not isinstance(row.get("away"), str)
                            or not row["home"].strip() or not row["away"].strip()):
                        raise ValueError("Unsafe UEFA article fixture hint")
                    hints.append({
                        "home": row["home"], "away": row["away"],
                        "date_printed": day,
                        "printed_kickoff_unverified": row.get("printed_kickoff"),
                        "clock_verified": False,
                    })
            elif league == "bel.1":
                for row in src.get("undated_fixtures", []):
                    if (not isinstance(row, dict)
                            or row.get("date_warsaw") is not None
                            or row.get("kickoff_warsaw") is not None
                            or not isinstance(row.get("home"), str)
                            or not isinstance(row.get("away"), str)
                            or not row["home"].strip() or not row["away"].strip()):
                        raise ValueError("Belgian selected-round fixture is not dated")
                    hints.append({"home": row["home"], "away": row["away"],
                                  "selected_round": row.get("selected_round"),
                                  "date_warsaw": None, "clock_verified": False})
            else:
                if not isinstance(src.get("day_cycle_status"), dict):
                    raise ValueError("Missing historical qualifier cycle status")
                hints.append({
                    "edition": EDITION,
                    "day_cycle_status": src["day_cycle_status"].get(day),
                    "documented_last_playoff_day": src.get("documented_last_playoff_day"),
                    "zero_games_certified": False,
                })
            if "partial_official_source_hints" in slot:
                raise ValueError("Do not overwrite prior partial source evidence")
            slot["partial_official_source_hints"] = {
                "kind": kind, "source": url,
                "captured_at_utc": src["captured_at_utc"],
                "source_status": src.get("status"),
                "source_errors": src["errors"],
                "date_and_kickoff_authenticated": False,
                "organizer_full_day_attested": False,
                "confirmed_no_matches": False,
                "fixture_hints": hints,
            }
            # No mutations of fixtures, captured_at, reviewer,
            # full_day_checked, confirmed_zero_matches or daily approvals.
            count += len(hints) if league != "bel.1" else 0
        counts[league] = count if league != "bel.1" else len(src.get("undated_fixtures", []))
    out["partial_official_hints_summary"] = {
        "sources_attached": len(sources), "hints_by_source": counts,
        "official_days_signed": 0,
    }
    out["calendar_gate"] = "BLOCKED"
    out["publication"] = "DIAGNOSTIC / NO PLAY"
    out["approval"] = None
    out["partial_official_hints_note"] = (
        "Official article dates/teams, undated Belgian round and historical "
        "qualifying context are EXCLUSIVELY unsigned review hints; they cannot "
        "complete the fixture inventory or confirm a zero-match day. Do not "
        "use them as signed fixtures, clock validation or LIVE KB Score."
    )
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("draft")
    p.add_argument("--uefa-champions")
    p.add_argument("--uefa-europa")
    p.add_argument("--uefa-conference")
    p.add_argument("--uefa-nations")
    p.add_argument("--belgium")
    p.add_argument("--qualifiers")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    filenames = {
        "uefa.champions": a.uefa_champions,
        "uefa.europa": a.uefa_europa,
        "uefa.europa.conf": a.uefa_conference,
        "uefa.nations": a.uefa_nations,
        "bel.1": a.belgium,
        "fifa.worldq.uefa": a.qualifiers,
    }
    sources = {code: json.loads(Path(file).read_text(encoding="utf-8"))
               for code, file in filenames.items() if file}
    data = attach(json.loads(Path(a.draft).read_text(encoding="utf-8")), sources)
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print("KB21 partial official hints:", data["partial_official_hints_summary"],
          "NO PLAY")


if __name__ == "__main__":
    main()
