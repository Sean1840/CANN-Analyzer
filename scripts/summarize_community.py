from __future__ import annotations

import json
from pathlib import Path

data = json.loads((Path(__file__).resolve().parents[1] / "catalogs" / "community_repos.json").read_text(encoding="utf-8"))
keys = (
    "prof", "log", "dump", "oam", "runtime", "driver", "ge", "hccl", "hixl",
    "hcomm", "msprof", "msinsight", "msop", "msprobe", "asys", "aicerr",
    "slog", "dlog", "trace", "debug", "parser", "collect", "monitor",
)


def dump(title: str, repos: list[dict]) -> None:
    print(f"=== {title} ({len(repos)}) ===")
    for r in repos:
        print(r["id"])


dump("cann", data["orgs"]["cann"]["repos"])
dump("Ascend", data["orgs"]["Ascend"]["repos"])
print("=== log/prof/runtime-ish ===")
for org in data["orgs"].values():
    for r in org["repos"]:
        blob = (r["id"] + " " + (r["description"] or "")).lower()
        if any(k in blob for k in keys):
            desc = (r["description"] or "").replace("\n", " ")[:120]
            print(f"{r['id']}\t{r['language'] or '-'}\t{r['stars']}\t{desc}")
