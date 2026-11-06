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
