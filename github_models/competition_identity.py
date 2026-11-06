"""Reviewed provider competition IDs; never infer country from generic league label.

Identifiers are supported by observed fixture examples and require independent
provider metadata confirmation before production deployment.
"""
COMPETITIONS = {
    "l_4WFCIZ": ("Premier League", "ENG"),
    "l_1Isor4": ("Bundesliga", "DEU"),
    "l_0ALvwF": ("Serie A", "ITA"),
    "l_0ErfuF": ("La Liga", "ESP"),
    "l_3FJFUl": ("Ligue 1", "FRA"),
}
def canonicalize(fixture):
    row = COMPETITIONS.get(str(fixture.get("league_id")))
    if not row:
        return fixture
    league, country = row
    if fixture.get("country_code") and str(fixture["country_code"]).upper() != country:
        raise ValueError("competition_country_conflict")
    return dict(fixture, league=league, country_code=country)
