"""Reviewed PitchAPI competition identities for the isolated research pipeline.

The opaque identifiers below are bound to stored PitchAPI fixture examples in
``data/pitchapi/prematch/2026-10-16.json`` through ``2026-10-30.json``.  They are
research mappings. Matching live league metadata was additionally observed in
GitHub Actions run 42189744814 for IDs present in that collection.
Neither a club name nor a generic competition label supplies a missing country.
"""
import re
import unicodedata


def _key(value):
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKD", value.casefold())
    value = value.translate(str.maketrans({"ł": "l", "ø": "o", "đ": "d", "ı": "i", "æ": "ae", "œ": "oe"}))
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
    "l_3xwVF2": ("Super League", "GRC"),
    "l_3zsMpo": ("Austrian Bundesliga", "AUT"),
    "l_1D8Xrl": ("Brazilian Serie A", "BRA"),
    "l_2Mh0jT": ("Russian Premier League", "RUS"),
    "l_49Zmno": ("Danish Superliga", "DNK"),
    "l_0kSJLz": ("Romanian Superliga", "ROU"),
    "l_214sqK": ("Ekstraklasa", "POL"),
    "l_1XsMdH": ("Allsvenskan", "SWE"),
    "l_2ApGa4": ("J1 League", "JPN"),
    "l_3v84VE": ("Liga MX", "MEX"),
    "l_0eg6C9": ("MLS", "USA"),
    "l_45VZuL": ("Liga Profesional", "ARG"),
    "l_20pNSc": ("Chinese Super League", "CHN"),
    "l_3Ci5Cg": ("Veikkausliiga", "FIN"),
    "l_1eJSA7": ("Irish Premier Division", "IRL"),
    "l_0uqFK8": ("Eliteserien", "NOR"),
    "l_4d6Bwl": ("Swiss Super League", "CHE"),
    "l_4auCPk": ("Swiss Challenge League", "CHE"),
}

# Observed foreign namesakes must not become English/Italian/German/Greek
# competitions even if a caller accidentally supplies those countries.
FOREIGN_COMPETITIONS = {
    "l_1dmt9H": ("Serie A", "ECU"),
    "l_46aZMC": ("Premier League", "EGY"),
    "l_3UiOcj": ("Premier League", "CAN"),
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
    "Austrian Bundesliga": "AUT", "Brazilian Serie A": "BRA", "Russian Premier League": "RUS",
    "Danish Superliga": "DNK", "Romanian Superliga": "ROU", "Ekstraklasa": "POL",
    "Allsvenskan": "SWE", "J1 League": "JPN", "Liga MX": "MEX", "MLS": "USA", "Liga Profesional": "ARG",
    "Chinese Super League": "CHN", "Veikkausliiga": "FIN", "Irish Premier Division": "IRL",
    "Eliteserien": "NOR", "Swiss Super League": "CHE", "Swiss Challenge League": "CHE",
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
    "Super League": ("Super League", "Super League Greece", "Super League 1"),
    "Championship": ("Championship",), "League One": ("League One",), "League Two": ("League Two",),
    "National League": ("National League",), "2. Bundesliga": ("2. Bundesliga",),
    "Serie B": ("Serie B",), "La Liga 2": ("La Liga 2", "LaLiga2"), "Ligue 2": ("Ligue 2",),
    "Scottish Championship": ("Scottish Championship",), "Scottish League One": ("Scottish League One",),
    "Scottish League Two": ("Scottish League Two",),
    "Austrian Bundesliga": ("Austrian Bundesliga", "Bundesliga"),
    "Brazilian Serie A": ("Brazilian Serie A", "Serie A"),
    "Russian Premier League": ("Russian Premier League", "Premier League"),
    "Danish Superliga": ("Danish Superliga", "Superligaen", "Superliga"),
    "Romanian Superliga": ("Romanian Superliga", "Liga I", "Superliga"),
    "Ekstraklasa": ("Ekstraklasa",), "Allsvenskan": ("Allsvenskan",),
    "J1 League": ("J1 League", "J. League"), "Liga MX": ("Liga MX",),
    "MLS": ("MLS",), "Liga Profesional": ("Liga Profesional",),
    "Chinese Super League": ("Chinese Super League", "Super League"),
    "Veikkausliiga": ("Veikkausliiga",), "Irish Premier Division": ("Irish Premier Division", "Premier Division"),
    "Eliteserien": ("Eliteserien",), "Swiss Super League": ("Swiss Super League", "Super League"),
    "Swiss Challenge League": ("Swiss Challenge League", "Challenge League"),
}
# Generic labels may name competitions in several countries.  Keep the legacy
# primary label for country-less diagnostics, and disambiguate using a reviewed
# ID or the complete (label, country) pair before matching any teams.
LABEL_TO_LEAGUE = {}
LABEL_COUNTRY_TO_LEAGUE = {}
for _league, _labels in LEAGUE_LABELS.items():
    for _label in _labels:
        LABEL_TO_LEAGUE.setdefault(_key(_label), _league)
        LABEL_COUNTRY_TO_LEAGUE[(_key(_label), LEAGUE_COUNTRIES[_league])] = _league

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
    "POL": ("POL", "PL", "Poland"), "DNK": ("DNK", "DEN", "DK", "Denmark"),
    "SWE": ("SWE", "SE", "Sweden"), "ARG": ("ARG", "AR", "Argentina"),
    "JPN": ("JPN", "JP", "Japan"), "MEX": ("MEX", "MX", "Mexico", "México"),
    "USA": ("USA", "US", "United States", "United States of America"),
    "ROU": ("ROU", "ROM", "RO", "Romania"),
    "FIN": ("FIN", "FI", "Finland"), "IRL": ("IRL", "IE", "Ireland", "Republic of Ireland"),
    "NOR": ("NOR", "NO", "Norway"), "CHE": ("CHE", "SUI", "CH", "Switzerland"),
}
# Additional country codes actually observed in the 65 live league metadata
# receipts from run 42189744814. FIFA spellings normalize to ISO alpha-3; this
# recognizes metadata only and does not authorize any league ID or add history.
_COUNTRIES.update({
    "AUS": ("AUS",), "BOL": ("BOL",), "COL": ("COL",),
    "HRV": ("HRV", "CRO"), "CHL": ("CHL", "CHI"), "PRY": ("PRY", "PAR"),
    "SAU": ("SAU", "KSA"), "ARE": ("ARE", "UAE"), "KOR": ("KOR",),
    "THA": ("THA",), "IND": ("IND",), "SRB": ("SRB",),
    "CZE": ("CZE",), "SVK": ("SVK",), "ISR": ("ISR",), "QAT": ("QAT",),
    "PER": ("PER",), "VEN": ("VEN",), "LVA": ("LVA",),
})
COUNTRY_ALIASES = {_key(value): country for country, values in _COUNTRIES.items() for value in values}


def country_code(value):
    """Normalize reviewed country spellings; GB/UK do not identify England."""
    return COUNTRY_ALIASES.get(_key(value))


def league_for_label(league, country=None):
    """Resolve an explicit label/country pair, never infer a country from teams."""
    code = country_code(country)
    return LABEL_COUNTRY_TO_LEAGUE.get((_key(league), code), LABEL_TO_LEAGUE.get(_key(league), league))


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
    league = league_for_label(raw_league, supplied)
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
    if supplied and league in LEAGUE_COUNTRIES and supplied != LEAGUE_COUNTRIES[league]:
        raise ValueError("competition_country_conflict")
    if supplied:
        result["country_code"] = supplied
    result["league"] = league
    return result
