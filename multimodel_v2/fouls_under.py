"""Independent observational fouls UNDER filter. No TOP, PLAY, P or N writes."""
from __future__ import annotations

from copy import deepcopy

from .source_manifest import build_source_manifest, instant, number

NO_CANDIDATES = "BRAK ZWERYFIKOWANYCH KANDYDATUR"
BELOW_THRESHOLD = "EKSPERYMENT/POZA PROGIEM/NIE PLAY"
WATCH = "OBSERWUJ"


def fouls_under_watchlist(report_date, runs, snapshots, *, as_of):
    """Only exact, regulation-time team/match quotes in [1.50, 2.00].

    The API assessment is copied, never calculated or interpreted as P(HIT).
    Sub-67 assessments remain visible with an explicit experimental status.
    Use the supplied cutoff as the real observation time, never backdate it.
    """
    manifest = build_source_manifest(report_date, runs, snapshots, as_of=as_of)
    cutoff = instant(as_of)
    candidates, rejections = [], []
    for record in manifest["records"]:
        identity = record["market_identity"]
        if identity["market"] != "fouls" or identity["direction"] != "under":
            continue
        reason = None
        if identity["settlement_period"] != "regulation_time":
            reason = "not_90_minutes"
        elif cutoff >= instant(record["kickoff"]):
            reason = "kickoff_reached"
        try:
            score = number(record["final_assessment_pct"])
            if not 0 <= score <= 100:
                raise ValueError("invalid_api_assessment")
        except ValueError:
            reason = "missing_or_invalid_api_assessment"
        quotes = [q for q in record["quotes"] if number("1.50") <= number(q["selected_odd"]) <= number("2.00")]
        if not quotes:
            reason = reason or "odds_outside_band"
        if reason:
            rejections.append({"market_identity": deepcopy(identity), "reason": reason})
            continue
        quote = sorted(quotes, key=lambda q: (-number(q["selected_odd"]),
                                             q["bookmaker"], q["provider_updated_at"]))[0]
        candidates.append({"date": report_date, "market_identity": deepcopy(identity),
                           "home": record["home"], "away": record["away"],
                           "kickoff": record["kickoff"], "api_assessment": str(score),
                           "quote": deepcopy(quote), "source": deepcopy(record["source"]),
                           "status": BELOW_THRESHOLD if score < 67 else WATCH})
    candidates.sort(key=lambda c: (c["kickoff"], c["market_identity"]["fixture_id"],
                                    str(c["market_identity"])))
    status = NO_CANDIDATES
    if candidates:
        status = WATCH if any(c["status"] == WATCH for c in candidates) else BELOW_THRESHOLD
    return {"schema": "multimodel-v2-fouls-under-v1", "date": report_date,
            "as_of": manifest["as_of"], "coverage": manifest["status"],
            "status": status,
            "candidates": candidates, "rejections": manifest["rejections"] + rejections}
