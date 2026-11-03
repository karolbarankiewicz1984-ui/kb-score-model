"""Paced, bounded API-Football reads shared by the separate API Market jobs.

Provider limits: https://www.api-football.com/news/post/how-ratelimit-works
No files, model parameters or KB Score data are read or written here.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime


class ApiLimitError(RuntimeError):
    pass


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class ApiClient:
    def __init__(self, min_interval=0.35, max_attempts=4):
        self.interval = min_interval
        self.max_attempts = max_attempts
        self.next_request = 0.0
        self.blocked = None

    def _observe_headers(self, headers):
        # Daily allowance and per-minute speed are different provider limits.
        limit = number(headers.get("x-ratelimit-limit"))
        if limit is not None and limit > 0:
            self.interval = max(self.interval, 60.0 / (limit * 0.8))
            self.next_request = max(self.next_request, time.monotonic() + self.interval)
        if number(headers.get("x-ratelimit-remaining")) == 0:
            self.next_request = max(self.next_request, time.monotonic() + 61.0)
        if number(headers.get("x-ratelimit-requests-remaining")) == 0:
            self.blocked = ApiLimitError("API-Football daily request allowance exhausted; no further requests sent")

    def _retry(self, endpoint, attempt, reason, headers, rate_limited=False):
        if self.blocked:
            raise self.blocked
        if attempt + 1 >= self.max_attempts:
            error = ApiLimitError(f"API-Football {endpoint}: {reason} after {self.max_attempts} attempts")
            if rate_limited:
                self.blocked = error
            raise error
        delay = min(60.0 * 2 ** attempt, 120.0) if rate_limited else 2.0 ** (attempt + 1)
        retry_after = headers.get("retry-after")
        seconds = number(retry_after)
        if seconds is None and retry_after:
            try:
                seconds = parsedate_to_datetime(retry_after).timestamp() - time.time()
            except (TypeError, ValueError, OverflowError):
                pass
        if seconds is not None:
            delay = max(delay, seconds)
        self.next_request = max(self.next_request, time.monotonic() + delay)
        print(f"API-Football {endpoint}: {reason}; retry {attempt + 2}/{self.max_attempts} after at least {delay:.0f}s", file=sys.stderr, flush=True)

    def get(self, base, key, endpoint, **params):
        if not key:
            raise RuntimeError("Missing API_FOOTBALL_KEY")
        url = f"{base}/{endpoint}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"x-apisports-key": key})
        for attempt in range(self.max_attempts):
            if self.blocked:
                raise self.blocked
            delay = self.next_request - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self.next_request = time.monotonic() + self.interval
            try:
                with urllib.request.urlopen(request, timeout=40) as response:
                    headers = {k.lower(): v for k, v in response.headers.items()}
                    payload = json.load(response)
                self._observe_headers(headers)
            except urllib.error.HTTPError as exc:
                headers = {k.lower(): v for k, v in (exc.headers or {}).items()}
                self._observe_headers(headers)
                code = exc.code
                exc.close()
                if code not in {429, 499, 500, 502, 503, 504}:
                    raise
                self._retry(endpoint, attempt, f"HTTP {code}", headers, rate_limited=code == 429)
                continue
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                self._retry(endpoint, attempt, "temporary connection failure", {})
                continue
            errors = payload.get("errors") or {}
            if isinstance(errors, dict) and any(k.lower() == "ratelimit" for k in errors):
                # Some provider errors arrive as JSON with HTTP 200.
                self._retry(endpoint, attempt, "rateLimit", headers, rate_limited=True)
                continue
            # Preserve successful data, even if it consumed the last daily call.
            # Other provider validation errors remain visible to the caller.
            return payload, headers
