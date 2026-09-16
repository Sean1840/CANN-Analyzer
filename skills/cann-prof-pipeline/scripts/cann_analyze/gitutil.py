from __future__ import annotations

import subprocess
from pathlib import Path


def ssh_url(https_or_ssh: str) -> str:
    url = https_or_ssh.strip()
    if url.startswith("git@"):
        return url
    url = url.removeprefix("https://").removeprefix("http://")
    if url.startswith("gitcode.com/"):
        path = url.removeprefix("gitcode.com/").removesuffix(".git")
        return f"git@gitcode.com:{path}.git"
    return https_or_ssh


def _run(source: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(source), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def clone_or_update(url: str, dest: Path, depth: int = 1) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    remote = ssh_url(url)
    if (dest / ".git").is_dir():
        fetch = subprocess.run(
            ["git", "-C", str(dest), "fetch", "--depth", str(depth), "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
        subprocess.run(
            ["git", "-C", str(dest), "reset", "--hard", "FETCH_HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return {
            "action": "update",
            "path": str(dest),
            "ok": fetch.returncode == 0,
            "detail": (fetch.stderr or fetch.stdout)[-400:],
        }
    cmd = ["git", "clone", "--depth", str(depth), "--single-branch", remote, str(dest)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return {
        "action": "clone",
        "path": str(dest),
        "ok": result.returncode == 0,
        "detail": (result.stderr or result.stdout)[-400:],
    }


def head_commit(source: Path) -> str:
    return _run(source, "rev-parse", "HEAD")


def head_ref(source: Path) -> str:
    return _run(source, "rev-parse", "--abbrev-ref", "HEAD")


def changed_files(source: Path, old: str, new: str) -> list[str]:
    out = _run(source, "diff", "--name-only", old, new)
    return [line.replace("\\", "/") for line in out.splitlines() if line]
