"""KB21 competition whitelist, using API-Football league ID first.

Names are a compatibility fallback for as-yet-unmapped or absent IDs.
Only the provider's existing fixtures can be considered; this module
never creates games, queries a second provider or grants PLAY.
"""

# Domestic competitions: API-Football ID -> expected country.
DOMESTIC_IDS = {
    39: "England", 140: "Spain", 135: "Italy", 78: "Germany",
    61: "France", 94: "Portugal", 88: "Netherlands",
    144: "Belgium", 203: "Turkey", 106: "Poland",
}

# World Cup, UCL, UEL, Nations League, Euro, European WC qualifiers, UECL.
INTERNATIONAL_IDS = {1, 2, 3, 4, 5, 32, 848}

DOMESTIC_NAMES = {
    ("England", "Premier League"), ("Spain", "La Liga"),
    ("Italy", "Serie A"), ("Germany", "Bundesliga"),
    ("France", "Ligue 1"), ("Portugal", "Primeira Liga"),
    ("Portugal", "Liga Portugal"), ("Netherlands", "Eredivisie"),
    ("Belgium", "Jupiler Pro League"), ("Belgium", "Pro League"),
    ("Turkey", "Süper Lig"), ("Poland", "Ekstraklasa"),
}

INTERNATIONAL_NAMES = {
    "UEFA Champions League", "UEFA Europa League",
    "UEFA Europa Conference League", "UEFA Conference League",
    "UEFA Nations League", "World Cup", "World Cup - Qualification Europe",
    "Euro Championship", "UEFA European Championship",
}


def is_domestic_competition(lid, country, name):
    """Accept domestic fixtures from known IDs even if display names change."""
    if type(lid) is int and lid in DOMESTIC_IDS:
        return country == DOMESTIC_IDS[lid]
    return isinstance(country, str) and isinstance(name, str) and (country, name) in DOMESTIC_NAMES


def scope_method(fixture):
    """Reason for accepting/excluding the provider's competition.

    Known domestic ID with contradictory country fails closed. Renamed
    display names are still accepted for matching IDs and countries.
    """
    if not isinstance(fixture, dict):
        return "OUT_OF_SCOPE"
    league = fixture.get("league")
    if not isinstance(league, dict):
        return "OUT_OF_SCOPE"
    lid = league.get("id")
    name, country = league.get("name"), league.get("country")
    if type(lid) is int and lid in DOMESTIC_IDS:
        if country != DOMESTIC_IDS[lid]:
            return "ID_COUNTRY_CONFLICT"
        return "LEAGUE_ID"
    if type(lid) is int and lid in INTERNATIONAL_IDS:
        return "LEAGUE_ID"
    if (country, name) in DOMESTIC_NAMES or name in INTERNATIONAL_NAMES:
        return "NAME_FALLBACK"
    return "OUT_OF_SCOPE"


def in_scope(fixture):
    return scope_method(fixture) in ("LEAGUE_ID", "NAME_FALLBACK")
