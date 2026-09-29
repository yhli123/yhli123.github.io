#!/usr/bin/env python3
"""Notify IndexNow after Pages deployment; receipt does not mean indexing."""
import json
import os
from pathlib import Path
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
HOST = "yihengli.com"
PAGES = {
    "immiscible-diffusion/index.html": "/immiscible-diffusion/",
    "improved-immiscible-diffusion/index.html": "/improved-immiscible-diffusion/",
    "agents/diffusion-training/index.html": "/agents/diffusion-training/",
}


def changed_pages(changed, key):
    if key + ".txt" in changed:
        return list(PAGES)
    return [p for p in PAGES if p in changed]


def previous_deployment(run):
    # Compare deployments, not just the last commit: a push may contain many commits.
    repo = os.environ["GITHUB_REPOSITORY"]
    url = (f"https://api.github.com/repos/{repo}/actions/workflows/"
           f"{run['workflow_id']}/runs?branch=main&status=success&per_page=100")
    request = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + os.environ["GH_TOKEN"],
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        runs = json.load(response)["workflow_runs"]
    older = [r for r in runs if r["run_number"] < run["run_number"]]
    if not older:
        raise RuntimeError("No previous deployment found; use the manual workflow to initialize.")
    return max(older, key=lambda r: r["run_number"])["head_sha"]


def main():
    key = (ROOT / "scripts/indexnow-key.txt").read_text().strip()
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    if os.environ["GITHUB_EVENT_NAME"] == "workflow_dispatch":
        selected = list(PAGES)
    else:
        run = event["workflow_run"]
        if run["conclusion"] != "success" or run["head_branch"] != "main":
            return
        base = previous_deployment(run)
        changed = subprocess.check_output(
            ["git", "diff", "--name-only", base, run["head_sha"]],
            cwd=ROOT, text=True).splitlines()
        selected = changed_pages(changed, key)
    if not selected:
        print("No research page changes; no notification sent.")
        return
    # Ensure the key and exact static HTML have reached the public host.
    # Abort on stale deployment rather than notify about content not yet live.
    for path, suffix in [(key + ".txt", "/" + key + ".txt")] + [(p, PAGES[p]) for p in selected]:
        with urllib.request.urlopen("https://" + HOST + suffix, timeout=30) as response:
            live = response.read()
        if live != (ROOT / path).read_bytes():
            raise RuntimeError("Live content differs from deployment: " + suffix + "; retry manually after deployment settles.")
    payload = {"host": HOST, "key": key,
               "keyLocation": f"https://{HOST}/{key}.txt",
               "urlList": ["https://" + HOST + PAGES[p] for p in selected]}
    request = urllib.request.Request("https://api.indexnow.org/indexnow",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status not in (200, 202):
            raise RuntimeError(f"Unexpected IndexNow status: {response.status}")
        print(f"IndexNow HTTP {response.status}: {len(selected)} URLs received; indexing is not guaranteed.")
        if response.status == 202:
            print("Ownership validation is pending.")


if __name__ == "__main__":
    main()
