from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from cann_analyze import __version__
from cann_analyze.catalog import refresh_community, repos
from cann_analyze.collect import collect
from cann_analyze.evidence import build_evidence
from cann_analyze.index_cmd import bootstrap, index_all, index_repo, status
from cann_analyze.locate import locate_one, locate_path
from cann_analyze.parsers import parse_file, parse_line
from cann_analyze.paths import project_root, skills_dir


def _dump(data: Any, output: Path | None) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if output:
        output.write_text(text, encoding="utf-8")
        print(str(output))
    else:
        print(text)


def cmd_status(_: argparse.Namespace) -> int:
    _dump(status(), None)
    return 0


def cmd_catalog(args: argparse.Namespace) -> int:
    if args.refresh:
        _dump(refresh_community(), None)
        return 0
    items = []
    for repo_id, repo in repos().items():
        items.append(
            {
                "id": repo_id,
                "url": repo.get("url"),
                "layer": repo.get("layer"),
                "role": repo.get("role"),
                "local_path": repo.get("local_path"),
                "msprof_roles": repo.get("msprof_roles"),
            }
        )
    if args.layer:
        items = [i for i in items if i.get("layer") == args.layer]
    _dump(items, None)
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    if args.bootstrap:
        ids = [args.repo] if args.repo else None
        _dump(bootstrap(ids), args.output)
        return 0
    if args.all:
        _dump(index_all(only_local=True), args.output)
        return 0
    if not args.repo:
        print("index requires --repo ID, --all, or --bootstrap", file=sys.stderr)
        return 2
    source = Path(args.source) if args.source else None
    _dump(index_repo(args.repo, source=source, commit=args.commit), args.output)
    return 0


def cmd_parse(args: argparse.Namespace) -> int:
    if args.line:
        _dump(parse_line(args.line), args.output)
        return 0
    path = Path(args.path)
    _dump(parse_file(path), args.output)
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    _dump(collect(Path(args.path)), args.output)
    return 0


def cmd_locate(args: argparse.Namespace) -> int:
    if args.line:
        _dump(locate_one(args.line), args.output)
        return 0
    _dump(locate_path(Path(args.path), limit=args.limit), args.output)
    return 0


def cmd_evidence(args: argparse.Namespace) -> int:
    pack = build_evidence(Path(args.path), max_records=args.max_records, locate_limit=args.limit)
    _dump(pack, args.output)
    return 0


def cmd_skills_install(args: argparse.Namespace) -> int:
    src = skills_dir()
    mapping = {
        "grok": Path.home() / ".grok" / "skills",
        "claude": Path.home() / ".claude" / "skills",
        "codex": Path.home() / ".codex" / "skills",
        "agents": Path.home() / ".agents" / "skills",
        "project-grok": project_root() / ".grok" / "skills",
    }
    targets = list(mapping) if args.target == "all" else [args.target]
    copied = []
    for name in targets:
        dest_root = mapping[name]
        dest_root.mkdir(parents=True, exist_ok=True)
        for skill in src.iterdir():
            if not (skill / "SKILL.md").is_file():
                continue
            dest = dest_root / skill.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(skill, dest)
            copied.append(str(dest))
    _dump({"copied": copied}, None)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cann-analyze",
        description="Collect CANN/Ascend logs and locate code sites from a versioned log-site index. "
        "This tool does not diagnose root cause.",
    )
    parser.add_argument("--version", action="version", version=f"cann-analyze {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("status", help="show indexed snapshots and local clones")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("catalog", help="list known repos")
    p.add_argument("--layer", help="filter by layer: runtime, toolchain, ops, ...")
    p.add_argument("--refresh", action="store_true", help="refresh catalogs/community_repos.json from GitCode public API")
    p.set_defaults(func=cmd_catalog)

    p = sub.add_parser("index", help="scan a local clone into the log-site index; never runs during locate")
    p.add_argument("--repo", help="catalog repo id, e.g. cann/runtime")
    p.add_argument("--source", help="override local clone path")
    p.add_argument("--commit", help="store this commit label")
    p.add_argument("--all", action="store_true", help="index every catalog repo with a path in repos.local.json")
    p.add_argument(
        "--bootstrap",
        action="store_true",
        help="shallow-clone missing catalog repos into data/mirrors and index them; locate still never clones",
    )
    p.add_argument("-o", "--output", type=Path)
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("collect", help="inventory log files under a path; does not copy binaries")
    p.add_argument("path")
    p.add_argument("-o", "--output", type=Path)
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("parse", help="parse log lines to JSON")
    p.add_argument("path", nargs="?", help="log file")
    p.add_argument("--line", help="single log line")
    p.add_argument("-o", "--output", type=Path)
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("locate", help="map log lines to indexed code sites")
    p.add_argument("path", nargs="?", help="log file")
    p.add_argument("--line", help="single log line")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("-o", "--output", type=Path)
    p.set_defaults(func=cmd_locate)

    p = sub.add_parser("evidence", help="collect + parse + locate into an evidence pack")
    p.add_argument("path")
    p.add_argument("--max-records", type=int, default=400)
    p.add_argument("--limit", type=int, default=3)
    p.add_argument("-o", "--output", type=Path)
    p.set_defaults(func=cmd_evidence)

    p = sub.add_parser("skills-install", help="copy skills/ into an agent skills directory")
    p.add_argument(
        "--target",
        choices=["grok", "claude", "codex", "agents", "project-grok", "all"],
        default="project-grok",
    )
    p.set_defaults(func=cmd_skills_install)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except FileNotFoundError as exc:
        print(json.dumps({"error": "not_found", "detail": str(exc)}), file=sys.stderr)
        return 2
    except KeyError as exc:
        print(json.dumps({"error": "unknown_repo", "detail": str(exc)}), file=sys.stderr)
        return 2
