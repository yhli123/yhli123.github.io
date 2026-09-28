#!/usr/bin/env python3
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

TIMEOUT = 20

PAPERS = [
    {
        "name": "Immiscible Diffusion",
        "arxiv": "2406.12303",
        "project": "https://yihengli.com/immiscible-diffusion/",
        "official": "https://proceedings.neurips.cc/paper_files/paper/2024/hash/a422a2f016c14406a01ddba731c0969a-Abstract-Conference.html",
        "dblp": "https://dblp.org/rec/conf/nips/LiJKTKX24",
    },
    {
        "name": "Improved Immiscible Diffusion",
        "arxiv": "2505.18521",
        "project": "https://yihengli.com/improved-immiscible-diffusion/",
        "official": "https://eccv.ecva.net/Conferences/2026/AcceptedPapers",
        "dblp": "https://dblp.org/rec/journals/corr/abs-2505-18521",
    },
]

def fetch(url, accept="application/json,text/html;q=0.9,*/*;q=0.8"):
    req = urllib.request.Request(url, headers={
        "User-Agent": "immiscible-agent-visibility-check/1.0 (+https://yihengli.com/)",
        "Accept": accept,
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read(300000).decode("utf-8", "replace")
            return {"ok": 200 <= r.status < 400, "status": r.status, "url": r.geturl(), "body": body}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "url": url, "body": ""}
    except Exception as e:
        return {"ok": False, "status": None, "url": url, "error": str(e), "body": ""}

def check_paper(p):
    arxiv = fetch("https://export.arxiv.org/api/query?id_list=" + p["arxiv"], "application/atom+xml")
    semantic = fetch("https://api.semanticscholar.org/graph/v1/paper/ARXIV:" + p["arxiv"] + "?fields=paperId,title,year,url")
    openalex = fetch("https://api.openalex.org/works/https://doi.org/10.48550/arXiv." + p["arxiv"])
    hf = fetch("https://huggingface.co/papers/" + p["arxiv"])
    project = fetch(p["project"])
    official = fetch(p["official"])
    dblp = fetch(p["dblp"])
    project_text = project.get("body","").lower()

    checks = {
        "project_page": project["ok"],
        "project_has_citation_title": "citation_title" in project_text,
        "project_has_jsonld": "application/ld+json" in project_text,
        "arxiv": arxiv["ok"] and p["arxiv"] in arxiv.get("body",""),
        "semantic_scholar": None if semantic.get("status") == 429 else semantic["ok"],
        "openalex": openalex["ok"],
        "hugging_face_papers": hf["ok"],
        "dblp": dblp["ok"],
        "official_venue": official["ok"],
    }
    return {
        "paper": p["name"],
        "arxiv_id": p["arxiv"],
        "checks": checks,
        "all_core_ok": all(value is True for value in checks.values()),
        "has_failures": any(value is False for value in checks.values()),
        "inconclusive_checks": [key for key, value in checks.items() if value is None],
        "statuses": {
            "project": project.get("status"),
            "arxiv": arxiv.get("status"),
            "semantic_scholar": semantic.get("status"),
            "openalex": openalex.get("status"),
            "hugging_face": hf.get("status"),
            "dblp": dblp.get("status"),
            "official": official.get("status"),
        }
    }

def main():
    results = [check_paper(p) for p in PAPERS]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Google Scholar is intentionally not scraped. Its automated-query behavior is not suitable for this lightweight health check.",
        "papers": results,
    }
    with open("agent-visibility-report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.write("\n")

    for r in results:
        print("\n" + r["paper"])
        for key, ok in r["checks"].items():
            if ok is None:
                print("::warning::" + r["paper"] + ": " + key +
                      " inconclusive (HTTP 429 rate limit); this does not establish absence from the index.")
            else:
                print(("OK   " if ok else "FAIL ") + key)

    if any(r["has_failures"] for r in results):
        sys.exit(1)

if __name__ == "__main__":
    main()
