"""Read committed historical counts and archived OddsPapi quotes without provider calls."""
from collections import Counter, defaultdict
from datetime import timedelta
import json
from pathlib import Path
from subprocess import run

from github_models.shots_research import (
    FAMILIES, HISTORY_SOURCE, MIN_MATCH_DURATION, archived_quote_eligible, identifier, timestamp,
)
from tools.pitchapi_xg_lab import competition, norm

# A mapping entry requires an archived catalog ID, exact label and market type,
# documented scope/unit, and an independently reviewed Superbet settlement rule.
# Mapping by substrings, player IDs, or approximate market names is unsafe.
VERIFIED_MARKETS = {}
HISTORY_DIRS = ("daily", "backfill_5m", "international_5m")
SHOT_WORDS = ("shot", "attempt on", "attempt at")


def _read_git(root, *args):
    return run(["git", "-C", str(root), *args], check=True, capture_output=True,
               text=True, encoding="utf-8").stdout


def committed_snapshots(root, directory):
    """Read committed versions with the committer time and immutable blob reference."""
    paths = _read_git(root, "ls-tree", "-r", "--name-only", "HEAD", directory)
    commits = _read_git(root, "log", "--format=%x1e%H%x09%cI", "--name-only", "HEAD", "--", directory)
    revisions = {}
    for revision in commits.split("\x1e")[1:]:
        header, *files = revision.strip().splitlines()
        commit, published = header.split("\t")
        for path in filter(None, files):
            revisions.setdefault(path, (commit, published))
    for path in paths.splitlines():
        if not Path(path).stem[:1].isdigit() or not path.endswith(".json"):
            continue
        if path not in revisions:
            raise ValueError("missing_archive_git_history")
        commit, published = revisions[path]
        yield path, json.loads(_read_git(root, "show", f"{commit}:{path}")), published, f"{commit}:{path}"


def _regular_time(row):
    score = row.get("score") or {}
    full = score.get("fulltime") or {}
    return (all(type(full.get(side)) is int for side in ("home", "away"))
            and row.get("goals") == full
            and all((score.get(period) or {}) == {"home": None, "away": None}
                    for period in ("extratime", "penalty")))


def _identity(row):
    return competition(row.get("league")), norm(row.get("home")), norm(row.get("away"))


def _explicit_counts(team):
    total, on_target, blocked = (team.get(k) for k in ("shots", "shots_on_goal", "blocked_shots"))
    if (type(total) is not int or type(on_target) is not int or type(blocked) is not int
            or min(on_target, blocked) < 0 or not on_target + blocked <= total <= 200):
        return None
    return {"shots_total": total, "shots_on_target": on_target}


def load_history(root, cutoff):
    """Exact cross-provider links identify teams; legacy explicit counts feed the model."""
    as_of = timestamp(cutoff)
    coverage = Counter()
    api = {}
    excluded = set()
    by_identity = defaultdict(list)
    for directory in HISTORY_DIRS:
        for _, payload, published, ref in committed_snapshots(root, "data/api_football/" + directory):
            coverage["api_football_files"] += 1
            coverage["api_football_rows"] += len(payload["rows"])
            if timestamp(published) > as_of:
                coverage["api_football_files_after_cutoff"] += 1
                continue
            for row in payload["rows"]:
                fid = str(row["fixture_id"])
                if not identifier(row.get("fixture_id")) or not _regular_time(row):
                    coverage["api_football_period_unverified"] += 1
                    continue
                kickoff = timestamp(row["date"])
                if kickoff + MIN_MATCH_DURATION > timestamp(published):
                    coverage["api_football_publication_before_fulltime"] += 1
                    continue
                teams = {}
                for side in ("home", "away"):
                    tid = row.get(side + "_id")
                    matching = [t for t in row["teams"] if t.get("team_id") == tid]
                    counts = _explicit_counts(matching[0]) if len(matching) == 1 else None
                    if identifier(tid) and counts:
                        teams[str(tid)] = {
                            **counts, "fixture_id": fid, "team_id": str(tid), "source": HISTORY_SOURCE,
                            "kickoff_utc": row["date"], "published_at_utc": published, "source_ref": ref,
                            "scope": "team", "period": "fulltime", "stat_definition_verified": True,
                        }
                if not teams:
                    coverage["api_football_missing_counts"] += 1
                identity = _identity(row)
                sides = tuple(str(row.get(side + "_id")) for side in ("home", "away"))
                signature = (identity, sides, kickoff, row["goals"],
                             {tid: tuple(t[f] for f in FAMILIES) for tid, t in teams.items()})
                if fid in api:
                    if api[fid][0] != signature:
                        excluded.add(fid)
                    elif timestamp(published) < timestamp(api[fid][1]):
                        api[fid] = (signature, published, teams)
                else:
                    api[fid] = (signature, published, teams)
    for fid, (signature, _, _) in api.items():
        if fid not in excluded:
            by_identity[signature[0]].append(fid)
    coverage["api_football_conflicting_fixtures"] = len(excluded)
    coverage["api_football_fulltime_fixtures"] = len(api) - len(excluded)
    coverage["api_football_fulltime_both_counts"] = sum(
        len(teams) == 2 for fid, (_, _, teams) in api.items() if fid not in excluded)

    crosswalk = defaultdict(set)
    reverse = defaultdict(set)
    fixture_links = defaultdict(set)
    for _, payload, published, ref in committed_snapshots(root, "data/pitchapi/daily"):
        coverage["pitchapi_daily_files"] += 1
        coverage["pitchapi_fixtures_available"] += payload["fixtures_available"]
        coverage["pitchapi_rows"] += len(payload["rows"])
        coverage["pitchapi_complete_xg"] += payload["matches_with_complete_xg"]
        coverage["pitchapi_shots_errors"] += sum(bool(r.get("shots_error")) for r in payload["rows"])
        observed = timestamp(payload["observed_at_utc"])
        if max(observed, timestamp(published)) > as_of:
            coverage["pitchapi_days_after_cutoff"] += 1
            continue
        for row in payload["rows"]:
            if (row.get("status") != "finished" or not all(identifier(row.get(k)) for k in
                    ("pitch_match_id", "home_team_id", "away_team_id", "league_id"))
                    or row["home_team_id"] == row["away_team_id"]):
                continue
            kickoff = timestamp(row["kickoff_utc"])
            if kickoff + MIN_MATCH_DURATION > observed:
                coverage["pitchapi_observations_before_fulltime"] += 1
                continue
            candidates = []
            for fid in by_identity[_identity(row)]:
                _, sides, start, goals, _ = api[fid][0]
                if (abs(start - kickoff) <= timedelta(minutes=15)
                        and goals == {side: row.get("goals_" + side) for side in ("home", "away")}):
                    candidates.append((fid, sides))
            if len(candidates) != 1:
                continue
            fid, sides = candidates[0]
            fixture_links[row["pitch_match_id"]].add(fid)
            coverage["pitchapi_exact_legacy_links"] += 1
            p_counts = [row["xg_" + s].get("shot_count") for s in ("home", "away")]
            if not row.get("shots_error") and all(t in api[fid][2] for t in sides):
                coverage["pitchapi_exact_legacy_both_totals_compared"] += 1
                if p_counts == [api[fid][2][t]["shots_total"] for t in sides]:
                    coverage["pitchapi_exact_legacy_both_totals_agree"] += 1
            for pitch_id, legacy_id in zip((row["home_team_id"], row["away_team_id"]), sides):
                crosswalk[pitch_id].add((legacy_id, ref, fid))
                reverse[legacy_id].add(pitch_id)
    coverage["pitchapi_prematch_files"] = len(
        _read_git(root, "ls-tree", "-r", "--name-only", "HEAD", "data/pitchapi/prematch").splitlines())
    histories = defaultdict(list)
    for fid, (_, _, teams) in api.items():
        if fid not in excluded:
            for tid, history in teams.items():
                histories[tid].append(history)
    verified = {}
    for tid, records in crosswalk.items():
        legacy_ids = {r[0] for r in records}
        if len(legacy_ids) == 1:
            legacy = next(iter(legacy_ids))
            if reverse[legacy] == {tid}:
                verified[tid] = {"legacy_team_id": legacy, "evidence": [
                    {"source_ref": ref, "legacy_fixture_id": fid} for _, ref, fid in sorted(records)
                ]}
    coverage["verified_team_ids"] = len(verified)
    return histories, verified, fixture_links, dict(coverage)


def archived_quotes(collection, fixtures, cutoff, queue_cutoff):
    """Inventory all archived shot-like contracts and return only exact reviewed quotes."""
    if (collection.get("schema") != "github-models-oddspapi-poland-collection-v1"
            or collection.get("provider") != "OddsPapi" or collection.get("bookmakers") != ["superbet.pl"]):
        return {}, {"status": "archive_unavailable_or_unverified"}
    links = defaultdict(list)
    for link in collection.get("links", {}).get("links", []):
        if link.get("status") == "matched":
            links[str(link.get("fixture_id"))].append(link)
    snapshots = Counter(str(s.get("pitch_fixture_id")) for s in collection.get("snapshots", []))
    vendor_ids = Counter(str(z.get("odds_fixture_id")) for group in links.values() for z in group)
    found, ambiguous, inventory = {}, set(), Counter()
    counts = Counter(fulltime_nonplayer_shot_like_quotes=0)
    for snapshot in collection.get("snapshots", []):
        fid = str(snapshot.get("pitch_fixture_id"))
        for quote in snapshot.get("quotes", []):
            if quote.get("bookmaker") != "superbet.pl":
                continue
            counts["superbet_quotes"] += 1
            name = str(quote.get("market_name") or "")
            search = f"{name} {quote.get('market_type') or ''}".casefold()
            if any(word in search for word in SHOT_WORDS):
                counts["shot_like_quotes"] += 1
                if quote.get("player_prop") is False and quote.get("period") == "fulltime":
                    counts["fulltime_nonplayer_shot_like_quotes"] += 1
                inventory[(str(quote.get("market_id")), name, str(quote.get("market_type")),
                           str(quote.get("period")), str(quote.get("player_prop")))] += 1
            rules = VERIFIED_MARKETS.get(str(quote.get("market_id")))
            if (not rules or fid not in fixtures or len(links[fid]) != 1 or snapshots[fid] != 1
                    or vendor_ids[str(snapshot.get("fixture_id"))] != 1):
                continue
            fixture, link = fixtures[fid], links[fid][0]
            family, scope, label, market_type, line, outcomes = rules
            if (snapshot.get("provider") != "oddspapi-v4"
                    or link.get("match_rule") != "verified_country_league_teams_kickoff"
                    or str(link.get("odds_fixture_id")) != str(snapshot.get("fixture_id"))
                    or str(link.get("tournament_id")) != str(snapshot.get("tournament_id"))
                    or any(link.get(k) != fixture.get(k) for k in ("home", "away", "league"))
                    or quote.get("player_prop") is not False or str(quote.get("player_id")) != "0"
                    or (name, quote.get("market_type"), quote.get("handicap")) != (label, market_type, line)):
                continue
            side = outcomes.get(str(quote.get("outcome_id")))
            if not side or quote.get("outcome_name") != side.title():
                continue
            try:
                kickoff = timestamp(fixture["kickoff_utc"])
                if (timestamp(snapshot.get("kickoff_utc")) != kickoff
                        or timestamp(link.get("kickoff_utc")) != kickoff
                        or timestamp(snapshot.get("captured_at_utc")) < timestamp(queue_cutoff)):
                    continue
            except ValueError:
                continue
            team_id = fixture.get(scope + "_team_id") if scope != "match" else None
            record = {
                "source": "oddspapi-v4", "bookmaker": quote["bookmaker"], "fixture_id": fid,
                "odds_fixture_id": str(snapshot["fixture_id"]), "team_id": team_id,
                "market_id": quote["market_id"], "outcome_id": quote["outcome_id"],
                "family": family, "scope": scope, "period": quote.get("period"), "line": line,
                "selection": side, "odds": quote.get("odds"), "market_name": name,
                "market_identity_verified": True, "captured_at_utc": snapshot.get("captured_at_utc"),
                "changed_at_utc": quote.get("changed_at_utc"),
            }
            if archived_quote_eligible(record, fixture_kickoff_utc=fixture["kickoff_utc"],
                                       forecast_cutoff_utc=cutoff, fixture_id=fid, team_id=team_id):
                key = (fid, family, scope, line, side)
                if key in found and found[key] != record:
                    ambiguous.add(key)
                found[key] = record
    quotes = {k: v for k, v in found.items() if k not in ambiguous}
    return quotes, {"status": "archived_quotes_verified" if quotes else "exact_quotes_unavailable",
                    "quotes_verified": len(quotes), "ambiguous_selections": len(ambiguous), **counts,
                    "shot_like_markets": [
                        dict(zip(("market_id", "market_name", "market_type", "period", "player_prop",
                                  "quotes"), (*k, count)))
                        for k, count in sorted(inventory.items())]}
