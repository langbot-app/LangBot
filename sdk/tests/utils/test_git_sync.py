from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from langbot_plugin.utils import git_sync as gs


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


def _make_plugin(tmp_path: Path) -> Path:
    root = tmp_path / "plugin"
    root.mkdir()
    (root / "manifest.yaml").write_text("apiVersion: v1\n", encoding="utf-8")
    return root


# --------------------------------------------------------------------------- #
# pure helpers
# --------------------------------------------------------------------------- #
def test_redact_removes_token_and_credentials():
    assert (
        gs._redact("push https://user:tok@github.com/o/r", "tok")
        == "push https://github.com/o/r"
    )
    assert gs._redact("", "tok") == ""


def test_with_token_only_for_http_urls():
    assert gs._with_token("git@github.com:o/r.git", "tok") == "git@github.com:o/r.git"
    assert (
        gs._with_token("https://github.com/o/r.git", "tok")
        == "https://x-access-token:tok@github.com/o/r.git"
    )


def test_parse_github_https():
    assert gs._parse_github_https("https://github.com/o/r.git") == ("o", "r")
    assert gs._parse_github_https("https://gitlab.com/o/r") is None
    assert gs._parse_github_https("https://github.com/o") is None


def test_is_git_available_returns_bool():
    assert isinstance(gs.is_git_available(), bool)


def test_is_git_repository_false_for_plain_dir(tmp_path):
    assert gs._is_git_repository(str(tmp_path)) is False


def test_run_git_reports_missing_binary(tmp_path, monkeypatch):
    def _boom(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(gs.subprocess, "run", _boom)
    with pytest.raises(gs.GitSyncError, match="Git is not installed"):
        gs._run_git(str(tmp_path), ["status"])


def test_run_git_reports_timeout(tmp_path, monkeypatch):
    def _boom(*args, **kwargs):
        raise subprocess.TimeoutExpired("git", 1)

    monkeypatch.setattr(gs.subprocess, "run", _boom)
    with pytest.raises(gs.GitSyncError, match="timed out"):
        gs._run_git(str(tmp_path), ["status"])


def test_run_git_reports_failure(tmp_path, monkeypatch):
    class _Completed:
        returncode = 1
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr(gs.subprocess, "run", lambda *a, **k: _Completed())
    with pytest.raises(gs.GitSyncError, match="boom"):
        gs._run_git(str(tmp_path), ["status"])


# --------------------------------------------------------------------------- #
# branch resolution (regression: unborn HEAD)
# --------------------------------------------------------------------------- #
def test_current_branch_unborn(tmp_path):
    _git(["init"], tmp_path)

    assert gs._current_branch(str(tmp_path)) in {"main", "master"}


def test_current_branch_detached_head(tmp_path):
    _git(["init"], tmp_path)
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    _git(["add", "-A"], tmp_path)
    _git(
        ["-c", "user.name=t", "-c", "user.email=t@e", "commit", "-m", "init"],
        tmp_path,
    )
    _git(["checkout", "--detach"], tmp_path)

    assert gs._current_branch(str(tmp_path)) == "main"


# --------------------------------------------------------------------------- #
# sync_plugin_to_github
# --------------------------------------------------------------------------- #
def test_sync_without_remote_commits_locally(tmp_path):
    root = _make_plugin(tmp_path)

    result = gs.sync_plugin_to_github(str(root), commit_message="init")

    assert result.committed is True
    assert result.pushed is False
    assert result.branch in {"main", "master"}
    assert result.remote_url == ""
    assert result.commit_sha
    assert any("No git remote" in warning for warning in result.warnings)


def test_sync_nothing_to_commit_on_unborn_repo(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()

    # Regression guard: an empty repository has no HEAD yet, which used to make
    # branch resolution raise instead of reporting a clean no-op.
    result = gs.sync_plugin_to_github(str(root))

    assert result.committed is False
    assert result.pushed is False
    assert result.commit_sha == ""


def test_sync_pushes_to_local_bare_remote(tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        capture_output=True,
        text=True,
    )
    root = _make_plugin(tmp_path)

    result = gs.sync_plugin_to_github(
        str(root),
        repo_url=str(remote),
        commit_message="init",
    )

    assert result.committed is True
    assert result.pushed is True
    assert result.commit_sha

    branches = subprocess.run(
        ["git", f"--git-dir={remote}", "branch", "--list"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert result.branch in branches


def test_sync_explicit_branch(tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        capture_output=True,
        text=True,
    )
    root = _make_plugin(tmp_path)

    result = gs.sync_plugin_to_github(
        str(root),
        repo_url=str(remote),
        branch="feature/x",
    )

    assert result.branch == "feature/x"
    assert result.pushed is True


# --------------------------------------------------------------------------- #
# GitHub auto-create
# --------------------------------------------------------------------------- #
def test_ensure_github_repo_skips_without_token(tmp_path):
    assert gs._ensure_github_repo(str(tmp_path), "https://github.com/o/r", "") == []


def test_ensure_github_repo_skips_non_github(tmp_path):
    assert gs._ensure_github_repo(str(tmp_path), "https://gitlab.com/o/r", "tok") == []


def test_ensure_github_repo_existing_public_is_noop(monkeypatch, tmp_path):
    monkeypatch.setattr(gs, "_remote_exists", lambda *a, **k: True)
    monkeypatch.setattr(
        gs.httpx, "get", lambda *a, **k: _Response(200, {"private": False})
    )

    assert gs._ensure_github_repo(str(tmp_path), "https://github.com/o/r", "tok") == []


class _Response:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = ""

    def json(self) -> dict:
        return self._payload


def test_ensure_github_repo_creates_public_repo(monkeypatch, tmp_path):
    monkeypatch.setattr(gs, "_remote_exists", lambda *a, **k: False)
    captured: dict = {}

    def _post(url, headers=None, json=None, timeout=None):
        captured.update(json or {})
        return _Response(201)

    monkeypatch.setattr(gs.httpx, "get", lambda *a, **k: _Response(200, {"login": "o"}))
    monkeypatch.setattr(gs.httpx, "post", _post)

    warnings = gs._ensure_github_repo(str(tmp_path), "https://github.com/o/r", "tok")

    assert captured == {"name": "r", "private": False}
    assert warnings and "Created GitHub repository" in warnings[0]


def test_ensure_github_repo_create_conflict_is_noop(monkeypatch, tmp_path):
    monkeypatch.setattr(gs, "_remote_exists", lambda *a, **k: False)
    monkeypatch.setattr(gs.httpx, "get", lambda *a, **k: _Response(200, {"login": "o"}))
    monkeypatch.setattr(gs.httpx, "post", lambda *a, **k: _Response(422))

    assert gs._ensure_github_repo(str(tmp_path), "https://github.com/o/r", "tok") == []


def test_ensure_github_repo_existing_private_is_made_public(monkeypatch, tmp_path):
    monkeypatch.setattr(gs, "_remote_exists", lambda *a, **k: True)
    monkeypatch.setattr(
        gs.httpx, "get", lambda *a, **k: _Response(200, {"private": True})
    )
    captured: dict = {}

    def _patch(url, headers=None, json=None, timeout=None):
        captured.update(json or {})
        return _Response(200)

    monkeypatch.setattr(gs.httpx, "patch", _patch)

    warnings = gs._ensure_github_repo(str(tmp_path), "https://github.com/o/r", "tok")

    assert captured == {"private": False}
    assert warnings and "public" in warnings[0]


def test_ensure_github_repo_existing_invisible_is_untouched(monkeypatch, tmp_path):
    # A token that cannot read the metadata (e.g. fine-grained token without the
    # repo scope) must not block the push with a failed visibility probe.
    monkeypatch.setattr(gs, "_remote_exists", lambda *a, **k: True)
    monkeypatch.setattr(gs.httpx, "get", lambda *a, **k: _Response(404))

    assert gs._ensure_github_repo(str(tmp_path), "https://github.com/o/r", "tok") == []


def test_ensure_github_repo_patch_failure_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(gs, "_remote_exists", lambda *a, **k: True)
    monkeypatch.setattr(
        gs.httpx, "get", lambda *a, **k: _Response(200, {"private": True})
    )
    monkeypatch.setattr(
        gs.httpx,
        "patch",
        lambda *a, **k: _Response(403, {"message": "Forbidden"}),
    )

    with pytest.raises(gs.GitSyncError, match="public"):
        gs._ensure_github_repo(str(tmp_path), "https://github.com/o/r", "tok")


def test_ensure_github_repo_auth_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(gs, "_remote_exists", lambda *a, **k: False)
    monkeypatch.setattr(gs.httpx, "get", lambda *a, **k: _Response(401))

    with pytest.raises(gs.GitSyncError, match="authentication failed"):
        gs._ensure_github_repo(str(tmp_path), "https://github.com/o/r", "tok")
