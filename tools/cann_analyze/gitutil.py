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


def candidates(url: str) -> list[str]:
    """Clone URLs to try, in order.

    The catalog stores https URLs, but a field machine may only have SSH keys (or only
    https). Try the URL as given first, then the other scheme. This never guesses a
    third form.
    """
    url = (url or "").strip()
    if not url:
        return []
    out = [url]
    other = ssh_url(url)
    if other and other != url:
        out.append(other)
    elif url.startswith("git@"):
        path = url.removeprefix("git@gitcode.com:").removesuffix(".git")
        if path and path != url:
            out.append(f"https://gitcode.com/{path}.git")
    return out


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
    """Shallow clone (or refresh) `url` into `dest`.

    Returns `ok` plus the `url` and `remote` actually used, so a failure can be
    reported with the form that was attempted instead of a bare exit code.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    urls = candidates(url)
    if not urls:
        return {"action": "none", "path": str(dest), "ok": False, "detail": "empty url"}
    remote = urls[0]

    if (dest / ".git").is_dir():
        fetch = subprocess.run(
            ["git", "-C", str(dest), "fetch", "--depth", str(depth), "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
        if fetch.returncode == 0:
            subprocess.run(
                ["git", "-C", str(dest), "reset", "--hard", "FETCH_HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
        return {
            "action": "update",
            "path": str(dest),
            "url": url,
            "remote": remote,
            "ok": fetch.returncode == 0,
            "detail": (fetch.stderr or fetch.stdout)[-400:],
        }

    attempts: list[str] = []
    for candidate in urls:
        result = subprocess.run(
            ["git", "clone", "--depth", str(depth), "--single-branch", candidate, str(dest)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return {
                "action": "clone",
                "path": str(dest),
                "url": url,
                "remote": candidate,
                "ok": True,
                "detail": "",
            }
        attempts.append(f"{candidate}: {(result.stderr or result.stdout).strip()[-200:]}")
    return {
        "action": "clone",
        "path": str(dest),
        "url": url,
        "remote": remote,
        "ok": False,
        "detail": " | ".join(attempts)[-400:],
    }


def head_commit(source: Path) -> str:
    return _run(source, "rev-parse", "HEAD")


def head_ref(source: Path) -> str:
    return _run(source, "rev-parse", "--abbrev-ref", "HEAD")


def changed_files(source: Path, old: str, new: str) -> list[str]:
    out = _run(source, "diff", "--name-only", old, new)
    return [line.replace("\\", "/") for line in out.splitlines() if line]
