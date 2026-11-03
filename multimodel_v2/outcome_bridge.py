"""Join native settlements to original publications and existing final receipts.

No provider calls, guessed quote selection, default settlement period, price,
ID or final-whistle timestamp. Native result functions are supplied unchanged.
"""
from copy import deepcopy

from .capture import verify_provider_capture
from .source_manifest import identifier, instant, market_identity


def final_fixture(receipt, *, fixture_id, kickoff, as_of):
    verify_provider_capture(receipt, as_of=as_of)
    if receipt["provider"] != "API-Football" or receipt["endpoint"] != "fixtures":
        raise ValueError("official_final_fixture_receipt_required")
    response = receipt["response"]
    if not isinstance(response, dict) or response.get("errors"):
        raise ValueError("official_final_response_invalid")
    data = response.get("response")
    if (not isinstance(data, list) or any(not isinstance(r, dict) or not isinstance(r.get("fixture"), dict) for r in data)):
        raise ValueError("official_final_response_invalid")
    rows = [r for r in data if identifier(r["fixture"].get("id")) == identifier(fixture_id)]
    if len(rows) != 1:
        raise ValueError("official_final_fixture_not_unique")
    fixture = rows[0]
    status = fixture["fixture"].get("status")
    if (not isinstance(status, dict) or status.get("short") != "FT"
            or instant(fixture["fixture"].get("date")) != instant(kickoff)
            or not instant(kickoff) < instant(receipt["received_at"])):
        raise ValueError("official_final_fixture_time_or_status_invalid")
    return fixture


def build_linked_native_outcomes(snapshot, observations, receipts, *, as_of, actual_metric, outcome_hit):
    """Evidence adapter, not a replacement settlement algorithm.

    actual_metric and outcome_hit must be the original native callables. Both
    final status and statistics must come from already captured responses.
    """
    result, rejected = [], []
    native_id = snapshot.get("publication", {}).get("id")
    positions = snapshot.get("background_candidates", []) + snapshot.get("top_positions", [])
    for index, observation in enumerate(observations):
        try:
            ids = {identifier(observation[k]) for k in ("publication_id", "prediction_id") if k in observation}
            if ids != {identifier(native_id)}:
                raise ValueError("wrong_native_publication_id")
            key = market_identity(observation.get("market_identity") or observation)
            # Only an explicitly selected quote frozen by the native publisher.
            matches = [row for row in positions if market_identity(row) == key and isinstance(row.get("frozen_quote"), dict)]
            if not matches:
                raise ValueError("original_selected_frozen_quote_missing")
            row = matches[0]
            if any(r["frozen_quote"] != row["frozen_quote"] for r in matches):
                raise ValueError("ambiguous_original_frozen_quote")
            if "frozen_quote" in observation and observation["frozen_quote"] != row["frozen_quote"]:
                raise ValueError("native_observation_frozen_quote_mismatch")
            finals, stats = [], []
            for receipt in receipts:
                verify_provider_capture(receipt, as_of=as_of)
                if receipt["endpoint"] == "fixtures":
                    try:
                        fixture = final_fixture(receipt, fixture_id=row["fixture_id"], kickoff=row["kickoff"], as_of=as_of)
                        finals.append((receipt, fixture))
                    except ValueError:
                        pass
                elif receipt["provider"] == "API-Football" and receipt["endpoint"] == "fixtures/statistics":
                    response = receipt["response"]
                    if not isinstance(response, dict) or not isinstance(response.get("parameters"), dict):
                        raise ValueError("original_statistics_parameters_missing")
                    params = response.get("parameters", {})
                    if str(params.get("fixture")) == str(row["fixture_id"]) and not response.get("errors"):
                        stats.append(receipt)
            if len(finals) != 1 or len(stats) != 1:
                raise ValueError("unique_original_final_and_statistics_receipts_required")
            final, fixture = finals[0]
            stat = stats[0]
            if stat["source"] != final["source"]:
                raise ValueError("final_and_statistics_source_mismatch")
            if instant(stat["requested_at"]) < instant(final["received_at"]):
                raise ValueError("statistics_observed_before_final_status")
            actual = actual_metric(fixture, stat["response"].get("response", []), row)
            if actual is None or observation.get("actual") != actual:
                raise ValueError("native_actual_missing_or_mismatch")
            hit = outcome_hit(float(actual), float(row["line"]), row["direction"])
            if hit not in (0, 1) or observation.get("hit") != hit:
                raise ValueError("native_hit_missing_or_mismatch")
            result.append({"publication_id": native_id, "date": snapshot["date"],
                "market_identity": deepcopy(observation.get("market_identity") or observation),
                "frozen_quote": deepcopy(row["frozen_quote"]), "quote_origin": "same_native_publication_selected_quote",
                "kickoff": row["kickoff"], "fixture_status": "FT", "outcome": "WIN" if hit else "LOSS",
                "actual": actual, "settled_at": stat["received_at"],
                "time_basis": "official_final_status_observation", "final_observed_at": final["received_at"],
                "final_status_receipt": deepcopy(final), "statistics_receipt": deepcopy(stat),
                "result_source": "API-Football:original_captured_final_responses"})
        except (ValueError, KeyError, TypeError) as exc:
            rejected.append({"observation_index": index, "reason": str(exc)})
    return {"observations": result, "rejections": rejected, "n_effect": 0}
