"""Research event-market forecasts from observed prematch historical samples."""
import math
from github_models.reviewed_resolver import resolve_reviewed as resolve
from github_models.competition_identity import canonicalize, country_code
from github_models.elo_engine import eligible_history, utc
from github_models.settlement import fixture_index

# Additional half-integer lines reuse the SAME observed data, Poisson model
# and frozen cutoff. No market odds are guessed and A/B/C thresholds unchanged.
THRESHOLDS = {"goals": (0.5, 1.5, 2.5, 3.5, 4.5),
              "corners": (6.5, 7.5, 8.5, 9.5, 10.5, 11.5),
              "cards": (2.5, 3.5, 4.5), "fouls": (19.5, 22.5, 25.5)}
MIN_LEAGUE = 60
MIN_TEAM = 8

def poisson_over(mean, line):
    """P(X > line) for a Poisson count and a nonnegative half-goal line.

    Sum the smaller tail directly, avoiding loss of tiny probabilities in
    1-CDF. Integer lines are deliberately unsupported: they require a push
    probability and their UNDER probability is not the OVER complement.
    """
    if isinstance(mean, bool) or not isinstance(mean, (int, float)) or not math.isfinite(mean) or mean < 0:
        raise ValueError("invalid_rate")
    if (isinstance(line, bool) or not isinstance(line, (int, float))
            or not math.isfinite(line) or line < 0 or line % 1 != 0.5):
        raise ValueError("unsupported_line_requires_nonnegative_half_integer")
    if mean == 0:
        return 0.0
    threshold = math.floor(line)
    if threshold < mean:
        term = math.exp(-mean + threshold * math.log(mean) - math.lgamma(threshold + 1))
        terms = [term]
        total = term
        k = threshold
        while k > 0 and term > 0:
            term *= k / mean
            terms.append(term)
            total += term
            k -= 1
            if term <= total * 1e-16:
                break
        probability = 1 - math.fsum(terms)
    else:
        k = threshold + 1
        term = math.exp(-mean + k * math.log(mean) - math.lgamma(k + 1))
        terms = [term]
        total = term
        while term > 0:
            k += 1
            term *= mean / k
            terms.append(term)
            total += term
            if term <= total * 1e-16:
                break
        probability = math.fsum(terms)
    if not math.isfinite(probability):
        raise ValueError("nonfinite_poisson_probability")
    return max(0.0, min(1.0, probability))


def _event_samples(rows, *, market, league, cutoff, country=None):
    """Unique nonnegative observed integer counts; contradictions fail closed."""
    grouped = {}
    for row in rows:
        try:
            canonical = canonicalize(row)
            # A matching generic league label cannot turn Brazilian Serie A
            # statistics into Italian samples, or Austrian Bundesliga into
            # German samples. Legacy imports without provider metadata retain
            # their explicit importer league label; supplied metadata must agree.
            if canonical["league"] != league:
                continue
            if (country and any(row.get(field) for field in ("country_code", "country", "league_id"))
                    and country_code(canonical.get("country_code")) != country):
                continue
            values = row["events"][market]
            if (not isinstance(values, (list, tuple))
                    or len(values) != 2 or any(type(v) is not int or v < 0 or not math.isfinite(float(v)) for v in values)
                    or not all(isinstance(row[key], str) and row[key].strip() for key in ("home", "away"))
                    or row["home"] == row["away"]):
                continue
            completed, published = utc(row["completed_at_utc"]), utc(row["published_at_utc"])
            if not completed < cutoff or not completed <= published <= cutoff:
                continue
            # Legacy rows have a conservative completion date+2d but no ID.
            # Including both teams prevents unrelated same-day games merging.
            key = (row["league"], row.get("match_date") or completed.isoformat(), row["home"], row["away"])
            grouped.setdefault(key, []).append((row, tuple(values), published))
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    samples = []
    for matches in grouped.values():
        if len({values for _, values, _ in matches}) != 1:
            continue
        row, values, _ = min(matches, key=lambda item: item[2])
        samples.append((row, values))
    return samples

def run(queue, history, event_history, as_of_utc):
    now = utc(as_of_utc)
    fixture_index(queue)
    verified_results = eligible_history(history, frozen_at_utc=as_of_utc)
    out, blockers = [], []
    for fixture in queue["fixtures"]:
        kick = utc(fixture["kickoff_utc"])
        if kick <= now:
            continue
        try:
            mapped = resolve(canonicalize(fixture), verified_results)
        except (ValueError, KeyError, TypeError) as exc:
            for market in THRESHOLDS:
                blockers.append({"fixture_id":fixture["fixture_id"],"market":market,"reason":"team_mapping_unverified"})
            continue
        for market, lines in THRESHOLDS.items():
            if market == "goals":
                valid = [(r, (r["home_goals"], r["away_goals"])) for r in verified_results
                         if r["league"] == mapped["league"]]
            else:
                valid = _event_samples(event_history, market=market, league=mapped["league"], cutoff=now,
                                       country=country_code(mapped.get("country_code")))
            home_rows = [v for r,v in valid if r["home"] == mapped["home"] or r["away"] == mapped["home"]]
            away_rows = [v for r,v in valid if r["home"] == mapped["away"] or r["away"] == mapped["away"]]
            if len(valid) < MIN_LEAGUE or min(len(home_rows),len(away_rows)) < MIN_TEAM:
                blockers.append({"fixture_id":fixture["fixture_id"],"market":market,
                    "reason":"insufficient_verified_history","league_n":len(valid),
                    "home_n":len(home_rows),"away_n":len(away_rows)})
                continue
            league_mean = sum(sum(v) for _,v in valid)/len(valid)
            hmean = sum(sum(v) for v in home_rows)/len(home_rows)
            amean = sum(sum(v) for v in away_rows)/len(away_rows)
            # Shrink sparse team totals to observed league baseline.
            hrate = (len(home_rows)*hmean+20*league_mean)/(len(home_rows)+20)
            arate = (len(away_rows)*amean+20*league_mean)/(len(away_rows)+20)
            rate = (hrate+arate)/2
            for line in lines:
                p = poisson_over(rate,line)
                out.append({"fixture_id":fixture["fixture_id"],"model_id":"observed-events-poisson-v1",
                    "market":market,"selection":"over","line":line,"probability":round(p,6),
                    "frozen_at_utc":as_of_utc,"probability_status":"uncalibrated_research",
                    "source":"football-data.co.uk","league_n":len(valid),
                    "home_n":len(home_rows),"away_n":len(away_rows),
                    "expected_rate":rate,"statistic":"yellow_cards" if market == "cards" else market,
                    "resolved_identity":{key:mapped[key] for key in
                        ("league","country_code","league_id","home","away","home_id","away_id",
                         "home_team_id","away_team_id","source_provider") if key in mapped},
                    "method":"Poisson with shrinkage of observed team match totals"})
                out.append({"fixture_id":fixture["fixture_id"],"model_id":"observed-events-poisson-v1",
                    "market":market,"selection":"under","line":line,"probability":round(1-p,6),
                    "frozen_at_utc":as_of_utc,"probability_status":"uncalibrated_research",
                    "source":"football-data.co.uk","league_n":len(valid),
                    "home_n":len(home_rows),"away_n":len(away_rows),
                    "expected_rate":rate,"statistic":"yellow_cards" if market == "cards" else market,
                    "resolved_identity":{key:mapped[key] for key in
                        ("league","country_code","league_id","home","away","home_id","away_id",
                         "home_team_id","away_team_id","source_provider") if key in mapped},
                    "method":"Poisson with shrinkage of observed team match totals"})
    return {"schema":"github-models-event-markets-v1","generated_at_utc":as_of_utc,
            "markets":out,"blockers":blockers,"production_multimodel_unchanged":True}
