"""Opt-in observer of the existing experimental producer; never an API client.

Run only from a separately pinned checkout. Original return values, exceptions,
stdout, publication IDs and archives are owned by the native producer.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile

from .capture import capture_provider_response, read_provider_capture
from .full_pool import build_full_pool, capture_full_pool, write_full_pool
from .source_manifest import instant, local_day

STAGES = {
    "prefetch": "api_national_today_prefetch", "scan": "api_market_scan",
    "enrich": "api_market_v3_enrich", "publish": "api_market_report_diversify",
    "playable": "api_market_playable_shadow", "freeze": "api_market_freeze",
    "pdf": "api_market_to_pdf", "settle": "api_market_settle",
    "status": None,
}
SCHEMA = "multimodel-v2-producer-stage-v1"
REPO = Path(__file__).resolve().parents[1]


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def immutable_json(root, relative, value):
    return immutable_bytes(root, relative, encode(value))


def immutable_bytes(root, relative, content):
    root = Path(root).resolve()
    target = root / relative
    if not target.resolve().is_relative_to(root):
        raise ValueError("recorder_path_escape")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix=".recorder-")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target)
    finally:
        os.unlink(temporary)
    return target


def checkout_sha(root):
    root = Path(root).resolve()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL).decode().strip()
    if Path(git("rev-parse", "--show-toplevel")).resolve() != root:
        raise ValueError("native_checkout_root_required")
    # Data produced by the native program may be untracked; source edits may not.
    if git("status", "--porcelain", "--untracked-files=no", "--", "tools", "config"):
        raise ValueError("native_source_has_uncommitted_changes")
    return git("rev-parse", "HEAD")


@contextmanager
def native_environment(root, day):
    """Isolate native module aliases and relative paths, including top-level freeze."""
    root = Path(root).resolve()
    previous = {k: v for k, v in sys.modules.items() if k.startswith(("api_market_", "api_national_", "pitchapi_"))}
    old_path, old_argv, old_cwd = sys.path[:], sys.argv[:], Path.cwd()
    try:
        for name in previous:
            del sys.modules[name]
        sys.path.insert(0, str(root / "tools"))
        sys.argv[:] = ["native-producer", local_day(day).isoformat()]
        os.chdir(root)
        yield
    finally:
        for name in list(sys.modules):
            if name.startswith(("api_market_", "api_national_", "pitchapi_")):
                del sys.modules[name]
        sys.modules.update(previous)
        sys.path[:] = old_path
        sys.argv[:] = old_argv
        os.chdir(old_cwd)


class NativeProducerRecorder:
    def __init__(self, native_root, output_root, source, *, recorder_sha, enabled=False, clock=None):
        self.native_root = Path(native_root).resolve()
        self.root = Path(output_root).resolve()
        for checkout in (REPO, self.native_root):
            if self.root == checkout or checkout in self.root.parents:
                raise ValueError("recorder_requires_output_outside_checkouts")
        self.source = deepcopy(source)
        for key in ("workflow_head_sha", "code_checkout_sha"):
            if not re.fullmatch(r"[0-9a-f]{40}", str(source.get(key))):
                raise ValueError("producer_source_sha_required")
        if not re.fullmatch(r"[1-9][0-9]{0,19}", str(source.get("run_id"))):
            raise ValueError("producer_run_id_required")
        if not re.fullmatch(r"[0-9a-f]{40}", str(recorder_sha)):
            raise ValueError("recorder_sha_required")
        self.recorder_sha, self.enabled = recorder_sha, enabled
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.errors, self.receipts, self.pools = [], [], []
        self.outputs = []
        self.output_digests = {}
        self.api_calls = 0

    def stamp(self):
        return self.clock().isoformat()

    def failure(self, exc):
        # Exception diagnostics must never copy credentials or provider bodies.
        code = str(exc) if isinstance(exc, ValueError) and re.fullmatch(r"[a-z0-9_]+", str(exc)) else type(exc).__name__
        self.errors.append(code)

    def _raw(self, endpoint, requested, received, result):
        path = capture_provider_response(result[0], provider="API-Football", endpoint=endpoint,
            requested_at=requested, received_at=received, source=self.source,
            output_root=self.root, clock=self.clock)
        self.receipts.append(str(path.relative_to(self.root)))

    def _pool(self, native):
        day, pub = native["date"], native["publication"]["id"]
        frozen = self.native_root / "data/api_football/predictions" / day / (pub + ".json")
        raw = frozen.read_bytes()
        if json.loads(raw) != native:
            raise ValueError("native_publication_file_mismatch")
        stamp = self.stamp()
        refs = []
        # Earlier stages are separate processes. Read their immutable receipts,
        # but bind only this run/revision and observations before publication.
        for path in sorted((self.root / "raw").glob("*/*.json")):
            receipt = read_provider_capture(path, as_of=stamp)
            if receipt["source"] != {k: self.source[k] for k in receipt["source"]}:
                raise ValueError("raw_receipt_source_mismatch")
            if instant(receipt["received_at"]) <= instant(native["publication"]["captured_at_utc"]):
                refs.append({"envelope_sha256": receipt["integrity"]["sha256"],
                    "response_sha256": receipt["integrity"]["response_sha256"],
                    "received_at": receipt["received_at"], "endpoint": receipt["endpoint"],
                    "provider": receipt["provider"]})
        playable = importlib.import_module("api_market_playable_shadow")
        config = json.loads(playable.CONFIG.read_text())
        captured = {"payload": native, "locator": str(frozen), "capture_sha256": hashlib.sha256(raw).hexdigest()}
        source = dict(self.source, raw_quote_receipts=refs)
        try:
            envelope = capture_full_pool(captured, source, recorded_at=stamp,
                evaluator=playable.evaluate, decision_config=config, clock=self.clock)
        except ValueError as exc:
            # Preserve actual late/partial originals too, without manufacturing
            # a fresh decision trace or promoting them to prematch evidence.
            self.failure(exc)
            envelope = build_full_pool(captured, source, recorded_at=stamp, mode="copy_original")
        path = write_full_pool(envelope, self.root / "full_pool")
        self.pools.append(str(path.relative_to(self.root)))

    def _outcomes(self, day):
        """Observe the native settlement already written by its original job."""
        from .outcome_bridge import build_linked_native_outcomes
        native_settle = importlib.import_module("api_market_settle")
        scan = importlib.import_module("api_market_scan")
        calibration = self.native_root / f"data/api_football/calibration/{day}.json"
        content = calibration.read_bytes()
        observations = json.loads(content).get("observations", [])
        receipts = [read_provider_capture(path, as_of=self.stamp())
                    for path in sorted((self.root / "raw").glob("*/*.json"))]
        ids = sorted({str(o.get("prediction_id")) for o in observations})
        for native_id in ids:
            if not re.fullmatch(r"[0-9]+-[0-9a-f]+", native_id):
                raise ValueError("original_settlement_native_id_invalid")
            original_path = self.native_root / f"data/api_football/predictions/{day}/{native_id}.json"
            native_content = original_path.read_bytes()
            snapshot = json.loads(native_content)
            if snapshot.get("publication", {}).get("id") != native_id:
                raise ValueError("original_settlement_native_id_mismatch")
            result = build_linked_native_outcomes(snapshot,
                [o for o in observations if o.get("prediction_id") == native_id], receipts,
                as_of=self.stamp(), actual_metric=native_settle.actual_metric, outcome_hit=scan.outcome_hit)
            result.update(schema="multimodel-v2-linked-outcomes-v1", date=day, native_publication_id=native_id,
                original_calibration_sha256=hashlib.sha256(content).hexdigest(),
                original_publication_sha256=hashlib.sha256(native_content).hexdigest())
            relative = f"outcomes/{day}/{native_id}.json"
            immutable_json(self.root, relative, result)
            self.outputs.append(relative)
            self.output_digests[relative] = digest(result)
            if result["rejections"]:
                self.errors.append("native_settlement_linkage_incomplete")

    @contextmanager
    def observe(self):
        if not self.enabled:
            yield self
            return
        scan = importlib.import_module("api_market_scan")
        storage = importlib.import_module("api_market_storage")
        original_api, original_publish = scan.api_get, storage.archive_publication

        def api(endpoint, **params):
            requested = self.stamp()
            self.api_calls += 1
            result = original_api(endpoint, **params)  # exactly one original call
            received = self.stamp()
            try:
                self._raw(endpoint, requested, received, result)
            except Exception as exc:
                self.failure(exc)
            return result  # retain tuple/body/header identity

        def publish(*args, **kwargs):
            native = original_publish(*args, **kwargs)
            try:
                self._pool(native)
            except Exception as exc:
                self.failure(exc)
            return native

        # Cover aliases imported before observer installation as well.
        patches = []
        for module in list(sys.modules.values()):
            if module is None or not getattr(module, "__name__", "").startswith(("api_market_", "api_national_")):
                continue
            for name, value in list(vars(module).items()):
                replacement = api if value is original_api else publish if value is original_publish else None
                if replacement is not None:
                    patches.append((module, name, value))
                    setattr(module, name, replacement)
        try:
            yield self
        finally:
            for module, name, original in patches:
                setattr(module, name, original)
            # Modules loaded inside the scope may have imported patched aliases.
            for module in list(sys.modules.values()):
                if module is None or not getattr(module, "__name__", "").startswith(("api_market_", "api_national_")):
                    continue
                for name, value in list(vars(module).items()):
                    if value is api:
                        setattr(module, name, original_api)
                    elif value is publish:
                        setattr(module, name, original_publish)

    def run_stage(self, stage, day):
        if stage not in STAGES:
            raise ValueError("unsupported_native_stage")
        self.errors, self.receipts, self.pools, self.outputs = [], [], [], []
        self.output_digests, self.api_calls = {}, 0
        day = local_day(day).isoformat()
        start, native_ok = self.stamp(), False
        try:
            with self.observe():
                if stage == "status":
                    path = self.native_root / f"reports/api_market_scan/multiday_status/{day}.json"
                    value = json.loads(path.read_bytes())
                    if value.get("date") != day or value.get("status") not in ("ok", "error"):
                        raise ValueError("native_day_status_invalid")
                    if self.enabled:
                        relative = f"multiday_status/{day}.json"
                        immutable_json(self.root, relative, value)
                        self.outputs.append(relative)
                        self.output_digests[relative] = digest(value)
                        if value["status"] != "ok":
                            self.errors.append("native_day_failed")
                elif stage in ("freeze", "pdf"):
                    runpy.run_path(str(self.native_root / "tools" / (STAGES[stage] + ".py")), run_name="__main__")
                else:
                    importlib.import_module(STAGES[stage]).main()
                native_ok = True
                if self.enabled:
                    if stage == "settle":
                        try:
                            self._outcomes(day)
                        except Exception as exc:
                            self.failure(exc)
                    paths = {
                        "scan": f"data/api_football/market_work/{day}.json",
                        "enrich": f"data/api_football/market_work/{day}.json",
                        "publish": f"data/api_football/market_scan/{day}.json",
                        "playable": f"reports/api_market_scan/v2/API_MARKET_SCAN_PLAYABLE_{day}.json",
                        "freeze": f"reports/api_market_scan/audit_input/{day}.json",
                        "pdf": f"reports/api_market_scan/pdf/API_MARKET_SCAN_{day}.pdf",
                    }
                    if stage in paths:
                        try:
                            original = self.native_root / paths[stage]
                            content = original.read_bytes()
                            # JSON evidence receives the same secret redaction as
                            # receipts. PDF bytes are original native output.
                            if original.suffix == ".json":
                                from .capture import _redact
                                content = encode(_redact(json.loads(content)))
                            relative = f"native/{day}/{stage}/" + original.name
                            immutable_bytes(self.root, relative, content)
                            self.outputs.append(relative)
                            self.output_digests[relative] = hashlib.sha256(content).hexdigest()
                        except Exception as exc:
                            self.failure(exc)
        finally:
            if self.enabled:
                summary = {"schema": SCHEMA, "date": day, "stage": stage,
                    "started_at": start, "completed_at": self.stamp(), "native_ok": native_ok,
                    "status": "CAPTURED" if native_ok and not self.errors else "SOURCE_BLOCKED",
                    "source": self.source, "recorder_sha": self.recorder_sha,
                    "api_calls": self.api_calls, "raw_receipts": self.receipts,
                    "full_pool": self.pools, "outputs": self.outputs, "output_sha256": self.output_digests,
                    "errors": self.errors, "n_effect": 0}
                summary["sha256"] = digest(summary)
                try:
                    immutable_json(self.root, f"producer/{day}/{stage}.json", summary)
                except Exception as exc:
                    # Native exit semantics remain intact; the upload gate will
                    # reject the missing/old stage receipt.
                    print("SOURCE_BLOCKED recorder_summary_" + type(exc).__name__, file=sys.stderr)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=STAGES)
    parser.add_argument("date")
    parser.add_argument("--native-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--native-sha", required=True)
    parser.add_argument("--recorder-sha", required=True)
    parser.add_argument("--enabled", action="store_true")
    args = parser.parse_args(argv)
    if checkout_sha(args.native_root) != args.native_sha or checkout_sha(REPO) != args.recorder_sha:
        parser.error("pinned_checkout_sha_mismatch")
    source = {"run_id": os.environ.get("GITHUB_RUN_ID"), "workflow_head_sha": os.environ.get("GITHUB_SHA"),
        "code_checkout_sha": args.native_sha, "workflow_path": ".github/workflows/api-market-multiday-experiment.yml"}
    recorder = NativeProducerRecorder(args.native_root, args.output_root, source,
        recorder_sha=args.recorder_sha, enabled=args.enabled)
    with native_environment(args.native_root, args.date):
        recorder.run_stage(args.stage, args.date)


if __name__ == "__main__":
    main()
