"""Reviewed PitchAPI competition identities for the isolated research pipeline.

The opaque identifiers below are bound to stored PitchAPI fixture examples in
``data/pitchapi/prematch/2026-10-16.json`` through ``2026-10-30.json``.  They are
research mappings, not a claim of independent provider metadata verification.
Neither a club name nor a generic competition label supplies a missing country.
"""
import re
import unicodedata


def _key(value):
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKD", value.casefold())
    value = value.translate(str.maketrans({"ł": "l", "ø": "o", "đ": "d", "ı": "i"}))
    value = value.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


# Canonical league names match the football-data.co.uk CSV importer's labels.
COMPETITIONS = {
    "l_4WFCIZ": ("Premier League", "ENG"),
    "l_1Isor4": ("Bundesliga", "DEU"),
    "l_0ALvwF": ("Serie A", "ITA"),
    "l_0ErfuF": ("La Liga", "ESP"),
    "l_3FJFUl": ("Ligue 1", "FRA"),
    "l_4H43wr": ("Eredivisie", "NLD"),
    "l_4QexZg": ("Primeira Liga", "PRT"),
    "l_2L6d1F": ("Jupiler Pro League", "BEL"),
    "l_0S1uaf": ("Super Lig", "TUR"),
    "l_1LMdEO": ("Premiership", "SCO"),
    "l_4DWyTT": ("Championship", "ENG"),
    "l_0ahLw8": ("League One", "ENG"),
    "l_1W6idJ": ("League Two", "ENG"),
    "l_3hvsne": ("2. Bundesliga", "DEU"),
    "l_0jy5yE": ("Serie B", "ITA"),
    "l_3kyHLd": ("La Liga 2", "ESP"),
    "l_0275VP": ("Ligue 2", "FRA"),
}

# Observed foreign namesakes must not become English/Italian/German/Greek
# competitions even if a caller accidentally supplies those countries.
FOREIGN_COMPETITIONS = {
    "l_3zsMpo": ("Bundesliga", "AUT"),
    "l_1D8Xrl": ("Serie A", "BRA"),
    "l_1dmt9H": ("Serie A", "ECU"),
    "l_2Mh0jT": ("Premier League", "RUS"),
    "l_46aZMC": ("Premier League", "EGY"),
    "l_3UiOcj": ("Premier League", "CAN"),
    "l_20pNSc": ("Super League", "CHN"),
    "l_3qUkB8": ("Serie B", "BRA"),
}

LEAGUE_COUNTRIES = {
    "Premier League": "ENG", "Bundesliga": "DEU", "Serie A": "ITA",
    "La Liga": "ESP", "Ligue 1": "FRA", "Eredivisie": "NLD",
    "Primeira Liga": "PRT", "Jupiler Pro League": "BEL",
    "Super Lig": "TUR", "Premiership": "SCO", "Super League": "GRC",
    "Championship": "ENG", "League One": "ENG", "League Two": "ENG", "National League": "ENG",
    "2. Bundesliga": "DEU", "Serie B": "ITA", "La Liga 2": "ESP", "Ligue 2": "FRA",
    "Scottish Championship": "SCO", "Scottish League One": "SCO", "Scottish League Two": "SCO",
}
LEAGUE_LABELS = {
    "Premier League": ("Premier League",),
    "Bundesliga": ("Bundesliga",),
    "Serie A": ("Serie A",),
    "La Liga": ("La Liga", "LaLiga"),
    "Ligue 1": ("Ligue 1",),
    "Eredivisie": ("Eredivisie",),
    "Primeira Liga": ("Primeira Liga", "Liga Portugal"),
    "Jupiler Pro League": ("Jupiler Pro League", "First Division A"),
    "Super Lig": ("Super Lig", "Süper Lig"),
    "Premiership": ("Premiership", "Scottish Premiership"),
    "Super League": ("Super League", "Super League Greece"),
    "Championship": ("Championship",), "League One": ("League One",), "League Two": ("League Two",),
    "National League": ("National League",), "2. Bundesliga": ("2. Bundesliga",),
    "Serie B": ("Serie B",), "La Liga 2": ("La Liga 2", "LaLiga2"), "Ligue 2": ("Ligue 2",),
    "Scottish Championship": ("Scottish Championship",), "Scottish League One": ("Scottish League One",),
    "Scottish League Two": ("Scottish League Two",),
}
LABEL_TO_LEAGUE = {_key(label): league for league, labels in LEAGUE_LABELS.items() for label in labels}

_COUNTRIES = {
    "ENG": ("ENG", "England"), "DEU": ("DEU", "GER", "DE", "Germany", "Deutschland"),
    "ITA": ("ITA", "IT", "Italy", "Italia"), "ESP": ("ESP", "ES", "Spain", "España"),
    "FRA": ("FRA", "FR", "France"), "NLD": ("NLD", "NED", "NL", "Netherlands", "Holland"),
    "PRT": ("PRT", "POR", "PT", "Portugal"), "BEL": ("BEL", "BE", "Belgium"),
    "TUR": ("TUR", "TR", "Turkey", "Türkiye"), "SCO": ("SCO", "Scotland"),
    "GRC": ("GRC", "GRE", "GR", "Greece"), "AUT": ("AUT", "AT", "Austria"),
    "BRA": ("BRA", "BR", "Brazil", "Brasil"), "ECU": ("ECU", "EC", "Ecuador"),
    "RUS": ("RUS", "RU", "Russia"), "EGY": ("EGY", "EG", "Egypt"),
    "CAN": ("CAN", "CA", "Canada"), "CHN": ("CHN", "CN", "China"),
}
COUNTRY_ALIASES = {_key(value): country for country, values in _COUNTRIES.items() for value in values}


def country_code(value):
    """Normalize reviewed country spellings; GB/UK do not identify England."""
    return COUNTRY_ALIASES.get(_key(value))


def country_for_league(league):
    return LEAGUE_COUNTRIES.get(LABEL_TO_LEAGUE.get(_key(league)))


def canonicalize(fixture):
    """Copy a fixture, rejecting contradictory IDs, labels and countries.

    Unknown IDs cannot be upgraded merely because a familiar label and country
    were supplied.  A missing ID is allowed with an explicit reviewed country.
    Existing unsupported/missing-country rows remain available to the resolver
    so its precise country-not-verified blocker is retained.
    """
    result = dict(fixture)
    raw_id = fixture.get("league_id")
    league_id = str(raw_id).strip() if raw_id is not None else ""
    known = COMPETITIONS.get(league_id)
    foreign = FOREIGN_COMPETITIONS.get(league_id)
    countries = []
    for field in ("country_code", "country"):
        value = fixture.get(field)
        if value is not None and value != "":
            code = country_code(value)
            # UK-wide metadata is compatible with both England and Scotland;
            # only a reviewed opaque competition ID may refine it to one.
            if (code is None and known and known[1] in ("ENG", "SCO")
                    and _key(value) in ("gb", "gbr", "uk", "united kingdom")):
                code = known[1]
            if code is None:
                raise ValueError("competition_country_not_verified")
            countries.append(code)
    if len(set(countries)) > 1:
        raise ValueError("competition_country_conflict")
    supplied = countries[0] if countries else None
    raw_league = fixture.get("league")
    league = LABEL_TO_LEAGUE.get(_key(raw_league), raw_league)
    if known or foreign:
        expected_league, expected_country = known or foreign
        if supplied and supplied != expected_country:
            raise ValueError("competition_country_conflict")
        if _key(raw_league) not in {_key(label) for label in LEAGUE_LABELS[expected_league]}:
            raise ValueError("competition_name_conflict")
        if foreign:
            # Country-less namesakes stay blocked, including legacy diagnostics.
            if supplied:
                raise ValueError("unsupported_competition_id")
            return result
        result.update(league=expected_league, country_code=expected_country)
        return result
    if league_id and supplied and league in LEAGUE_COUNTRIES:
        raise ValueError("competition_id_not_verified")
    if supplied:
        result["country_code"] = supplied
    result["league"] = league
    return result
