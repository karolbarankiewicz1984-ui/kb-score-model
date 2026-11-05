"""Immutable pre-match API publications and deterministic calibration inputs."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from api_market_policy import candidate_key, target_date

ROOT = Path("data/api_football")


def parse_time(value):
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, TypeError):
        return None


def dumps(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def archive_publication(payload, target, policy, now=None):
    target = target_date(target)
    now = now or datetime.now(timezone.utc)
    payload = dict(payload)
    # Do not issue a new prediction for an event which started during the scan.
    background = []
    for old in payload.get("background_candidates") or []:
        item = dict(old)
        kickoff = parse_time(item.get("kickoff"))
        item["prematch_verified"] = bool(kickoff and kickoff > now)
        background.append(item)
    payload["background_candidates"] = background
    valid_keys = {candidate_key(x) for x in background if x["prematch_verified"]}
    payload["top_positions"] = [x for x in payload.get("top_positions") or [] if candidate_key(x) in valid_keys]
    payload["publication"] = {
        "model_version": policy["model_version"],
        "captured_at_utc": now.isoformat(),
        "code_revision": os.environ.get("GITHUB_SHA"),
        "policy": policy,
        "provenance": "live_pre_match",
    }
    digest = hashlib.sha256(dumps(payload).encode()).hexdigest()[:16]
    publication_id = f"{now.strftime('%H%M%S%f')}-{digest}"
    payload["publication"]["id"] = publication_id
    folder = ROOT / "predictions" / target
    folder.mkdir(parents=True, exist_ok=True)
    current = ROOT / "market_scan" / f"{target}.json"
    if current.exists():
        old_text = current.read_text(encoding="utf-8")
        old = json.loads(old_text)
        if not old.get("publication"):
            # Preserve legacy bytes without inventing their capture time/provenance.
            legacy = folder / ("legacy-" + hashlib.sha256(old_text.encode()).hexdigest()[:16] + ".json")
            if not legacy.exists():
                with legacy.open("x", encoding="utf-8") as handle:
                    handle.write(old_text)
    frozen = folder / f"{publication_id}.json"
    with frozen.open("x", encoding="utf-8") as handle:
        handle.write(dumps(payload))
    atomic_write(current, dumps(payload))
    return payload


def frozen_candidates(target):
    """Earliest verified prediction per selection/version; never count reruns twice."""
    target = target_date(target)
    snapshots = []
    for path in sorted((ROOT / "predictions" / target).glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        pub = payload.get("publication") or {}
        captured = parse_time(pub.get("captured_at_utc"))
        if captured and pub.get("provenance") == "live_pre_match":
            snapshots.append((captured, path, payload))
    chosen = {}
    for captured, path, payload in sorted(snapshots, key=lambda x: (x[0], str(x[1]))):
        pub = payload["publication"]
        published = {candidate_key(x) for x in payload.get("top_positions") or []}
        for item in payload.get("background_candidates") or []:
            kickoff = parse_time(item.get("kickoff"))
            if not kickoff or captured >= kickoff or item.get("prematch_verified") is not True:
                continue
            key = candidate_key(item)
            identity = f"{target}|{pub['model_version']}|{key}"
            if identity not in chosen:
                chosen[identity] = dict(item, observation_id=identity,
                    prediction_id=pub["id"], prediction_path=str(path),
                    model_version=pub["model_version"], captured_at_utc=pub["captured_at_utc"],
                    published=key in published, ever_published=key in published,
                    training_eligible=True)
            elif key in published:
                chosen[identity]["ever_published"] = True
    return list(chosen.values())
