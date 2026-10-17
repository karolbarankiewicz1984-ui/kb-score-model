"""Version-bound Portuguese official season-round GAP evidence (unsigned).

Source was inspected as a dated Liga Portugal communique, LP.DC.026.10,
15 Jun 2026 (Comunicado Oficial 357). The grid puts LP Betclic J8 on
11 Oct 2026 and J9 on 25 Oct 2026; 3rd round Taça Portugal on 18 Oct.

CRITICAL: this is a STATIC published framework, NOT a live updated full
league schedule and NOT a declaration that 17/18 Oct have zero league
matches. Other days, CPC-authorized reschedules, postponements and changes
after publication are outside the grid's guarantees.

The same calendar explicitly permits CPC approved alternative dates:
never certify absence or retrospectively approve the pre-match gate.
"""
from datetime import date

SOURCE = ("https://www.ligaportugal.pt/backoffice/assets/"
          "Comunicado_Oficial_n_357_Calendarios_das_Competicoes_"
          "Profissionais_2026_27_3b82c06381.pdf")
PUBLISHED = "2026-06-15"
SEASON = "2026/27"
MATCHDAY_8 = "2026-10-11"
MATCHDAY_9 = "2026-10-25"
TAÇA_ROUND_3 = "2026-10-18"
GAP_DAYS = frozenset(("2026-10-17", "2026-10-18"))
CLUB_SOURCE = "https://gilvicentefc.pt/data-e-hora-do-jogo-em-atraso-com-o-sc-braga/"


def _observed_postponed_club_game(snapshot):
    if snapshot is None:
        return None
    if (not isinstance(snapshot, dict)
            or snapshot.get("schema") != "kb21-official-portugal-club-postponement-v1"
            or snapshot.get("league_id") != "por.1"
            or snapshot.get("calendar_gate") != "BLOCKED"
            or snapshot.get("reviewer_signed") is not False
            or snapshot.get("full_calendar_verified") is not False
            or snapshot.get("status") != "CLUB_ARTICLE_PARTIAL_FOR_REVIEW"):
        return None
    article = snapshot.get("gil_official_article")
    if (not isinstance(article, dict)
            or article.get("source_url") != CLUB_SOURCE
            or article.get("date_warsaw") != "2026-10-19"
            or article.get("home") != "SC Braga"
            or article.get("away") != "Gil Vicente FC"
            or article.get("kickoff_utc") != "2026-10-19T19:15:00+00:00"
            or article.get("gil_timezone") != "Europe/Lisbon"
            or article.get("article_published") != "2026-10-01"):
        return None
    return {
        "date_warsaw": article["date_warsaw"],
        "home": article["home"], "away": article["away"],
        "kickoff_utc": article["kickoff_utc"],
        "source": CLUB_SOURCE,
        "context_only": True,
    }


def season_break(day, club_snapshot=None):
    """Return manual-review evidence ONLY for Oct 17/18, never an approved zero."""
    try:
        day = date.fromisoformat(day).isoformat()
    except (TypeError, ValueError):
        raise ValueError("Date must be ISO calendar date")
    if day not in GAP_DAYS:
        return None
    exception = _observed_postponed_club_game(club_snapshot)
    return {
        "kind": "PUBLISHED_LP_BETCLIC_ROUND_GAP_CPC_EXCEPTION_CHECK_REQUIRED",
        "league_id": "por.1", "day": day,
        "official_publication": SOURCE,
        "publication_date": PUBLISHED,
        "publication_id": "Comunicado Oficial 357 / LP.DC.026.10",
        "season": SEASON,
        "previous_scheduled_league_round": {
            "round": 8, "scheduled_weekend_reference": MATCHDAY_8},
        "next_scheduled_league_round": {
            "round": 9, "scheduled_weekend_reference": MATCHDAY_9},
        "cup_round_on_reference_day": (
            {"round": 3, "scheduled_reference": TAÇA_ROUND_3}
            if day == TAÇA_ROUND_3 else None),
        "known_postponement_elsewhere_in_window": exception,
        "club_postponement_check_complete": False,
        "cpc_amendment_log_reviewed": False,
        "source_is_live_fixture_inventory": False,
        "captured_full_date_fixture_list": False,
        "confirmed_zero_matches": False,
        "full_calendar_verified": False, "reviewer_signed": False,
        "calendar_gate": "BLOCKED",
        "manual_action": (
            "Before the first candidate kickoff of the ENTIRE date, check "
            "the CURRENT Liga Portugal Betclic calendar for 17/18 Oct, "
            "all CPC approved changes, any league postponements and both "
            "clubs' dated statements. The published round gap is NOT zero proof; "
            "Oct 19 Braga-Gil Vicente is a known rescheduled league fixture."
        ),
    }
