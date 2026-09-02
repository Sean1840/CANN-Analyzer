from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "catalogs" / "community_repos.json"
API = "https://gitcode.com/api/v5/orgs/{org}/repos?page={page}&per_page=100&type=all"


def list_org(org: str) -> list[dict]:
    repos: list[dict] = []
    page = 1
    while True:
        url = API.format(org=org, page=page)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "CANN-Analyze/0.1", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not isinstance(data, list) or not data:
            break
        repos.extend(data)
        if len(data) < 100:
            break
        page += 1
        time.sleep(0.15)
    return repos


def slim(org: str, raw: dict) -> dict:
    ns = (raw.get("namespace") or {}).get("path") or org
    name = raw.get("path") or raw.get("name")
    return {
        "id": f"{ns}/{name}",
        "name": name,
        "org": ns,
        "url": raw.get("html_url"),
        "git_url": f"https://gitcode.com/{ns}/{name}.git",
        "description": raw.get("description") or "",
        "language": raw.get("language"),
        "default_branch": raw.get("default_branch") or "master",
        "stars": raw.get("stargazers_count") or 0,
        "forks": raw.get("forks_count") or 0,
        "private": bool(raw.get("private")),
        "pushed_at": raw.get("pushed_at"),
    }


def main() -> None:
    out = {"schema": "cann-analyze.community-repos.v1", "orgs": {}}
    for org in ("cann", "Ascend"):
        items = [slim(org, r) for r in list_org(org)]
        items.sort(key=lambda x: x["id"].lower())
        out["orgs"][org] = {"count": len(items), "repos": items}
        print(f"{org}: {len(items)} repos", flush=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
