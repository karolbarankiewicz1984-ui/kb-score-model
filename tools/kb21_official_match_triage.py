"""Read source-vs-ESPN comparisons as per-fixture UNSIGNED review evidence.

Do not infer a fixture or its kickoff from empty/sampled round pages. Each
comparator remains a diagnostic and may identify only some games; output can
never certify full organizer day, zero games, or Calendar Gate PASS.
"""
import json
from pathlib import Path

from tools.kb21_calendar_evidence_dashboard import ADAPTERS


ID_FIELDS = ("espn_fixture_id", "fixture_id", "candidate_id")
KICKOFF_FIELDS = (
    "fpl_kickoff", "organizer_kickoff", "knvb_kickoff",
    "tff_kickoff", "club_article_kickoff_warsaw",
)


def collect(queue, sources_dir):
    if (not isinstance(queue, dict) or not isinstance(queue.get("days"), list)
            or not isinstance(queue.get("fixtures"), list)):
        raise ValueError("Invalid KB21 candidate queue")
    days = queue["days"]
    if len(set(days)) != len(days) or not 1 <= len(days) <= 3:
        raise ValueError("Invalid KB21 dates")
    identities = {}
    for fixture in queue["fixtures"]:
        if not isinstance(fixture, dict):
            raise ValueError("Invalid fixture")
        fixture_id = fixture.get("fixture_id")
        if not isinstance(fixture_id, str) or ":" not in fixture_id:
            raise ValueError("Invalid fixture id")
        key = fixture.get("date_warsaw"), fixture_id
        if key in identities:
            raise ValueError("Duplicate fixture ID in scoped queue")
        identities[key] = fixture
    folder = Path(sources_dir)
    results = {
        key: {
            "organizer_comparator_status": "NO_COMPARATOR_RECORD",
            "official_kickoff_claim": None,
            "kickoff_evidence_validated_by_signoff": False,
            "comparison_file": ADAPTERS[fixture["fixture_id"].rsplit(":", 1)[0]][0]
            if fixture["fixture_id"].rsplit(":", 1)[0] in ADAPTERS else None,
        }
        for key, fixture in identities.items()
    }
    for league, (filename, _, kind) in ADAPTERS.items():
        file = folder / filename
        if not file.is_file():
            for key in results:
                if key[1].startswith(league + ":"):
                    results[key]["organizer_comparator_status"] = "COMPARATOR_NOT_AVAILABLE"
            continue
        data = json.loads(file.read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or data.get("calendar_gate") != "BLOCKED"
                or not isinstance(data.get("days"), dict)
                or set(data["days"]) != set(days)):
            raise ValueError("Invalid/signed/mismatched organizer comparator: " + filename)
        for day in days:
            day_data = data["days"][day]
            if not isinstance(day_data, dict):
                raise ValueError("Invalid per-day organizer comparison")
            rows = day_data.get("comparisons", [])
            if not isinstance(rows, list):
                raise ValueError("Invalid per-game organizer comparison")
            seen = set()
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError("Invalid per-game result")
                ids = [row.get(field) for field in ID_FIELDS if row.get(field) is not None]
                if not ids or not isinstance(ids[0], str):
                    raise ValueError("Comparator has no usable candidate ID")
                if len(set(map(str, ids))) != 1:
                    raise ValueError("Comparator candidate identifiers disagree")
                key = day, ids[0]
                if not key[1].startswith(league + ":") or key not in identities:
                    raise ValueError("Comparator refers to unknown or misdated fixture")
                if key in seen:
                    raise ValueError("Comparator duplicates fixture result")
                seen.add(key)
                status = row.get("status")
                if not isinstance(status, str) or not status.strip():
                    raise ValueError("Missing comparator status")
                times = [row.get(field) for field in KICKOFF_FIELDS
                         if row.get(field) is not None]
                if len(set(map(str, times))) > 1:
                    raise ValueError("Contradictory organizer kickoff within comparator")
                official_time = times[0] if times else None
                results[key] = {
                    "organizer_comparator_status": status,
                    # Raw source text, never promoted to signed kickoff or score.
                    "official_kickoff_claim": official_time,
                    "kickoff_evidence_validated_by_signoff": False,
                    "comparison_file": filename, "source_evidence_role": kind,
                }
    return results
