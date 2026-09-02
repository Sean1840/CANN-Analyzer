from __future__ import annotations

import json
import urllib.request

HEADERS = {"User-Agent": "CANN-Analyze/0.1", "Accept": "application/json"}
REPOS = [
    ("Ascend", "msprof-analyze"),
    ("Ascend", "mspti"),
    ("Ascend", "mstx"),
    ("Ascend", "msserviceprofiler"),
    ("Ascend", "msmonitor"),
    ("Ascend", "msinsight"),
    ("Ascend", "msopprof"),
    ("Ascend", "msprobe"),
    ("Ascend", "msmemscope"),
    ("Ascend", "msit"),
    ("cann", "oam-tools"),
    ("cann", "asc-tools"),
    ("cann", "docs"),
]


def get(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    for owner, name in REPOS:
        print(f"==== {owner}/{name}")
        try:
            info = get(f"https://gitcode.com/api/v5/repos/{owner}/{name}")
            desc = (info.get("description") or "").replace("\n", " ")[:180]
            print(
                f"lang={info.get('language')} stars={info.get('stargazers_count')} "
                f"branch={info.get('default_branch')}"
            )
            print(desc)
            tree = get(f"https://gitcode.com/api/v5/repos/{owner}/{name}/contents/")
            names = [x.get("name") for x in tree] if isinstance(tree, list) else [str(tree)[:200]]
            print("root:", ", ".join(str(n) for n in names[:30]))
        except Exception as exc:
            print("FAIL", exc)
        print()


if __name__ == "__main__":
    main()
