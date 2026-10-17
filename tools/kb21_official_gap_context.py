"""Reuse existing organizer snapshots for bounded gap-between-matchdays context.

Unlike an actual league-wide date-by-date inventory, two adjacent published
fixture dates do not rule out late additions/postponements or automatically
confirm ZERO GAMES. All findings remain unsigned and cannot pass Calendar Gate.
"""
from datetime import timezone

from tools.kb21_fixture_crosscheck import _instant
from tools.kb21_official_knvb import SOURCE as KNVB_URL
from tools.kb21_official_press_fixtures import (
    SOURCES as PRESS_URLS, EXPECTED_ARTICLE_FIXTURES,
)

PORTUGAL_SEASON_SCHEDULE = (
    "https://www.ligaportugal.pt/backoffice/assets/"
    "Comunicado_Oficial_n_357_Calendarios_das_Competicoes_"
    "Profissionais_2026_27_3b82c06381.pdf"
)


def date_gap(league, day, source, deadline):
    if not isinstance(source, dict):
        return None
    if (source.get("calendar_gate") != "BLOCKED"
            or source.get("reviewer_signed") is not False
            or source.get("full_calendar_verified") is not False
            or source.get("league_id") != league
            or source.get("errors") != []
            or _instant(source.get("captured_at_utc")) is None
            or not isinstance(source.get("days"), list)
            or day not in source["days"]
            or not isinstance(source.get("by_day"), dict)
            or source["by_day"].get(day) != []):
        return None
    if league == "fra.1":
        if (source.get("schema") != "kb21-official-press-fixtures-v1"
                or source.get("official_url") != PRESS_URLS["fra.1"][0]
                or source.get("status") != "OFFICIAL_DATED_ARTICLE_PARTIAL_FOR_REVIEW"
                or source.get("parsed_article_fixture_count")
                    != EXPECTED_ARTICLE_FIXTURES["fra.1"]
                or source.get("expected_article_fixture_count")
                    != EXPECTED_ARTICLE_FIXTURES["fra.1"]):
            return None
        dates = source.get("article_fixture_dates")
        kind = "PUBLISHED_LIGUE1_TWO_ROUNDS_DATE_GAP"
        url = PRESS_URLS["fra.1"][0]
    elif league == "ned.1":
        if (source.get("schema") != "kb21-official-knvb-eredivisie-v1"
                or source.get("official_url") != KNVB_URL
                or source.get("status") != "OFFICIAL_KNVB_PAGE_PARTIAL_FOR_REVIEW"
                or not isinstance(source.get("page_fixture_count"), int)
                or source["page_fixture_count"] < 1
                or day not in source.get("unconfirmed_zero_dates", [])):
            return None
        dates = source.get("page_dates_found")
        kind = "KNVB_ROLLING_PROGRAM_BETWEEN_DATES"
        url = KNVB_URL
    else:
        return None
    if not isinstance(dates, list) or not all(
            isinstance(x, str) and len(x) == 10 for x in dates):
        return None
    previous = sorted({x for x in dates if x < day})
    future = sorted({x for x in dates if x > day})
    if day in dates or not previous or not future:
        return None
    captured = _instant(source["captured_at_utc"])
    return {
        "kind": kind, "official_url": url,
        "previous_visible_date": previous[-1],
        "next_visible_date": future[0],
        "captured_at_utc": captured.astimezone(timezone.utc).isoformat(),
        "snapshot_taken_before_first_whole_day_candidate":
            deadline is not None and captured < deadline,
        "source_fixture_count": (
            source["parsed_article_fixture_count"] if league == "fra.1"
            else source["page_fixture_count"]),
        "calendar_gate": "BLOCKED",
        "organizer_whole_date_complete": False,
        "verified_zero_games": False,
        "human_signed": False,
    }
