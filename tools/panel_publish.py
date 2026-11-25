"""MM-05 operator-side conditional private publication. No provider API calls.

Only run on a trusted machine or private CI, never upload the bundle as a
public GitHub artifact. No credentials in command arguments or output.
"""
import argparse
import os
import re
import tempfile
from pathlib import Path
from github_models.panel_export import verify, MAX_BYTES, stamp

KEY = "multimodel/latest.zip"

def compare(current, previous):
    for field in ("forecast_cutoff_utc", "audit_as_of_utc"):
        if stamp(current[field]) < stamp(previous[field]):
            raise ValueError("older_snapshot:" + field)
    if all(stamp(current[f]) == stamp(previous[f]) for f in ("forecast_cutoff_utc", "audit_as_of_utc")):
        if current["files"] != previous["files"]:
            raise ValueError("same_cutoff_conflicting_payload")
        return False
    return True

def check(path):
    if Path(path).stat().st_size > MAX_BYTES:
        raise ValueError("compressed_bundle_too_large")
    manifest = verify(path)
    if manifest.get("publication") != "local_only" or manifest.get("historical_snapshot") is not True:
        raise ValueError("unsupported_manifest")
    for role in ("abc", "odds", "audit"):
        if type(manifest["sources"][role]["run_id"]) is not int or manifest["sources"][role]["run_id"] <= 0:
            raise ValueError("invalid_source_run_id")
    return manifest

def publish(client, bucket, path):
    manifest = check(path)
    condition = {"IfNoneMatch": "*"}
    try:
        old = client.get_object(Bucket=bucket, Key=KEY)
    except Exception as e:
        code = getattr(e, "response", {}).get("Error", {}).get("Code")
        if code not in ("NoSuchKey", "404", "NotFound"):
            raise
    else:
        stream = old["Body"]
        try:
            if not 0 < old["ContentLength"] <= MAX_BYTES:
                raise ValueError("invalid_previous_bundle_size")
            with tempfile.TemporaryDirectory() as d:
                previous_path = Path(d) / "previous.zip"
                with previous_path.open("wb") as f:
                    total = 0
                    for chunk in iter(lambda: stream.read(1024*1024), b""):
                        total += len(chunk)
                        if total > old["ContentLength"] or total > MAX_BYTES:
                            raise ValueError("oversize_previous_bundle")
                        f.write(chunk)
                    if total != old["ContentLength"]:
                        raise ValueError("truncated_previous_bundle")
                previous = check(previous_path)
            if not compare(manifest, previous):
                return "unchanged"
            condition = {"IfMatch": old["ETag"]}
        finally:
            stream.close()
    with Path(path).open("rb") as f:
        client.put_object(Bucket=bucket, Key=KEY, Body=f, ContentType="application/zip",
                          CacheControl="private, no-store, max-age=0", **condition)
    return "published"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("bundle", type=Path)
    p.add_argument("--publish-private", action="store_true", help="Explicitly write to configured private R2 bucket")
    a=p.parse_args()
    manifest=check(a.bundle)
    print("Validated forecast cutoff:",manifest["forecast_cutoff_utc"],"audit:",manifest["audit_as_of_utc"])
    if not a.publish_private:
        print("Dry run; no network or upload.")
        return
    import boto3
    account=os.environ["MM_R2_ACCOUNT_ID"]
    bucket=os.environ["MM_R2_BUCKET"]
    if not re.fullmatch(r"[a-fA-F0-9]{32}",account) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]",bucket):
        raise ValueError("invalid_private_storage_config")
    s3=boto3.client("s3",endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
                    region_name="auto",aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
                    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"])
    # Account operator must ensure bucket has no public URLs or bindings.
    print(publish(s3,bucket,a.bundle))

if __name__=="__main__":
    main()
