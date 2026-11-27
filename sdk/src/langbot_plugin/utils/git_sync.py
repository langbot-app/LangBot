"""Git synchronisation helper for the "upload plugin to LangBot Space" flow.

The upload flow optionally mirrors the local plugin directory into a GitHub
repository. Two credential styles are supported, matching the product decision:

* **Reuse local git** (default): stage, commit and ``git push`` using whatever
  remote/credentials the developer already configured in the working copy.
* **Explicit override**: when the upload page supplies a repository URL and/or a
  token, the token is used only for this single ``git push`` via a temporary
  credential-bearing URL, and never persisted to ``.git/config``.

Security notes:
* The token is never written to disk, never committed and never echoed back in
  an error message (``redact_secrets`` strips it defensively).
* All git invocations run with ``GIT_TERMINAL_PROMPT=0`` so a missing credential
  fails fast instead of hanging the Runtime waiting for interactive input.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import typing
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit

import httpx

# Bound every git subprocess so a network stall cannot pin the Runtime forever.
_GIT_TIMEOUT_SECONDS = 120


class GitSyncError(RuntimeError):
    """Raised when a git operation fails; the message is safe to surface."""


@dataclass(slots=True)
class GitSyncResult:
    """Outcome of a synchronisation attempt."""

    committed: bool
    pushed: bool
    branch: str = ""
    remote_url: str = ""
    commit_sha: str = ""
    message: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, typing.Any]:
        return {
            "committed": self.committed,
            "pushed": self.pushed,
            "branch": self.branch,
            "remote_url": self.remote_url,
            "commit_sha": self.commit_sha,
            "message": self.message,
            "warnings": list(self.warnings),
        }


def is_git_available() -> bool:
    return shutil.which("git") is not None


def _redact(text: str, token: str) -> str:
    """Remove a token (and any URL-embedded credentials) from a message."""

    if not text:
        return text
    if token:
        text = text.replace(token, "***")
    # ``https://user:pass@host`` -> ``https://host``
    return re.sub(r"(https?://)[^/@\s]+@", r"\1", text)


def _run_git(
    cwd: str,
    args: list[str],
    *,
    token: str = "",
    extra_env: dict[str, str] | None = None,
) -> str:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    # A neutral identity avoids failures on machines without a global git config.
    env.setdefault("GIT_AUTHOR_NAME", env.get("GIT_AUTHOR_NAME", "LangBot"))
    env.setdefault(
        "GIT_AUTHOR_EMAIL", env.get("GIT_AUTHOR_EMAIL", "noreply@langbot.app")
    )
    env.setdefault("GIT_COMMITTER_NAME", env["GIT_AUTHOR_NAME"])
    env.setdefault("GIT_COMMITTER_EMAIL", env["GIT_AUTHOR_EMAIL"])
    if extra_env:
        env.update(extra_env)

    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitSyncError(_redact(f"Git operation timed out: {exc}", token)) from exc
    except FileNotFoundError as exc:
        raise GitSyncError("Git is not installed on the Runtime host") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise GitSyncError(_redact(f"git {' '.join(args)} failed: {detail}", token))
    return completed.stdout


def _is_git_repository(cwd: str) -> bool:
    if not os.path.isdir(os.path.join(cwd, ".git")):
        return False
    try:
        output = _run_git(cwd, ["rev-parse", "--is-inside-work-tree"])
    except GitSyncError:
        return False
    return output.strip() == "true"


def _current_branch(cwd: str) -> str:
    # A freshly ``git init``-ed repository has an unborn HEAD: ``rev-parse
    # --abbrev-ref HEAD`` fails with "ambiguous argument 'HEAD'". The symbolic
    # ref still resolves to the intended branch name, so read it first.
    try:
        symbolic = _run_git(cwd, ["symbolic-ref", "--short", "HEAD"]).strip()
        if symbolic:
            return symbolic
    except GitSyncError:
        pass
    try:
        output = _run_git(cwd, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
        if output and output != "HEAD":
            return output
    except GitSyncError:
        pass
    # Detached HEAD: fall back to the remote default or main.
    try:
        symbolic = _run_git(
            cwd, ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"]
        ).strip()
        if symbolic.startswith("origin/"):
            return symbolic[len("origin/") :]
    except GitSyncError:
        pass
    return "main"


def _with_token(url: str, token: str) -> str:
    """Inject a token into an HTTPS remote URL for one push only."""

    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        # SSH remotes carry their own key material; the token is not applicable.
        return url
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    netloc = f"x-access-token:{token}@{host}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _has_remote(cwd: str, name: str = "origin") -> bool:
    try:
        _run_git(cwd, ["remote", "get-url", name])
        return True
    except GitSyncError:
        return False


def _commit_identity_args(cwd: str) -> list[str]:
    """Return ``-c user.name/-c user.email`` overrides when identity is unset.

    ``git commit`` aborts with "configure user.name and user.email" on a host
    without a global identity. Passing ``-c`` satisfies the check without
    mutating the user's global config; when an identity already exists the
    defaults are left alone so the real author is preserved.
    """

    args: list[str] = []
    for key, fallback in (
        ("user.name", "LangBot"),
        ("user.email", "noreply@langbot.app"),
    ):
        try:
            configured = _run_git(cwd, ["config", "--get", key]).strip()
        except GitSyncError:
            configured = ""
        if not configured:
            args.extend(["-c", f"{key}={fallback}"])
    return args


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _parse_github_https(url: str) -> tuple[str, str] | None:
    parts = urlsplit(url)
    if (parts.hostname or "").lower() not in ("github.com", "www.github.com"):
        return None
    segments = [segment for segment in parts.path.strip("/").split("/") if segment]
    if len(segments) < 2:
        return None
    owner, repo = segments[0], segments[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        return None
    return owner, repo


def _remote_exists(plugin_root: str, url: str, token: str) -> bool:
    check_url = _with_token(url, token) if token else url
    try:
        _run_git(plugin_root, ["ls-remote", "--heads", check_url], token=token)
        return True
    except GitSyncError:
        return False


def _github_repo_api_url(owner: str, repo: str) -> str:
    """Return the REST API URL for an ``owner/repo`` pair."""

    return f"https://api.github.com/repos/{owner}/{repo}"


def _github_authenticated_login(token: str) -> str:
    """Return the login of the token owner, failing loudly when unauthenticated."""

    try:
        login_resp = httpx.get(
            "https://api.github.com/user",
            headers=_github_headers(token),
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise GitSyncError(_redact(f"GitHub request failed: {exc}", token)) from exc
    if login_resp.status_code != 200:
        raise GitSyncError(
            _redact(
                f"GitHub authentication failed (HTTP {login_resp.status_code}); "
                "the repository does not exist and could not be created",
                token,
            )
        )
    return str(login_resp.json().get("login") or "")


def _create_github_repo(owner: str, repo: str, token: str) -> list[str]:
    """Create a new **public** GitHub repository for ``owner/repo``."""

    login = _github_authenticated_login(token)
    create_url = (
        "https://api.github.com/user/repos"
        if owner.lower() == login.lower()
        else f"https://api.github.com/orgs/{owner}/repos"
    )
    try:
        create_resp = httpx.post(
            create_url,
            headers=_github_headers(token),
            json={"name": repo, "private": False},
            timeout=30,
        )
    except httpx.HTTPError as exc:
        raise GitSyncError(_redact(f"GitHub request failed: {exc}", token)) from exc

    if create_resp.status_code in (200, 201):
        return [f"Created GitHub repository {owner}/{repo}."]
    if create_resp.status_code == 422:
        # Already exists (e.g. created concurrently) — nothing to do.
        return []

    detail = ""
    try:
        detail = str(create_resp.json().get("message") or "")
    except Exception:  # noqa: BLE001 - best-effort error detail
        detail = create_resp.text[:200]
    raise GitSyncError(
        _redact(
            f"Failed to create GitHub repository {owner}/{repo}: "
            f"HTTP {create_resp.status_code} {detail}",
            token,
        )
    )


def _ensure_github_repo_public(owner: str, repo: str, token: str) -> list[str]:
    """Flip an existing private GitHub repository to public.

    A no-op when the repository is already public or when the visibility probe
    is inconclusive (the push itself must not be blocked by a read-only probe).
    """

    try:
        info_resp = httpx.get(
            _github_repo_api_url(owner, repo),
            headers=_github_headers(token),
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise GitSyncError(_redact(f"GitHub request failed: {exc}", token)) from exc

    if info_resp.status_code != 200:
        # The token cannot read the repository metadata; leave it untouched.
        return []
    try:
        is_private = bool(info_resp.json().get("private"))
    except Exception:  # noqa: BLE001 - best-effort metadata probe
        return []
    if not is_private:
        return []

    try:
        patch_resp = httpx.patch(
            _github_repo_api_url(owner, repo),
            headers=_github_headers(token),
            json={"private": False},
            timeout=30,
        )
    except httpx.HTTPError as exc:
        raise GitSyncError(_redact(f"GitHub request failed: {exc}", token)) from exc

    if patch_resp.status_code == 200:
        return [f"Changed GitHub repository {owner}/{repo} to public."]

    detail = ""
    try:
        detail = str(patch_resp.json().get("message") or "")
    except Exception:  # noqa: BLE001 - best-effort error detail
        detail = getattr(patch_resp, "text", "")[:200]
    raise GitSyncError(
        _redact(
            f"Failed to make GitHub repository {owner}/{repo} public: "
            f"HTTP {patch_resp.status_code} {detail}",
            token,
        )
    )


def _ensure_github_repo(
    plugin_root: str,
    effective_remote: str,
    token: str,
) -> list[str]:
    """Create the GitHub repository when missing, and always keep it public.

    Only runs when a token is supplied and the remote is a github.com HTTPS URL,
    so an accidental push never silently creates test repositories. New
    repositories are created public; an existing private repository is flipped to
    public so the published plugin source stays discoverable.
    """

    if not token:
        return []

    parsed = _parse_github_https(effective_remote)
    if parsed is None:
        return []
    owner, repo = parsed

    if not _remote_exists(plugin_root, effective_remote, token):
        return _create_github_repo(owner, repo, token)
    return _ensure_github_repo_public(owner, repo, token)


def sync_plugin_to_github(
    plugin_root: str,
    *,
    repo_url: str = "",
    token: str = "",
    branch: str = "",
    commit_message: str = "",
    file_name: str = "",
) -> GitSyncResult:
    """Commit and push the plugin directory to GitHub.

    Args:
        plugin_root: The plugin working directory.
        repo_url: Optional remote URL to set as ``origin`` before pushing. When
            empty, the existing ``origin`` (local git configuration) is reused.
        token: Optional access token used only for this push.
        branch: Optional target branch; defaults to the current branch.
        commit_message: Optional commit message.
        file_name: Optional filename of the package to also commit, if present
            under ``plugin_root`` (e.g. the built ``.lbpkg`` next to the source).
    """

    if not is_git_available():
        raise GitSyncError("Git is not available on the Runtime host")

    plugin_root = os.path.abspath(plugin_root)
    if not os.path.isdir(plugin_root):
        raise GitSyncError("Plugin working directory is unavailable")

    if not _is_git_repository(plugin_root):
        _run_git(plugin_root, ["init"])
        # Make ``main`` the default branch for freshly initialised repositories.
        if not branch:
            branch = "main"

    warnings: list[str] = []

    remote_url = repo_url.strip()
    if remote_url:
        if _has_remote(plugin_root, "origin"):
            _run_git(plugin_root, ["remote", "set-url", "origin", remote_url])
        else:
            _run_git(plugin_root, ["remote", "add", "origin", remote_url])

    effective_remote = ""
    if _has_remote(plugin_root, "origin"):
        effective_remote = _run_git(
            plugin_root, ["remote", "get-url", "origin"]
        ).strip()
    else:
        warnings.append("No git remote configured; committed locally but did not push.")

    target_branch = branch.strip() or _current_branch(plugin_root)

    if not branch.strip():
        # Ensure the checked-out branch has the intended name (e.g. unborn main).
        try:
            head_branch = _run_git(
                plugin_root, ["rev-parse", "--abbrev-ref", "HEAD"]
            ).strip()
            if head_branch in ("HEAD", ""):
                _run_git(plugin_root, ["checkout", "-b", target_branch])
        except GitSyncError:
            pass

    _run_git(plugin_root, ["add", "-A"])

    commit_sha = ""
    committed = False
    message = commit_message.strip() or "Upload plugin via LangBot"
    try:
        _run_git(
            plugin_root,
            [*_commit_identity_args(plugin_root), "commit", "-m", message],
        )
        committed = True
        commit_sha = _run_git(plugin_root, ["rev-parse", "HEAD"]).strip()
    except GitSyncError as exc:
        # "nothing to commit" is a normal no-op, not a failure.
        if (
            "nothing to commit" in str(exc).lower()
            or "no changes added" in str(exc).lower()
        ):
            try:
                commit_sha = _run_git(plugin_root, ["rev-parse", "HEAD"]).strip()
            except GitSyncError:
                commit_sha = ""
        else:
            raise

    if not effective_remote:
        return GitSyncResult(
            committed=committed,
            pushed=False,
            branch=target_branch,
            remote_url="",
            commit_sha=commit_sha,
            message="Committed locally; no remote to push to.",
            warnings=warnings,
        )

    # Auto-create the repository when a token is supplied and it is missing.
    warnings.extend(_ensure_github_repo(plugin_root, effective_remote, token))

    push_url = _with_token(effective_remote, token) if token else effective_remote
    # ``--`` separates refspecs; use an explicit URL so an override token never
    # lands in ``.git/config`` (the origin remote may point elsewhere).
    _run_git(
        plugin_root,
        ["push", push_url, f"HEAD:refs/heads/{target_branch}"],
        token=token,
    )

    safe_remote = _redact(effective_remote, token)
    return GitSyncResult(
        committed=committed,
        pushed=True,
        branch=target_branch,
        remote_url=safe_remote,
        commit_sha=commit_sha,
        message=f"Pushed to {safe_remote} ({target_branch}).",
        warnings=warnings,
    )
