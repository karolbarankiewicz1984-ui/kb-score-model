"""Record an already received provider response for future native audit.

No provider call or model evaluation occurs here. The receipt identifies raw
response evidence, never a prediction, publication or quote identity. Decoding
an exact quote still requires the provider's fixture/bet/line/team evidence.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from .source_manifest import WARSAW, instant

SCHEMA = "multimodel-v2-provider-receipt-v1"
REPO = Path(__file__).resolve().parents[1]
MAX_BYTES = 8 * 1024 * 1024
PROVIDERS = frozenset({"API-Football", "PitchAPI"})
SECRET_NAMES = {"authorization", "proxyauthorization", "apikey", "apifootballkey", "pitchapiapikey",
                "xapisportskey", "xrapidapikey", "token", "accesstoken", "refreshtoken",
                "password", "clientsecret", "secret"}


def _bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode()


def _digest(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _redact(value, path="", paths=None):
    paths = [] if paths is None else paths
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            here = path + "/" + str(key)
            if re.sub(r"[^a-z0-9]", "", str(key).casefold()) in SECRET_NAMES:
                paths.append(here)
                result[key] = "[REDACTED]"
            else:
                result[key] = _redact(item, here, paths)
        return result
    if isinstance(value, list):
        return [_redact(item, path + "/" + str(i), paths) for i, item in enumerate(value)]
    if isinstance(value, str):
        # Do not preserve credential-bearing diagnostic URLs or header strings.
        cleaned = re.sub(r"(?i)([?&](?:api[_-]?key|token|access_token|key)=)[^&#\s]+", r"\1[REDACTED]", value)
        cleaned = re.sub(r"(?i)\bBearer\s+[^\s]+", "Bearer [REDACTED]", cleaned)
        cleaned = re.sub(r"(?i)((?:x[-_]rapidapi[-_]key|x[-_]apisports[-_]key|pitchapi[-_]api[-_]key|api[-_]football[-_]key|api[-_]?key|refresh[-_]token|access[-_]token|authorization|password|secret)\s*[:=]\s*)[^\s&,;]+",
                         r"\1[REDACTED]", cleaned)
        if cleaned != value:
            paths.append(path)
        return cleaned
    return deepcopy(value)


def capture_provider_response(response, *, provider, endpoint, requested_at, received_at,
                              source, output_root, retention_days=30, clock=None):
    """Fresh-only hook called AFTER a real existing client received JSON.

    source={run_id, workflow_head_sha, code_checkout_sha}; workflow SHA and
    checkout SHA are intentionally separate. A five-minute recording window is
    a receipt freshness limit, not a model threshold. Past captures can be read
    unchanged; this hook cannot publish them as new historical prematch data.
    """
    if not isinstance(response, (dict, list)):
        raise ValueError("provider_json_response_required")
    if not isinstance(endpoint, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*(?:/[a-z][a-z0-9_-]*)*", endpoint):
        raise ValueError("endpoint_name_without_credentials_required")
    if not isinstance(provider, str) or provider not in PROVIDERS:
        raise ValueError("unsupported_provider_identifier")
    if not isinstance(source, dict):
        raise ValueError("provider_source_required")
    if not re.fullmatch(r"[1-9][0-9]{0,19}", str(source.get("run_id"))):
        raise ValueError("provider_source_native_run_id_required")
    for field in ("workflow_head_sha", "code_checkout_sha"):
        if not re.fullmatch(r"[0-9a-f]{40}", str(source.get(field))):
            raise ValueError("provider_source_sha_required")
    if type(retention_days) is not int or not 1 <= retention_days <= 90:
        raise ValueError("provider_retention_out_of_bounds")
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if isinstance(now, datetime):
        now = instant(now.isoformat())
    else:
        now = instant(now)
    requested, received = instant(requested_at), instant(received_at)
    if not requested <= received <= now or now - received > timedelta(minutes=5):
        raise ValueError("provider_capture_not_fresh")
    original_digest = _digest(response)
    paths = []
    stored = _redact(response, paths=paths)
    body = {"schema": SCHEMA, "provider": provider, "endpoint": endpoint,
            "source": {k: source[k] for k in ("run_id", "workflow_head_sha", "code_checkout_sha")},
            "requested_at": requested_at, "received_at": received_at,
            "recorded_at": now.isoformat(), "expires_at": (now + timedelta(days=retention_days)).isoformat(),
            "response": stored, "original_response_sha256": original_digest,
            "redacted_paths": paths, "purpose": "original_response_evidence_only",
            "creates_native_publication": False, "n_effect": 0}
    envelope = dict(body, integrity={"sha256": _digest(body), "response_sha256": _digest(stored)})
    content = _bytes(envelope)
    if len(content) > MAX_BYTES:
        raise ValueError("provider_capture_size_limit")
    root = Path(output_root).expanduser().resolve()
    if root == REPO or REPO in root.parents:
        raise ValueError("provider_capture_requires_isolated_output")
    directory = root / "raw" / received.astimezone(WARSAW).date().isoformat()
    if not directory.resolve().is_relative_to(root):
        raise ValueError("provider_capture_path_escape")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (envelope["integrity"]["sha256"] + ".json")
    descriptor, temporary = tempfile.mkstemp(prefix=".capture-", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target)  # exclusive, atomic, never overwrites evidence
    finally:
        os.unlink(temporary)
    return target


def verify_provider_capture(envelope, *, as_of):
    if not isinstance(envelope, dict) or envelope.get("schema") != SCHEMA:
        raise ValueError("unsupported_provider_capture")
    if len(_bytes(envelope)) > MAX_BYTES:
        raise ValueError("provider_capture_size_limit")
    if not isinstance(envelope.get("provider"), str) or envelope["provider"] not in PROVIDERS:
        raise ValueError("unsupported_provider_identifier")
    if not isinstance(envelope.get("endpoint"), str) or not re.fullmatch(r"[a-z][a-z0-9_-]*(?:/[a-z][a-z0-9_-]*)*", envelope["endpoint"]):
        raise ValueError("provider_capture_endpoint_invalid")
    source = envelope.get("source")
    if not isinstance(source, dict):
        raise ValueError("provider_capture_source_missing")
    if not re.fullmatch(r"[1-9][0-9]{0,19}", str(source.get("run_id"))):
        raise ValueError("provider_source_native_run_id_required")
    if any(not re.fullmatch(r"[0-9a-f]{40}", str(source.get(k))) for k in ("workflow_head_sha", "code_checkout_sha")):
        raise ValueError("provider_capture_source_sha_invalid")
    if (not isinstance(envelope.get("response"), (dict, list))
            or not re.fullmatch(r"[0-9a-f]{64}", str(envelope.get("original_response_sha256")))
            or envelope.get("purpose") != "original_response_evidence_only"
            or envelope.get("creates_native_publication") is not False):
        raise ValueError("provider_capture_contract_invalid")
    body = {k: v for k, v in envelope.items() if k != "integrity"}
    proof = envelope.get("integrity") or {}
    if proof.get("sha256") != _digest(body) or proof.get("response_sha256") != _digest(envelope.get("response")):
        raise ValueError("provider_capture_digest_mismatch")
    cutoff = instant(as_of)
    requested, received, recorded, expires = [instant(envelope.get(k)) for k in (
        "requested_at", "received_at", "recorded_at", "expires_at")]
    if not requested <= received <= recorded <= cutoff < expires:
        raise ValueError("provider_capture_unavailable_or_expired")
    if recorded - received > timedelta(minutes=5) or not timedelta(days=1) <= expires - recorded <= timedelta(days=90):
        raise ValueError("provider_capture_freshness_or_retention_invalid")
    return envelope


def read_provider_capture(path, *, as_of):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("provider_capture_size_limit")
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("provider_capture_size_limit")
    return verify_provider_capture(json.loads(raw), as_of=as_of)
