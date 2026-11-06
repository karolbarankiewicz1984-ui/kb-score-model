"""Strict matching with reviewed supplementary aliases, preserving existing gates."""
from github_models.team_mapping import resolve, normalize
from github_models.reviewed_team_aliases import ALIASES_EXTRA

def resolve_reviewed(fixture, history):
    try:
        return resolve(fixture, history)
    except ValueError as original:
        if not str(original).startswith("unmatched_"):
            raise
        league = normalize(fixture["league"])
        aliases = ALIASES_EXTRA.get(league, {})
        revised = dict(fixture)
        for side in ("home", "away"):
            raw = normalize(revised[side])
            alias = aliases.get(raw)
            if alias:
                targets = {team for row in history if normalize(row.get("league","")) == league
                           for team in (row["home"],row["away"]) if normalize(team) == alias}
                if len(targets) == 1:
                    revised[side] = next(iter(targets))
        return resolve(revised, history)
