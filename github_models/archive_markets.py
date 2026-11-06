"""Append-only archive of frozen market probabilities."""
import base64
import json
import os
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

def main():
    day = datetime.now(ZoneInfo("Europe/Warsaw")).date().isoformat()
    run_id = os.environ["GITHUB_RUN_ID"]
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GH_TOKEN"]
    source = Path("reports/github_models/markets") / (day + ".json")
    content = base64.b64encode(source.read_bytes()).decode("ascii")
    destination = f"markets/{day}/{run_id}.json"
    endpoint = f"https://api.github.com/repos/{repo}/contents/{destination}"
    payload = json.dumps({"message":f"archive: frozen event markets {day} {run_id}",
                          "content":content,"branch":"research/github-models-frozen"}).encode()
    req = Request(endpoint,data=payload,method="PUT",headers={
        "Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
        "Content-Type":"application/json"})
    with urlopen(req,timeout=30) as response:
        print("Archived market predictions:",destination,"HTTP",response.status)

if __name__ == "__main__":
    main()
