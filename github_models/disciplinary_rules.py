"""Evidence gates for Superbet disciplinary markets (no bookmaker calls).

Official Superbet football rules effective 2025-12-16 and the 2026-04-29
OPTA-source notice are documentation of business rules, NOT historical game
statistics or proof that OddsPapi 'Bookings' uses the same units.

No imported HF/AF or HY/AY aggregate can establish exclusions for
referee advantage, bench/staff, 2nd yellow, halftime and post-whistle events.
"""
from __future__ import annotations

from collections.abc import Mapping

SUPERBET_FOOTBALL_RULES = (
    "https://superbet.pl/wiki/oficjalny-komunikat-nr-06-2022-z-dnia-18-11-2024-r"
)
SUPERBET_OPTA_NOTICE = (
    "https://superbet.pl/wiki/oficjalny-komunikat-nr-02-2022-z-dnia-091122"
)
OPTA_DEFINITIONS = (
    "https://optaplayerstats.statsperform.com/en_GB/opta-event-definitions"
)
SOURCE_REQUIREMENTS = {
    "fouls": frozenset({
        "fixture_id","official_opta_match_source",
        "referee_whistled_fouls","advantage_fouls_excluded",
        "team_home_fouls","team_away_fouls",
        "period_fulltime","stat_observed_at_utc",
    }),
    "cards": frozenset({
        "fixture_id","official_opta_match_source",
        "player_on_pitch_status","staff_bench_exclusion",
        "after_final_whistle_exclusion","halftime_player_resumed",
        "yellow_card_events","straight_red_card_events",
        "second_yellow_dismissals","period_fulltime",
        "stat_observed_at_utc",
    }),
}
# Raw football-data.co.uk event CSV contains HF/AF and HY/AY only; it
# cannot infer all of these event details. Foul/Bookings market matching and
# official Superbet payout are distinct additional proof obligations.
ODDSPAPI_BOOKINGS_UNIT_UNVERIFIED = True

def review_capabilities(*, market, field_names, source_provider,
                        provider_market_identity_verified=False,
                        bookmaker_payout_verified=False):
    if market not in SOURCE_REQUIREMENTS:
        raise ValueError("disciplinary_market_not_supported")
    if not isinstance(field_names,(list,tuple,set,frozenset)):
        raise ValueError("field_names_required")
    if any(not isinstance(x,str) for x in field_names):
        raise ValueError("invalid_source_field")
    missing=sorted(SOURCE_REQUIREMENTS[market]-set(field_names))
    official_source = source_provider == "OPTA-official-event-data"
    # Even complete vendor data cannot prove how OddsPapi names a market,
    # nor actual Superbet settlement. Never turn this predicate into a bet.
    source_event_compatible = official_source and not missing
    return {
        "market":market,
        "source_provider":source_provider,
        "source_event_schema_compatible":source_event_compatible,
        "missing_required_fields":missing,
        "official_source_verified":official_source,
        "provider_market_identity_verified":bool(provider_market_identity_verified),
        "bookmaker_payout_verified":bool(bookmaker_payout_verified),
        "automatic_market_promotion":False,
        "official_superbet_payout_confirmed_by_this_gate":False,
        "booking_units_equivalent_to_yellow_cards":False,
        "source_covered_matches":0,
        "rule_sources":[SUPERBET_FOOTBALL_RULES,SUPERBET_OPTA_NOTICE,OPTA_DEFINITIONS],
    }

def review_football_data_schema():
    """Trace the actually imported fields, not synthetic OPTA rows."""
    legacy={"fixture_id","home","away","match_date","events","HF","AF","HY","AY",
            "published_at_utc"}
    return {market:review_capabilities(market=market,field_names=legacy,
                                        source_provider="football-data.co.uk")
            for market in SOURCE_REQUIREMENTS}

def total_cards_from_verified_trajectories(rows):
    """Compute official rule arithmetic ONLY for explicitly verified player trajectories.

    A second-yellow dismissal is an entire player disciplinary sequence of
    exactly two yellows and counts as 3 cards IN TOTAL. A straight red counts
    as two cards. Exclusions are applied before arithmetic. NOT an API adapter,
    historical source parser or bookmaker settlement.
    """
    if not isinstance(rows,list):
        raise ValueError("player_trajectories_required")
    total=0
    for r in rows:
        if not isinstance(r,Mapping):
            raise ValueError("invalid_player_trajectory")
        required={"yellow_count","straight_red","second_yellow_dismissal",
                  "on_pitch_at_card","after_final_whistle","in_halftime",
                  "resumed_second_half","official_event_verified"}
        if set(r) != required:
            raise ValueError("incomplete_player_event_trajectory")
        if r["official_event_verified"] is not True:
            raise ValueError("unverified_player_event")
        count=r["yellow_count"]
        if type(count) is not int or count not in (0,1,2):
            raise ValueError("invalid_yellow_count")
        for k in required-{"yellow_count","official_event_verified"}:
            if type(r[k]) is not bool:
                raise ValueError("invalid_trajectory_flag")
        if (r["second_yellow_dismissal"] and
            (count != 2 or r["straight_red"])):
            raise ValueError("conflicting_red_card_events")
        if not r["on_pitch_at_card"] or r["after_final_whistle"]:
            continue
        if r["in_halftime"] and not r["resumed_second_half"]:
            continue
        total += 3 if r["second_yellow_dismissal"] else (count+2*int(r["straight_red"]))
    return total
