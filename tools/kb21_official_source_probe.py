"""Probe public organizer URLs, never infer fixture coverage from HTTP success.

Research-only metadata: UTC observation time, response URL/status, content-type,
up to 128 KiB of body SHA256 (not stored). This is NOT actual fixture extraction,
not source authenticity, not official match-card completeness and NOT a signature.
"""
import argparse
import hashlib
import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from tools.kb21_official_review import OFFICIAL_PAGES

MAX_SAMPLE = 131072
TIMEOUT = 9


def _host(url):
    try:
        parsed = urlsplit(url)
        return parsed.hostname.lower() if parsed.scheme == "https" and parsed.hostname else None
    except (ValueError, AttributeError, TypeError):
        return None


def _related_host(start, redirected):
    a, b = _host(start), _host(redirected)
    if not a or not b:
        return False
    a = a.removeprefix("www.")
    b = b.removeprefix("www.")
    return a == b or a.endswith("." + b) or b.endswith("." + a)


def probe(code, url, opener=urllib.request.urlopen, clock=None):
    if not _host(url):
        raise ValueError("Only fixed public HTTPS organizer URLs are accepted")
    clock = clock or (lambda: datetime.now(timezone.utc))
    result = {
        "league_id": code, "organizer_url": url,
        "observed_at_utc": None, "http_status": None,
        "status": "FETCH_FAILED", "response_url": None,
        "content_type": None, "sample_bytes": 0,
        "sample_sha256": None, "sample_truncated": None,
        "fixture_list_extracted": False, "full_day_verified": False,
        "reviewer_signed": False, "calendar_gate": "BLOCKED",
    }
    request = urllib.request.Request(
        url, headers={
            "User-Agent": "KBScore21FixtureAudit/1.0 (+public research only)",
            "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.2",
        }
    )
    try:
        with opener(request, timeout=TIMEOUT) as response:
            status = getattr(response, "status", None)
            final_url = response.geturl()
            raw = response.read(MAX_SAMPLE + 1)
            result["http_status"] = status
            result["response_url"] = final_url
            result["content_type"] = response.headers.get("Content-Type")
            result["sample_bytes"] = min(len(raw), MAX_SAMPLE)
            result["sample_truncated"] = len(raw) > MAX_SAMPLE
            result["sample_sha256"] = hashlib.sha256(raw[:MAX_SAMPLE]).hexdigest()
            if not _related_host(url, final_url):
                result["status"] = "CROSS_HOST_REDIRECT_REQUIRES_REVIEW"
            elif status is not None and not 200 <= status < 300:
                result["status"] = "NON_SUCCESS_HTTP_STATUS"
            elif len(raw) == 0:
                result["status"] = "EMPTY_HTTP_BODY"
            else:
                result["status"] = ("HTTP_ACCESSIBLE_PARTIAL_SAMPLE"
                                    if result["sample_truncated"]
                                    else "HTTP_ACCESSIBLE_SAMPLE")
    except urllib.error.HTTPError as exc:
        result["http_status"] = exc.code
        result["status"] = "HTTP_ERROR"
        result["error_category"] = str(exc.code)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        result["status"] = "FETCH_FAILED"
        result["error_category"] = type(exc).__name__
    result["observed_at_utc"] = clock().astimezone(timezone.utc).isoformat()
    return result


def collect(days, opener=urllib.request.urlopen, clock=None):
    if not isinstance(days, list) or len(days) not in (1, 2, 3):
        raise ValueError("Expected a 1–3 day requested scope")
    if len(set(days)) != len(days):
        raise ValueError("Duplicate requested day")
    for day in days:
        datetime.strptime(day, "%Y-%m-%d")
    sources = list(OFFICIAL_PAGES.items())
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda p: probe(p[0], p[1], opener=opener, clock=clock), sources))
    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {
        "schema": "kb21-organizer-url-probe-v1",
        "days": sorted(days), "calendar_gate": "BLOCKED",
        "status": "HTTP_EVIDENCE_ONLY",
        "publication": "DIAGNOSTIC / NO PLAY",
        "sources": rows, "status_counts": dict(sorted(counts.items())),
        "all_organizers_authenticated": False,
        "any_fixture_list_verified": False, "reviewer_signed": False,
        "note": ("HTTP availability and sampled body hashes show which source pages can be reached "
                 "on this run. They DO NOT prove the page contains the requested matches, "
                 "the complete official day, no games or a valid manual signoff. "
                 "Never unblock KB21 Calendar Gate on HTTP success.")
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("assessment_queue")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    queue = json.loads(Path(args.assessment_queue).read_text(encoding="utf-8"))
    report = collect(queue.get("days"))
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"KB21 official URL probes: {report['status_counts']}; no Calendar Gate approval")


if __name__ == "__main__":
    main()
