from __future__ import annotations

import json
import urllib.request

HEADERS = {"User-Agent": "CANN-Analyze/0.1", "Accept": "application/json"}
REPOS = [
    "Ascend/msprof-analyze",
    "Ascend/mspti",
    "Ascend/mstx",
    "Ascend/msserviceprofiler",
    "Ascend/msmonitor",
    "Ascend/msinsight",
    "Ascend/msopprof",
    "Ascend/msprobe",
    "Ascend/msmemscope",
    "Ascend/msit",
    "cann/oam-tools",
    "cann/asc-tools",
]


def get(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    for full in REPOS:
        print(f"==== {full}")
        try:
            tree = get(f"https://gitcode.com/api/v5/repos/{full}/contents")
            if not isinstance(tree, list):
                print(tree)
            else:
                print(", ".join(x.get("name", "?") for x in tree))
        except Exception as exc:
            print("FAIL", exc)
        print()


if __name__ == "__main__":
    main()
