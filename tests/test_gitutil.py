"""Tests for clone/update URL handling.

The catalog stores https URLs for gitcode, but a field machine may only have SSH keys
set up (or the sandbox may block the bundled ssh client). A one-form clone fails with an
opaque exit code; the fallback keeps `index --bootstrap` usable and reports which remote
was actually tried.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cann_analyze import gitutil


class _Result:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_ssh_url_converts_gitcode_https():
    assert gitutil.ssh_url("https://gitcode.com/cann/runtime.git") == "git@gitcode.com:cann/runtime.git"
    assert gitutil.ssh_url("git@gitcode.com:cann/runtime.git") == "git@gitcode.com:cann/runtime.git"
    assert gitutil.ssh_url("https://example.com/x.git") == "https://example.com/x.git"


def test_candidates_tries_https_then_ssh():
    assert gitutil.candidates("https://gitcode.com/cann/runtime.git") == [
        "https://gitcode.com/cann/runtime.git",
        "git@gitcode.com:cann/runtime.git",
    ]


def test_candidates_tries_ssh_then_https():
    assert gitutil.candidates("git@gitcode.com:cann/runtime.git") == [
        "git@gitcode.com:cann/runtime.git",
        "https://gitcode.com/cann/runtime.git",
    ]


def test_candidates_is_empty_for_empty_url():
    assert gitutil.candidates("") == []
    assert gitutil.candidates("   ") == []


def test_clone_falls_back_to_second_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        if cmd[0] == "git" and "clone" in cmd:
            target = cmd[-2]
            if target.startswith("https://"):
                return _Result(1, stderr="fatal: could not read Username")
            return _Result(0)
        return _Result(0)

    monkeypatch.setattr(gitutil.subprocess, "run", fake_run)
    dest = tmp_path / "runtime"
    result = gitutil.clone_or_update("https://gitcode.com/cann/runtime.git", dest)

    assert result["ok"] is True
    assert result["remote"] == "git@gitcode.com:cann/runtime.git"
    assert result["url"] == "https://gitcode.com/cann/runtime.git"
    clone_cmds = [c for c in calls if "clone" in c]
    assert len(clone_cmds) == 2, "must try both forms before giving up"
    assert "could not read Username" in result.get("detail", "") or result["detail"] == ""


def test_clone_failure_reports_both_attempts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def fake_run(cmd, **kwargs):
        return _Result(1, stderr="fatal: repository not found")

    monkeypatch.setattr(gitutil.subprocess, "run", fake_run)
    result = gitutil.clone_or_update("https://gitcode.com/cann/nope.git", tmp_path / "nope")

    assert result["ok"] is False
    assert result["action"] == "clone"
    assert "repository not found" in result["detail"]
    assert result["detail"].count("repository not found") == 2, "both attempts must be reported"


def test_update_existing_clone_reports_fetch_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    dest = tmp_path / "runtime"
    (dest / ".git").mkdir(parents=True)

    def fake_run(cmd, **kwargs):
        if "fetch" in cmd:
            return _Result(0)
        return _Result(0)

    monkeypatch.setattr(gitutil.subprocess, "run", fake_run)
    result = gitutil.clone_or_update("https://gitcode.com/cann/runtime.git", dest)
    assert result["action"] == "update"
    assert result["ok"] is True
    assert result["path"] == str(dest)


def test_update_reports_failed_fetch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    dest = tmp_path / "runtime"
    (dest / ".git").mkdir(parents=True)

    def fake_run(cmd, **kwargs):
        if "fetch" in cmd:
            return _Result(1, stderr="fatal: unable to access")
        return _Result(0)

    monkeypatch.setattr(gitutil.subprocess, "run", fake_run)
    result = gitutil.clone_or_update("https://gitcode.com/cann/runtime.git", dest)
    assert result["ok"] is False
    assert "unable to access" in result["detail"]


def test_empty_url_does_not_shell_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def fake_run(cmd, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError("no git call expected for an empty url")

    monkeypatch.setattr(gitutil.subprocess, "run", fake_run)
    result = gitutil.clone_or_update("", tmp_path / "x")
    assert result["ok"] is False
    assert result["action"] == "none"
