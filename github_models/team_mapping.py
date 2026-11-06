"""Auditable, conservative team matching between PitchAPI and historical CSV.

Never guesses aliases: unmatched names remain blocked and are counted.
"""
import re
import unicodedata

ALIASES = {
    "premier league": {
        "manchester united": "man united", "manchester city": "man city",
        "tottenham hotspur": "tottenham", "newcastle united": "newcastle",
        "nottingham forest": "nott'm forest", "wolverhampton wanderers": "wolves",
        "brighton hove albion": "brighton", "west ham united": "west ham",
        "afc bournemouth": "bournemouth", "leeds united": "leeds",
        "leicester city": "leicester", "ipswich town": "ipswich",
        "norwich city": "norwich", "sheffield united": "sheffield united",
    },
    "bundesliga": {"bayern munich": "bayern munich", "borussia dortmund": "dortmund",
                    "bayer leverkusen": "leverkusen", "rb leipzig": "rb leipzig"},
    "serie a": {"inter milan": "inter", "ac milan": "milan", "as roma": "roma",
                 "ssc napoli": "napoli", "juventus fc": "juventus"},
    "la liga": {"real madrid cf": "real madrid", "fc barcelona": "barcelona",
                 "atletico de madrid": "ath madrid", "athletic club": "ath bilbao"},
}

def normalize(name):
    if not isinstance(name, str):
        return ""
    text = unicodedata.normalize("NFKD", name.casefold())
    text = text.translate(str.maketrans({"ł": "l", "ø": "o", "đ": "d", "ı": "i"}))
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def resolve(fixture, history):
    """Resolve both sides against the exact in-league historical candidate set.

    An exact normalized spelling and its reviewed alias are considered together;
    if they point to different literal candidates the row is ambiguous.  The
    caller should pass only history available at the relevant as-of time.
    """
    from github_models.competition_identity import canonicalize, country_for_league, country_code
    from github_models.reviewed_team_aliases import ALIASES_EXTRA

    if fixture.get("identity_blockers"):
        raise ValueError("provider_identity_blocked:" + str(fixture["identity_blockers"][0]))
    fixture = canonicalize(fixture)
    side_ids = {}
    for side in ("home", "away"):
        values = []
        for field in (side + "_id", side + "_team_id"):
            value = fixture.get(field)
            if value is not None:
                if type(value) not in (str, int) or not str(value).strip():
                    raise ValueError("fixture_team_id_invalid")
                values.append(str(value).strip())
        if len(set(values)) > 1:
            raise ValueError("fixture_team_id_conflict")
        if values:
            side_ids[side] = values[0]
    if len(side_ids) == 2 and side_ids["home"] == side_ids["away"]:
        raise ValueError("fixture_team_ids_not_distinct")
    history = list(history)
    league = fixture["league"]
    league_key = normalize(league)
    expected_country = country_for_league(league)
    supplied_country = country_code(fixture.get("country_code"))
    if expected_country and supplied_country != expected_country:
        reason = ("competition_country_conflict" if supplied_country else
                  f"ambiguous_{league_key.replace(chr(32), chr(95))}_country_not_verified")
        raise ValueError(reason)

    candidates = {}
    for row in history:
        if normalize(row.get("league")) != league_key:
            continue
        historical_country = row.get("country_code") or row.get("country")
        if historical_country and expected_country and country_code(historical_country) != expected_country:
            raise ValueError("history_competition_country_conflict")
        for side in ("home", "away"):
            team = row.get(side)
            normalized = normalize(team)
            if normalized:
                candidates.setdefault(normalized, set()).add(team)
    aliases = {}
    for source in (ALIASES.get(league_key, {}), ALIASES_EXTRA.get(league_key, {})):
        for name, target in source.items():
            aliases.setdefault(normalize(name), set()).add(normalize(target))
    matched = {}
    for side in ("home", "away"):
        raw = normalize(fixture.get(side))
        targets = {raw} | aliases.get(raw, set())
        options = {team for target in targets for team in candidates.get(target, set())}
        if not options:
            raise ValueError(f"unmatched_{side}_team:{fixture.get(side)}")
        if len(options) != 1:
            raise ValueError(f"ambiguous_{side}_team:{fixture.get(side)}")
        matched[side] = next(iter(options))
    if matched["home"] == matched["away"]:
        raise ValueError("fixture_teams_not_distinct")
    # Team IDs belong to a provider namespace.  Never compare a PitchAPI ID
    # with football-data.co.uk or infer an ID equivalence from matching names.
    provider = normalize(fixture.get("source_provider"))
    if provider:
        known_ids = {}
        for row in history:
            if normalize(row.get("league")) != league_key or normalize(row.get("source_provider")) != provider:
                continue
            for side in ("home", "away"):
                values = [row.get(field) for field in (side + "_id", side + "_team_id")
                          if row.get(field) is not None]
                if any(type(value) not in (str, int) or not str(value).strip() for value in values):
                    raise ValueError("history_team_id_invalid")
                ids = {str(value).strip() for value in values}
                if len(ids) > 1:
                    raise ValueError("history_team_id_conflict")
                if ids:
                    known_ids.setdefault(row.get(side), set()).update(ids)
        for side, supplied_id in side_ids.items():
            named_ids = known_ids.get(matched[side], set())
            if len(named_ids) > 1:
                raise ValueError("history_team_id_ambiguous")
            other_ids = {value for name, values in known_ids.items() if name != matched[side] for value in values}
            if supplied_id in other_ids or (named_ids and supplied_id not in named_ids):
                raise ValueError("fixture_team_id_name_conflict")
    return dict(fixture, home=matched["home"], away=matched["away"])
