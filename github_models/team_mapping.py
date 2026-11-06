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
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return re.sub(r"\s+", " ", text)

def resolve(fixture, history):
    league = fixture["league"]
    # Country-sensitive league names must be verified, never inferred from a team name.
    # Other generic names (Premier League, Bundesliga) also exist in multiple countries.
    league_key = normalize(league)
    if league_key in ("serie a", "premier league", "bundesliga"):
        country = normalize(str(fixture.get("country_code") or ""))
        expected = {"serie a": ("ita",),
                    "premier league": ("eng",),
                    "bundesliga": ("deu", "ger")}[league_key]
        if country not in expected:
            raise ValueError(f"ambiguous_{league_key.replace(chr(32), chr(95))}_country_not_verified")
    league_key = normalize(league)
    teams = {normalize(t) for row in history if row.get("league") == league
             for t in (row["home"], row["away"])}
    aliases = ALIASES.get(league_key, {})
    matched = {}
    for side in ("home", "away"):
        raw = normalize(fixture[side])
        # Exact canonical name first; explicit reviewed alias only second.
        target = raw if raw in teams else aliases.get(raw)
        if target is None or target not in teams:
            raise ValueError(f"unmatched_{side}_team:{fixture[side]}")
        options = sorted({t for row in history if row.get("league") == league
                          for t in (row["home"], row["away"]) if normalize(t) == target})
        if len(options) != 1:
            raise ValueError(f"ambiguous_{side}_team:{fixture[side]}")
        matched[side] = options[0]
    return dict(fixture, home=matched["home"], away=matched["away"])

# TODO: league_id-to-country mapping must be explicitly audited against PitchAPI metadata.
