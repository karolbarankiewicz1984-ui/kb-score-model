"""Read-only transition policy for MULTIMODEL when legacy feeds are inactive.

This module never promotes overlay percentages to scored picks or treats PitchAPI
context as bookmaker quotes. No network calls and no provider-budget assumptions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourcePolicy:
    api_football_subscription_end: str = "2026-11-04"
    pitchapi_active: bool = True
    pitchapi_internal_request_cap: int | None = None
    kb21_active: bool = False
    consensus_active: bool = False


def classify_sources(
    report_date: str,
    *,
    scored_api_publication: dict[str, Any] | None = None,
    pitchapi_context: dict[str, Any] | None = None,
    api_overlay: dict[str, Any] | None = None,
    policy: SourcePolicy = SourcePolicy(),
) -> dict[str, Any]:
    """Return independent readiness lanes; never fabricate a composite TOP."""
    from datetime import date

    target = date.fromisoformat(report_date)
    expiry = date.fromisoformat(policy.api_football_subscription_end)
    scored = scored_api_publication or {}
    overlay = api_overlay or {}
    pitch = pitchapi_context or {}
    native_scored = (
        scored.get("date") == report_date
        and scored.get("schema") in {"api-market-scan-v3", "api-market-playable-export-v2"}
    )
    # This is source *presence*, not verified prematch pick readiness.
    pitch_present = bool(pitch) and policy.pitchapi_active
    overlay_present = (
        overlay.get("schema") == "api-market-snapshot-v1"
        and overlay.get("date") == report_date
    )
    return {
        "report_date": report_date,
        "api_football_subscription_window": "expires_today_or_earlier"
        if target >= expiry else "before_expiry",
        "pitchapi_context_available": pitch_present,
        "pitchapi_internal_request_cap": policy.pitchapi_internal_request_cap,
        "native_api_scored_source_present": native_scored,
        "overlay_context_only": overlay_present,
        "kb21_source_required": False,
        "consensus_source_required": False,
        "composite_top_authorized": False,
        "api_only_candidates_may_be_verified": native_scored,
        "bookmaker_quotes_verified": False,
        "ready_to_publish_bets": False,
        "blockers": ([] if native_scored else ["native_scored_publication_missing"])
        + ["independent_exact_market_quote_verification_required"],
    }
