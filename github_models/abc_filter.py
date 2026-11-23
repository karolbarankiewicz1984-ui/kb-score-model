"""Isolated research filters. No model, source or production changes."""
import json
import math
from collections import defaultdict

THRESHOLDS = {"A": .70, "B": .75, "C": .80}

def evaluate(predictions, events):
    by_match = defaultdict(dict)
    for row in predictions["predictions"]:
        p = [row[k] for k in ("p_home", "p_draw", "p_away")]
        if any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 or x > 1 for x in p) or abs(sum(p)-1) > 1e-5:
            raise ValueError("invalid_1x2")
        by_match[str(row["fixture_id"])][row["model_id"]] = p
    out = []
    for fixture_id, models in by_match.items():
        a, b = models.get("github-elo"), models.get("callumfm-dixon-coles")
        if a is None or b is None:
            continue
        for index, selection in enumerate(("1", "X", "2")):
            if abs(a[index]-b[index]) > .10:
                continue
            for variant, minimum in THRESHOLDS.items():
                if min(a[index], b[index]) >= minimum:
                    out.append(dict(fixture_id=fixture_id, market="1X2", selection=selection,
                                    variant=variant, probability_min=min(a[index],b[index]),
                                    status="research_uncalibrated"))
    # Three double-chance outcomes are sums of mutually exclusive 1X2
    # outcomes from EACH frozen model; never multiply or treat as independent.
    # Require both original Elo/DC models and the existing 10pp agreement gate.
    dc_sides = {"1X": (0, 1), "X2": (1, 2), "12": (0, 2)}
    for fixture_id, models in by_match.items():
        elo, dc = models.get("github-elo"), models.get("callumfm-dixon-coles")
        if elo is None or dc is None:
            continue
        for selection, indexes in dc_sides.items():
            p_elo = math.fsum(elo[i] for i in indexes)
            p_dc = math.fsum(dc[i] for i in indexes)
            if abs(p_elo - p_dc) > .10:
                continue
            for variant, minimum in THRESHOLDS.items():
                if min(p_elo, p_dc) >= minimum:
                    out.append(dict(
                        fixture_id=fixture_id, market="double_chance",
                        selection=selection, line=None, variant=variant,
                        probability_min=min(p_elo, p_dc),
                        status="research_uncalibrated",
                        source="two_frozen_1X2_models", correlated_with_1x2=True))
    pairs = defaultdict(dict)
    for row in events.get("markets", []):
        p = row["probability"]
        if type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError("invalid_event_probability")
        key = (str(row["fixture_id"]),row["model_id"],row["market"],row["line"])
        if row["selection"] in pairs[key]:
            raise ValueError("duplicate_selection")
        pairs[key][row["selection"]] = p
    for (fid, model, market, line), sides in pairs.items():
        if set(sides) != {"over","under"} or abs(sum(sides.values())-1)>1e-5:
            raise ValueError("invalid_event_pair")
        for selection, p in sides.items():
            for variant, minimum in THRESHOLDS.items():
                if p >= minimum:
                    out.append(dict(fixture_id=fid, market=market, line=line, selection=selection,
                                    variant=variant, probability=p, model=model,
                                    status="research_single_model_uncalibrated"))
    return dict(schema="github-models-abc-v1", calibration="unverified",
                v2_score="not_computed", candidates=out,
                counts={v:sum(x["variant"]==v for x in out) for v in THRESHOLDS})
