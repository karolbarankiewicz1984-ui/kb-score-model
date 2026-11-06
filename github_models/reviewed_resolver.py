"""One shared strict resolver for forecasts, audits and settlement."""
from github_models.team_mapping import resolve


def resolve_reviewed(fixture, history):
    # All aliases are considered in one pass.  Retrying after an unmatched side
    # could otherwise hide a collision between an exact name and an alias.
    return resolve(fixture, history)
