"""Preserve dated, immutable-looking (SHA256 checked) UNSIGNED organizer snapshots.

This is a diagnostic vault, not signed human review, a certified complete
calendar, or betting score. GitHub Actions artifacts are immutable by run;
SHA256 detects accidental modification between capture and comparison.
A scheduled job may run late: never label a capture 'pre-kickoff' merely
because its workflow was scheduled for an early clock time.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit
import zipfile

from tools.kb21_fixture_crosscheck import _instant
from tools.kb21_official_research_compare import _team

KIND = {
    "knvb": ("ned.1", "kb21-official-knvb-eredivisie-v1"),
    "fpl": ("eng.1", "kb21-official-premier-league-fpl-v1"),
    "dfl": ("ger.1", "kb21-official-bundesliga-media-v1"),
    "laliga": ("esp.1", "kb21-official-laliga-matchday-html-v1"),
}
SCHEMA = "kb21-early-official-snapshot-v1"
ARTIFACT_PREFIX = "kb21-early-organizer-"
MAX_BYTES = 5_000_000


class NoCrossHostAuthRedirect(HTTPRedirectHandler):
    """Keep GitHub token on api.github.com; never forward it to ZIP storage."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and (
            urlsplit(req.full_url).hostname != urlsplit(newurl).hostname
        ):
            redirected.remove_header("Authorization")
            redirected.remove_header("authorization")
        return redirected


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _read_snapshot(blob, name, days):
    if name not in KIND:
        raise ValueError("Unsupported official snapshot")
    try:
        doc = json.loads(blob)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid organizer JSON") from exc
    league, schema = KIND[name]
    incomplete_flag = ("full_day_coverage_verified" if name == "dfl"
                       else "full_calendar_verified")
    if (not isinstance(doc, dict)
            or doc.get("schema") != schema or doc.get("league_id") != league
            or doc.get("calendar_gate") != "BLOCKED"
            or doc.get("reviewer_signed") is not False
            or doc.get(incomplete_flag) is not False
            or (name == "dfl" and
                doc.get("full_season_coverage_verified") is not False)
            or set(doc.get("days", [])) != set(days)
            or not isinstance(doc.get("by_day"), dict)
            or set(doc["by_day"]) != set(days)
            or not all(isinstance(doc["by_day"][day], list) for day in days)
            or _instant(doc.get("captured_at_utc")) is None):
        raise ValueError("Organizer snapshot scope or safety flags invalid")
    if name == "laliga":
        # LaLiga scans only a LIMITED window of matchdays. A valid snapshot
        # can corroborate a listed match but cannot certify missing games.
        from tools.kb21_official_laliga import URL
        sources = doc.get("sources")
        rounds = doc.get("rounds_scanned")
        if (doc.get("status") not in (
                "OFFICIAL_PARTIAL_MATCHDAY_WINDOW_FOR_REVIEW",
                "NO_USABLE_OFFICIAL_MATCHES")
                or not isinstance(rounds, list)
                or not isinstance(sources, list)
                or len(rounds) != len(sources)
                or not isinstance(doc.get("errors"), list)
                or not isinstance(doc.get("season"), str)):
            raise ValueError("Invalid LaLiga partial-round evidence metadata")
        declared = {}
        for entry in sources:
            if (not isinstance(entry, dict)
                    or not isinstance(entry.get("round"), int)
                    or isinstance(entry.get("round"), bool)
                    or entry["round"] in declared
                    or entry["round"] not in rounds
                    or entry.get("url") != URL.format(
                        season=doc["season"], round=entry["round"])
                    or entry.get("status") not in (
                        "PARSED_MATCHDAY", "UNREADABLE_OR_EMPTY_MATCHDAY",
                        "FETCH_ERROR")):
                raise ValueError("LaLiga scan references a wrong matchday")
            declared[entry["round"]] = entry["status"]
        if set(declared) != set(rounds):
            raise ValueError("Incomplete LaLiga scan metadata")
        for day in days:
            for fixture in doc["by_day"][day]:
                if (not isinstance(fixture, dict)
                        or fixture.get("league_id") != "esp.1"
                        or fixture.get("date_warsaw") != day
                        or not isinstance(fixture.get("round"), int)
                        or declared.get(fixture["round"]) != "PARSED_MATCHDAY"
                        or fixture.get("official_url") != URL.format(
                            season=doc["season"], round=fixture["round"])
                        or _instant(fixture.get("kickoff_utc")) is None):
                    raise ValueError("LaLiga match claim lacks a parsed official round")
    return doc


def package(days, snapshot_files, outdir, generated_at=None):
    if (not isinstance(days, list) or len(days) != len(set(days))
            or not 1 <= len(days) <= 3):
        raise ValueError("Expected one to three different Warsaw calendar days")
    days = sorted(dt.date.fromisoformat(d).isoformat() for d in days)
    now = generated_at or dt.datetime.now(dt.timezone.utc)
    if not isinstance(now, dt.datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("A timezone-aware vault creation time is mandatory")
    destination = Path(outdir)
    destination.mkdir(parents=True, exist_ok=True)
    sources = {}
    for name, path in snapshot_files.items():
        if name not in KIND:
            raise ValueError("Unrecognized organizer")
        blob = Path(path).read_bytes()
        doc = _read_snapshot(blob, name, days)
        if _instant(doc["captured_at_utc"]) > now + dt.timedelta(minutes=5):
            raise ValueError("Capture timestamp lies in the future")
        target_name = name + ".json"
        (destination / target_name).write_bytes(blob)
        sources[name] = {
            "filename": target_name,
            "league_id": KIND[name][0],
            "sha256": _digest(blob),
            "captured_at_utc": doc["captured_at_utc"],
            "visible_scoped_rows": sum(len(doc["by_day"][day]) for day in days),
            "source_errors": doc.get("errors", []),
            "snapshot_is_signed": False,
        }
    if not sources:
        raise ValueError("No source snapshots to preserve")
    manifest = {
        "schema": SCHEMA, "days": days, "created_at_utc": now.astimezone(
            dt.timezone.utc).isoformat(), "sources": sources,
        "calendar_gate": "BLOCKED", "publication": "DIAGNOSTIC / NO PLAY",
        "prematch_status": "NOT_ESTABLISHED_UNTIL_INDEPENDENT_KICKOFF_CHECK",
        "human_approval": None, "official_day_completeness_verified": False,
        "note": ("Snapshot capture timestamp is NOT proof of prematch timing. "
                 "Must check against first ESPN kickoff for the ENTIRE date; "
                 "no retroactive signoff or historical N."),
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    return manifest


def verify(folder):
    path = Path(folder)
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if (not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA
            or manifest.get("calendar_gate") != "BLOCKED"
            or manifest.get("human_approval") is not None
            or manifest.get("official_day_completeness_verified") is not False
            or manifest.get("prematch_status")
            != "NOT_ESTABLISHED_UNTIL_INDEPENDENT_KICKOFF_CHECK"
            or not isinstance(manifest.get("days"), list)
            or not isinstance(manifest.get("sources"), dict)):
        raise ValueError("Invalid/approved early capture manifest")
    days = manifest["days"]
    if not 1 <= len(days) <= 3 or len(set(days)) != len(days):
        raise ValueError("Early capture dates invalid")
    for day in days:
        dt.date.fromisoformat(day)
    sources = {}
    for name, record in manifest["sources"].items():
        if name not in KIND or record.get("filename") != name + ".json":
            raise ValueError("Invalid source name in manifest")
        blob = (path / (name + ".json")).read_bytes()
        if _digest(blob) != record.get("sha256"):
            raise ValueError("Official snapshot checksum mismatch")
        doc = _read_snapshot(blob, name, days)
        if doc["captured_at_utc"] != record.get("captured_at_utc"):
            raise ValueError("Source capture time differs from manifest")
        sources[name] = doc
    return manifest, sources


def match_before_whole_day_start(queue, vaults):
    """Give per-match dated organizer comparison, but never approve PLAY.

    Only an archive captured STRICTLY before the earliest valid ESPN start
    across all 14 competitions that day is admissible. If any kickoff is
    missing, time window is UNKNOWN and no early-snapshot match is returned.
    """
    if (not isinstance(queue, dict) or not isinstance(queue.get("days"), list)
            or not isinstance(queue.get("fixtures"), list)):
        raise ValueError("Invalid independent ESPN candidate queue")
    days = queue["days"]
    all_days = {}
    for day in days:
        matches = [f for f in queue["fixtures"] if f.get("date_warsaw") == day]
        start_times = [_instant(f.get("kickoff")) for f in matches]
        all_days[day] = (min(start_times) if matches and all(start_times)
                         else None)
    findings = {}
    for day in days:
        for fixture in queue["fixtures"]:
            if fixture.get("date_warsaw") != day:
                continue
            fixture_id = fixture.get("fixture_id")
            league = str(fixture_id).rsplit(":", 1)[0]
            if league not in {v[0] for v in KIND.values()}:
                continue
            key = (day, fixture_id)
            if key in findings:
                raise ValueError("Duplicate candidate fixture")
            findings[key] = {
                "status": "NO_ELIGIBLE_EARLY_OFFICIAL_CAPTURE",
                "official_kickoff_from_early_capture": None,
                "capture_at_utc": None,
                "prematch_clock_review_only": True,
                "calendar_gate": "BLOCKED",
            }
            if all_days[day] is None:
                findings[key]["status"] = "NO_SAFE_ENTIRE_DAY_KICKOFF_WINDOW"
                continue
            name = next(k for k, v in KIND.items() if v[0] == league)
            eligible = []
            for folder in vaults:
                manifest, sources = verify(folder)
                if day not in manifest["days"] or name not in sources:
                    continue
                doc = sources[name]
                captured = _instant(doc["captured_at_utc"])
                if (captured >= all_days[day] or captured.date()
                        < dt.date.fromisoformat(day) - dt.timedelta(days=3)):
                    continue
                if doc.get("errors") or (name == "fpl" and
                    doc.get("season_full_380_catalogue") is not True) or (
                    name == "knvb" and doc.get("status")
                    != "OFFICIAL_KNVB_PAGE_PARTIAL_FOR_REVIEW") or (
                    name == "dfl" and (
                    doc.get("status") != "OFFICIAL_PAGE_PARTIAL_MATCHDAY_FOR_REVIEW"
                    or doc.get("table_headers_detected") is not True
                    or doc.get("page_invalid_row_count") != 0)) or (
                    name == "laliga" and (
                    doc.get("status") != "OFFICIAL_PARTIAL_MATCHDAY_WINDOW_FOR_REVIEW"
                    or doc.get("errors"))):
                    continue
                eligible.append((captured, doc))
            if not eligible:
                continue
            captured, selected = max(eligible, key=lambda item: item[0])
            teams = str(fixture.get("fixture") or "").split(" - ", 1)
            independent_time = _instant(fixture.get("kickoff"))
            if len(teams) != 2 or independent_time is None:
                findings[key]["status"] = "INVALID_INDEPENDENT_FIXTURE"
                continue
            home, away = [_team(league, team) for team in teams]
            official = [x for x in selected["by_day"][day]
                        if _team(league, x.get("home")) == home
                        and _team(league, x.get("away")) == away]
            status = "NOT_IN_EARLY_OFFICIAL_SNAPSHOT"
            official_time = None
            if len(official) > 1:
                status = "DUPLICATE_EARLY_ORGANIZER_PAIRS"
            elif len(official) == 1:
                official_time = _instant(official[0].get("kickoff_utc"))
                if official_time is None:
                    status = "EARLY_ORGANIZER_KICKOFF_MISSING"
                elif abs((official_time - independent_time).total_seconds()) > 300:
                    status = "EARLY_ORGANIZER_KICKOFF_CONFLICT"
                elif name == "fpl" and official[0].get("kickoff_provisional"):
                    status = "EARLY_ORGANIZER_KICKOFF_PROVISIONAL"
                else:
                    status = "EARLY_SNAPSHOT_MATCHED_FOR_REVIEW"
            findings[key] = {
                "status": status,
                "official_kickoff_from_early_capture": (
                    official_time.isoformat() if official_time else None),
                "capture_at_utc": captured.isoformat(),
                "prematch_clock_review_only": True,
                "calendar_gate": "BLOCKED",
            }
    return findings


def restore(repo, directory, token, opener=urlopen, now=None):
    """Fetch recent immutable Action ZIPs; safe names, checksums, bounded bytes.

    No artifact is trusted for PLAY even if the archive is from main.
    """
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid repository identifier")
    if not token:
        raise ValueError("GitHub Actions read token required")
    now = now or dt.datetime.now(dt.timezone.utc)
    header = {"Authorization": "Bearer " + token,
              "Accept": "application/vnd.github+json",
              "User-Agent": "KB21EarlyOrganizerVault/1.0"}
    # The artifact ZIP endpoint returns a 302 to signed object storage.
    # urllib normally copies Authorization across that redirect, which breaks
    # storage signature validation and leaks the API token to another host.
    # Limit bearer credentials to api.github.com; follow only HTTPS redirects.
    def strict_opener(req, timeout):
        if opener is not urlopen:
            return opener(req, timeout=timeout)
        return build_opener(NoCrossHostAuthRedirect()).open(req, timeout=timeout)
    def get(url, limit=MAX_BYTES):
        with strict_opener(Request(url, headers=header), timeout=25) as response:
            blob = response.read(limit + 1)
        if len(blob) > limit:
            raise ValueError("GitHub response exceeds safety cap")
        return blob
    api = "https://api.github.com/repos/" + repo + "/actions/artifacts?per_page=100"
    listing = json.loads(get(api))
    found = []
    for artifact in listing.get("artifacts", []):
        if (not isinstance(artifact, dict)
                or artifact.get("expired")
                or not str(artifact.get("name", "")).startswith(ARTIFACT_PREFIX)
                or artifact.get("workflow_run", {}).get("head_branch") != "main"):
            continue
        stamp = _instant(artifact.get("created_at"))
        if (stamp is None or stamp > now + dt.timedelta(minutes=5)
                or now - stamp > dt.timedelta(days=4)):
            continue
        found.append(artifact)
    found.sort(key=lambda a: a["created_at"], reverse=True)
    restored = []
    for artifact in found[:8]:
        ident = artifact.get("id")
        if not isinstance(ident, int) or isinstance(ident, bool):
            continue
        blob = get(
            "https://api.github.com/repos/" + repo +
            "/actions/artifacts/" + str(ident) + "/zip")
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                listed = set(z.namelist())
                if ("manifest.json" not in listed
                        or len(listed) > len(KIND) + 1
                        or not listed <= {"manifest.json"} | {
                            name + ".json" for name in KIND}):
                    raise ValueError("Unexpected ZIP contents")
                path = Path(directory) / str(ident)
                path.mkdir(parents=True, exist_ok=True)
                for name in listed:
                    info = z.getinfo(name)
                    if info.file_size > 1_000_000:
                        raise ValueError("Source file too large inside artifact")
                    (path / name).write_bytes(z.read(name))
            verify(path)
            restored.append(path)
        except (zipfile.BadZipFile, OSError, ValueError, KeyError) as exc:
            print("::warning::Early organizer artifact rejected: " + type(exc).__name__)
    return restored


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    archive = sub.add_parser("package")
    archive.add_argument("--days", nargs="+", required=True)
    archive.add_argument("--knvb")
    archive.add_argument("--fpl")
    archive.add_argument("--dfl")
    archive.add_argument("--laliga")
    archive.add_argument("--outdir", required=True)
    download = sub.add_parser("restore")
    download.add_argument("--repo", required=True)
    download.add_argument("--outdir", required=True)
    verify_cmd = sub.add_parser("compare")
    verify_cmd.add_argument("--queue", required=True)
    verify_cmd.add_argument("--vault-dir", required=True)
    verify_cmd.add_argument("--output", required=True)
    a = p.parse_args()
    if a.cmd == "package":
        snap = {name: value for name, value in
                (("knvb", a.knvb), ("fpl", a.fpl),
                 ("dfl", a.dfl), ("laliga", a.laliga)) if value}
        out = package(a.days, snap, a.outdir)
        print("Early organizer snapshot captured, NOT pre-match certified:",
              {k: v["visible_scoped_rows"] for k, v in out["sources"].items()})
    elif a.cmd == "restore":
        restored = restore(a.repo, a.outdir, os.getenv("GITHUB_TOKEN", ""))
        print("Recovered prior early organizer artifacts:", len(restored),
              "no approval")
    else:
        queue = json.loads(Path(a.queue).read_text(encoding="utf-8"))
        root = Path(a.vault_dir)
        folders = sorted(p.parent for p in root.glob("*/manifest.json"))
        report = match_before_whole_day_start(queue, folders)
        output = {
            "schema": "kb21-earliest-kickoff-early-official-crosscheck-v1",
            "days": queue["days"], "calendar_gate": "BLOCKED",
            "publication": "DIAGNOSTIC / NO PLAY",
            "matches": [
                {"day": day, "fixture_id": fixture_id, **info}
                for (day, fixture_id), info in sorted(report.items())
            ],
            "summary": {
                "matched_pregame_captured": sum(
                    row["status"] == "EARLY_SNAPSHOT_MATCHED_FOR_REVIEW"
                    for row in report.values()),
                "unresolved": sum(
                    row["status"] != "EARLY_SNAPSHOT_MATCHED_FOR_REVIEW"
                    for row in report.values()),
            },
        }
        target = Path(a.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")
        print("Early official archive candidate checks:", output["summary"],
              "NO PLAY")


if __name__ == "__main__":
    main()
