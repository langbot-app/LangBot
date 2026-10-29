# GitHubKit - GitHub integration plugin for LangBot.
# Provides read-only GitHub queries/search plus repository event push to IM
# sessions via background polling of the GitHub events API.
from __future__ import annotations

import os
import sys
import json
import asyncio
import datetime
from typing import Any, Optional

import httpx

from langbot_plugin.api.definition.plugin import BasePlugin
from langbot_plugin.api.proxies.invocation import (
    bind_invocation,
    current_binding,
    current_config,
)

# Allow importing the plugin-level i18n module.
sys.path.insert(0, os.path.dirname(__file__))
from i18n import get_text  # noqa: E402

API_BASE = "https://api.github.com"
SUBS_KEY = "subscriptions"  # storage key for repo -> [subscribers] map

# Give the runtime a moment to settle before the first poll (seconds).
POLL_START_DELAY = 10

# Process-cache slot used when no installation binding is available (dedicated
# placement). It maps to the legacy storage key so existing dedicated installs
# keep reading their own subscriptions.
DEDICATED_SCOPE = "dedicated"

# Written by the SDK worker launcher. A shared worker must always carry a trusted
# invocation binding; without one it must refuse to touch tenant state instead of
# falling back to a binding-less scope shared by every installation.
RUNTIME_PROFILE_ENV = "LANGBOT_PLUGIN_RUNTIME_PROFILE"


def installation_scope(binding) -> str:
    """Return the stable scope token for one installation binding.

    ``runtime_revision`` changes on every worker upgrade, so only the stable
    installation identity triple is used; the revoked binding and the resumed
    poller must resolve to the same scope.
    """

    return f"{binding.instance_uuid}:{binding.workspace_uuid}:{binding.installation_uuid}"


def storage_key(scope: str) -> str:
    """Return the plugin-storage key for one scope.

    Host rows are keyed by ``[instance, workspace, owner_type, owner, key]`` with
    no installation dimension, so the installation scope has to live in the
    plugin's own key. The binding-less dedicated scope keeps the legacy key.
    """

    if scope == DEDICATED_SCOPE:
        return SUBS_KEY
    return f"{SUBS_KEY}:{scope}"


class _Poller:
    """背景轮询 belongs to exactly one installation binding.

    The registry entry carries the poller's subscription lock, its captured
    invocation config (token/interval/cap/language), and the task handle so
    ``on_installation_revoked`` can stop it.
    """

    __slots__ = ("scope", "binding", "lock", "config", "task")

    def __init__(self, scope: str, binding, config: dict[str, Any]) -> None:
        self.scope = scope
        self.binding = binding
        self.lock = asyncio.Lock()
        self.config = config
        self.task: Optional[asyncio.Task] = None


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class GitHubKitPlugin(BasePlugin):
    """GitHub integration: queries, search, and event-push subscriptions.

    Subscriptions are stored as JSON in plugin KV under ``subscriptions``::

        {
          "owner/repo": {
            "subscribers": {
              "<session_id>": {
                "bot_uuid": "...",
                "target_type": "group"|"person",
                "target_id": "...",
                "events": ["push","pull_request",...] | null,   # null = all
                "lang": "en_US"|"zh_Hans",   # language for pushed messages
                "added_at": "iso"
              }
            },
            "last_event_id": "123456789"
          }
        }
    """

    # ------------------------------------------------------------- lifecycle

    def __init__(self) -> None:
        super().__init__()
        self._pollers: dict[str, _Poller] = {}

    async def initialize(self) -> None:
        """Process-wide initialization only.

        Under shared placement this runs once per worker with an empty config and
        no installation context, so configuration is read per invocation and the
        event poller is started lazily per installation binding instead.
        """
        return None

    async def on_installation_revoked(self, binding) -> None:
        """Stop the revoked installation's poller; only process-local state is available."""
        poller = self._pollers.pop(installation_scope(binding), None)
        if poller is None:
            return
        task = poller.task
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def destroy(self) -> None:
        """Stop every installation's poller (process end)."""
        pending = [
            poller.task
            for poller in self._pollers.values()
            if poller.task is not None and not poller.task.done()
        ]
        self._pollers.clear()
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    # --------------------------------------------------------- scope & config

    def _current_scope(self) -> str:
        binding = self.get_installation_binding()
        if binding is not None:
            return installation_scope(binding)
        if os.environ.get(RUNTIME_PROFILE_ENV) == "shared":
            raise RuntimeError(
                "shared invocation has no trusted installation binding; "
                "refusing to read or write tenant state"
            )
        return DEDICATED_SCOPE

    def _poller_config(self) -> dict[str, Any]:
        """Read the invoking installation's poll settings (never cached on the object)."""
        cfg = self.get_config() or {}
        try:
            interval = max(60, int(cfg.get("poll_interval", 120) or 120))
        except (TypeError, ValueError):
            interval = 120
        try:
            max_events = max(1, int(cfg.get("max_events_per_push", 5) or 5))
        except (TypeError, ValueError):
            max_events = 5
        return {
            "token": (cfg.get("github_token") or "").strip(),
            "poll_interval": interval,
            "max_events": max_events,
            "language": cfg.get("language", "en_US") or "en_US",
        }

    def get_language(self) -> str:
        return self._poller_config()["language"]

    def t(self, key: str, **kwargs) -> str:
        return get_text(self.get_language(), key, **kwargs)

    def _ensure_poller(self) -> _Poller:
        """Start (or refresh) the poller belonging to the invoking installation.

        One installation's subscriptions are polled by exactly one task, keyed by
        the full binding; a worker upgrade (same installation, new revision)
        restarts it with the new binding so Host calls stay authorized.
        """
        scope = self._current_scope()
        binding = self.get_installation_binding()
        handler = getattr(self, "plugin_runtime_handler", None)
        inv_config = current_config(handler)
        config = self._poller_config()
        poller = self._pollers.get(scope)
        if poller is not None and poller.binding == binding:
            poller.config = config
            return poller
        if poller is not None and poller.task is not None and not poller.task.done():
            poller.task.cancel()
        poller = _Poller(scope, binding, config)
        try:
            poller.task = asyncio.create_task(
                self._poll_loop(poller, handler, inv_config, binding)
            )
        except RuntimeError:
            poller.task = None
        self._pollers[scope] = poller
        return poller

    def __del__(self) -> None:
        for poller in getattr(self, "_pollers", {}).values():
            if poller.task is not None and not poller.task.done():
                poller.task.cancel()

    # --------------------------------------------------------------- http

    def _headers(self, token: str) -> dict[str, str]:
        h = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "LangBot-GitHubKit",
        }
        if token:
            h["Authorization"] = f"Bearer {token}"
        return h

    async def _get(
        self,
        path: str,
        params: dict | None = None,
        *,
        token: Optional[str] = None,
    ) -> tuple[int, Any, dict]:
        """GET against the GitHub API. Returns (status, json_or_text, headers)."""
        if token is None:
            # Any invocation of this installation resumes its event poller.
            self._ensure_poller()
            token = self._poller_config()["token"]
        url = path if path.startswith("http") else f"{API_BASE}{path}"
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, headers=self._headers(token), params=params or {})
            try:
                body = r.json()
            except Exception:
                body = r.text
            return r.status_code, body, dict(r.headers)

    def _err_msg(self, status: int, body: Any) -> str:
        msg = ""
        if isinstance(body, dict):
            msg = body.get("message", "")
        if status == 404:
            return self.t("err.404")
        if status in (401, 403):
            if "rate limit" in str(msg).lower():
                return self.t("err.rate")
            return self.t("err.perm", status=status, msg=msg or self.t("err.perm_default"))
        return self.t("err.generic", status=status, msg=msg or body)

    # ----------------------------------------------------------- queries

    async def repo_info(self, repo: str) -> str:
        repo = _norm_repo(repo)
        if not repo:
            return self.t("repo.usage")
        status, body, _ = await self._get(f"/repos/{repo}")
        if status != 200:
            return self._err_msg(status, body)
        dash = self.t("repo.dash")
        lang = body.get("language") or dash
        lic = (body.get("license") or {}).get("spdx_id") or dash
        desc = body.get("description") or self.t("repo.no_desc")
        homepage = body.get("homepage")
        out = self.t(
            "repo.body",
            full_name=body["full_name"],
            desc=desc,
            stars=body["stargazers_count"],
            forks=body["forks_count"],
            watchers=body["watchers_count"],
            issues=body["open_issues_count"],
            lang=lang,
            lic=lic,
            branch=body.get("default_branch", dash),
            url=body["html_url"],
        )
        if homepage:
            out += "\n" + self.t("repo.homepage", homepage=homepage)
        return out

    async def list_issues(self, repo: str, state: str = "open") -> str:
        repo = _norm_repo(repo)
        if not repo:
            return self.t("issues.usage")
        state = state if state in ("open", "closed", "all") else "open"
        status, body, _ = await self._get(
            f"/repos/{repo}/issues",
            {"state": state, "per_page": 10, "sort": "updated"},
        )
        if status != 200:
            return self._err_msg(status, body)
        issues = [i for i in body if "pull_request" not in i]
        if not issues:
            return self.t("issues.none", repo=repo, state=state)
        lines = [self.t("issues.header", repo=repo, state=state)]
        for i in issues[:10]:
            labels = ",".join(l["name"] for l in i.get("labels", [])[:3])
            ltxt = f" [{labels}]" if labels else ""
            lines.append(self.t("issues.item", number=i["number"], title=i["title"], labels=ltxt))
        return "\n".join(lines)

    async def list_prs(self, repo: str, state: str = "open") -> str:
        repo = _norm_repo(repo)
        if not repo:
            return self.t("prs.usage")
        state = state if state in ("open", "closed", "all") else "open"
        status, body, _ = await self._get(
            f"/repos/{repo}/pulls",
            {"state": state, "per_page": 10, "sort": "updated", "direction": "desc"},
        )
        if status != 200:
            return self._err_msg(status, body)
        if not body:
            return self.t("prs.none", repo=repo, state=state)
        lines = [self.t("prs.header", repo=repo, state=state)]
        for p in body[:10]:
            draft = self.t("prs.draft") if p.get("draft") else ""
            lines.append(
                self.t("prs.item", number=p["number"], title=p["title"], draft=draft, user=p["user"]["login"])
            )
        return "\n".join(lines)

    async def issue_detail(self, repo: str, number: str) -> str:
        repo = _norm_repo(repo)
        if not repo or not number:
            return self.t("issue.usage")
        try:
            n = int(str(number).lstrip("#"))
        except ValueError:
            return self.t("issue.bad_number")
        status, body, _ = await self._get(f"/repos/{repo}/issues/{n}")
        if status != 200:
            return self._err_msg(status, body)
        is_pr = "pull_request" in body
        kind = self.t("issue.kind_pr") if is_pr else self.t("issue.kind_issue")
        state = body["state"]
        labels = ",".join(l["name"] for l in body.get("labels", []))
        ltxt = self.t("issue.labels", labels=labels) if labels else ""
        comments = body.get("comments", 0)
        text = (body.get("body") or "").strip()
        if len(text) > 400:
            text = text[:400] + "\u2026"
        body_txt = f"\n\n{text}" if text else ""
        return self.t(
            "issue.body",
            emoji="\U0001f500" if is_pr else "\U0001f41b",
            repo=repo,
            kind=kind,
            number=body["number"],
            state=state,
            title=body["title"],
            author=body["user"]["login"],
            comments=comments,
            labels=ltxt,
            url=body["html_url"],
            body=body_txt,
        )

    async def releases(self, repo: str) -> str:
        repo = _norm_repo(repo)
        if not repo:
            return self.t("releases.usage")
        status, body, _ = await self._get(
            f"/repos/{repo}/releases", {"per_page": 5}
        )
        if status != 200:
            return self._err_msg(status, body)
        if not body:
            return self.t("releases.none", repo=repo)
        lines = [self.t("releases.header", repo=repo)]
        for r in body[:5]:
            pre = self.t("releases.prerelease") if r.get("prerelease") else ""
            date = (r.get("published_at") or "")[:10]
            lines.append(self.t("releases.item", tag=r["tag_name"], name=r.get("name", ""), pre=pre, date=date))
        return "\n".join(lines)

    async def user_info(self, username: str) -> str:
        username = (username or "").strip().lstrip("@")
        if not username:
            return self.t("user.usage")
        status, body, _ = await self._get(f"/users/{username}")
        if status != 200:
            return self._err_msg(status, body)
        name = body.get("name") or body["login"]
        bio = body.get("bio") or ""
        biotxt = f"\n{bio}" if bio else ""
        return self.t(
            "user.body",
            name=name,
            login=body["login"],
            bio=biotxt,
            repos=body.get("public_repos", 0),
            followers=body.get("followers", 0),
            following=body.get("following", 0),
            url=body["html_url"],
        )

    async def search_repos(self, query: str) -> str:
        query = (query or "").strip()
        if not query:
            return self.t("search.usage")
        status, body, _ = await self._get(
            "/search/repositories",
            {"q": query, "per_page": 8, "sort": "stars", "order": "desc"},
        )
        if status != 200:
            return self._err_msg(status, body)
        items = body.get("items", [])
        if not items:
            return self.t("search.none", query=query)
        lines = [self.t("search.header", query=query)]
        for it in items[:8]:
            desc = it.get("description") or ""
            if len(desc) > 50:
                desc = desc[:50] + "\u2026"
            lines.append(self.t("search.item", stars=it["stargazers_count"], full_name=it["full_name"], desc=desc))
        return "\n".join(lines)

    # ------------------------------------------------------- subscriptions

    async def _load_subs(self, scope: str) -> dict[str, Any]:
        try:
            raw = await self.get_plugin_storage(storage_key(scope))
        except Exception:
            raw = None
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except Exception:
            return {}

    async def _save_subs(self, scope: str, subs: dict[str, Any]) -> None:
        await self.set_plugin_storage(
            storage_key(scope), json.dumps(subs, ensure_ascii=False).encode("utf-8")
        )

    async def subscribe(
        self,
        repo: str,
        session_id: str,
        bot_uuid: str,
        target_type: str,
        target_id: str,
        events: Optional[list[str]],
    ) -> str:
        repo = _norm_repo(repo)
        if not repo:
            return self.t("sub.usage")
        poller = self._ensure_poller()
        token = poller.config["token"]
        status, body, _ = await self._get(f"/repos/{repo}", token=token)
        if status != 200:
            return self._err_msg(status, body)
        async with poller.lock:
            subs = await self._load_subs(poller.scope)
            entry = subs.setdefault(repo, {"subscribers": {}, "last_event_id": None})
            if entry.get("last_event_id") is None:
                st, ev, _ = await self._get(
                    f"/repos/{repo}/events", {"per_page": 1}, token=token
                )
                if st == 200 and isinstance(ev, list) and ev:
                    entry["last_event_id"] = ev[0]["id"]
            entry["subscribers"][session_id] = {
                "bot_uuid": bot_uuid,
                "target_type": target_type,
                "target_id": target_id,
                "events": events,  # None = all
                "lang": self.get_language(),
                "added_at": _now_iso(),
            }
            await self._save_subs(poller.scope, subs)
        evtxt = self.t("sub.all_events") if not events else self.t("misc.sep").join(events)
        return self.t(
            "sub.ok",
            repo=repo,
            events=evtxt,
            interval=poller.config["poll_interval"],
        )

    async def unsubscribe(self, repo: str, session_id: str) -> str:
        repo = _norm_repo(repo)
        if not repo:
            return self.t("unsub.usage")
        poller = self._ensure_poller()
        async with poller.lock:
            subs = await self._load_subs(poller.scope)
            entry = subs.get(repo)
            if not entry or session_id not in entry.get("subscribers", {}):
                return self.t("unsub.not_subbed", repo=repo)
            del entry["subscribers"][session_id]
            if not entry["subscribers"]:
                del subs[repo]
            await self._save_subs(poller.scope, subs)
        return self.t("unsub.ok", repo=repo)

    async def list_subscriptions(self, session_id: str) -> str:
        poller = self._ensure_poller()
        subs = await self._load_subs(poller.scope)
        mine = []
        for repo, entry in subs.items():
            sub = entry.get("subscribers", {}).get(session_id)
            if sub:
                events = sub.get("events")
                evtxt = self.t("subs.all") if not events else self.t("misc.sep").join(events)
                mine.append(self.t("subs.item", repo=repo, events=evtxt))
        if not mine:
            return self.t("subs.none")
        return self.t("subs.header") + "\n" + "\n".join(mine)

    # --------------------------------------------------------- poller

    async def _poll_loop(self, poller: _Poller, handler, inv_config, binding) -> None:
        """Poll one installation's subscriptions inside its captured invocation.

        A detached task does not inherit a live invocation, so the config and
        binding captured when the poller started are re-entered explicitly; this
        keeps every storage/send call inside the originating installation.
        """
        with bind_invocation(handler, config=inv_config, binding=binding):
            await asyncio.sleep(POLL_START_DELAY)
            while True:
                try:
                    await self._poll_once(poller)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass
                await asyncio.sleep(poller.config["poll_interval"])

    async def _poll_once(self, poller: _Poller) -> None:
        async with poller.lock:
            subs = await self._load_subs(poller.scope)
            repos = list(subs.keys())
        if not repos:
            return
        for repo in repos:
            try:
                await self._poll_repo(poller, repo)
            except asyncio.CancelledError:
                raise
            except Exception:
                continue

    async def _poll_repo(self, poller: _Poller, repo: str) -> None:
        status, events, _ = await self._get(
            f"/repos/{repo}/events", {"per_page": 30}, token=poller.config["token"]
        )
        if status != 200 or not isinstance(events, list):
            return
        async with poller.lock:
            subs = await self._load_subs(poller.scope)
            entry = subs.get(repo)
            if not entry or not entry.get("subscribers"):
                return
            last_id = entry.get("last_event_id")
            new_events = []
            for ev in events:
                if last_id is not None and ev["id"] == last_id:
                    break
                new_events.append(ev)
            if events:
                entry["last_event_id"] = events[0]["id"]
            subscribers = dict(entry["subscribers"])
            await self._save_subs(poller.scope, subs)

        if not new_events or last_id is None:
            return

        new_events.reverse()  # chronological order
        new_events = new_events[-poller.config["max_events"] :]

        for session_id, sub in subscribers.items():
            wanted = sub.get("events")  # None = all
            lang = sub.get("lang", poller.config["language"])
            msgs = []
            for ev in new_events:
                etype = _event_kind(ev)
                if wanted and etype not in wanted:
                    continue
                line = _format_event(lang, repo, ev)
                if line:
                    msgs.append(line)
            if not msgs:
                continue
            text = get_text(lang, "push.header", repo=repo) + "\n" + "\n".join(msgs)
            await self._push(sub, text)

    async def _push(self, sub: dict, text: str) -> None:
        from langbot_plugin.api.entities.builtin.platform import (
            message as platform_message,
        )

        try:
            await self.send_message(
                sub["bot_uuid"],
                sub["target_type"],
                str(sub["target_id"]),
                platform_message.MessageChain(
                    [platform_message.Plain(text=text)]
                ),
            )
        except Exception:
            pass


# --------------------------------------------------------------- helpers


def _norm_repo(repo: str) -> str:
    repo = (repo or "").strip()
    if repo.startswith("http"):
        repo = repo.rstrip("/")
        parts = repo.split("/")
        if len(parts) >= 2:
            repo = f"{parts[-2]}/{parts[-1]}"
    repo = repo.removesuffix(".git")
    if repo.count("/") != 1:
        return ""
    return repo


# Map GitHub event API types to short kind tokens used in user filters.
_EVENT_TYPE_MAP = {
    "PushEvent": "push",
    "PullRequestEvent": "pull_request",
    "IssuesEvent": "issues",
    "IssueCommentEvent": "issue_comment",
    "ReleaseEvent": "release",
    "WatchEvent": "star",
    "ForkEvent": "fork",
    "CreateEvent": "create",
    "DeleteEvent": "delete",
    "PullRequestReviewEvent": "pr_review",
    "PullRequestReviewCommentEvent": "pr_review_comment",
}

# Friendly aliases users may type for the event filter.
EVENT_ALIASES = {
    "push": "push",
    "commit": "push",
    "commits": "push",
    "pr": "pull_request",
    "prs": "pull_request",
    "pull_request": "pull_request",
    "issue": "issues",
    "issues": "issues",
    "comment": "issue_comment",
    "release": "release",
    "releases": "release",
    "star": "star",
    "stars": "star",
    "fork": "fork",
    "forks": "fork",
}


def _event_kind(ev: dict) -> str:
    return _EVENT_TYPE_MAP.get(ev.get("type", ""), ev.get("type", "").lower())


def _format_event(lang: str, repo: str, ev: dict) -> str:
    etype = ev.get("type", "")
    actor = (ev.get("actor") or {}).get("login", "?")
    payload = ev.get("payload", {})
    if etype == "PushEvent":
        ref = (payload.get("ref") or "").split("/")[-1]
        commits = payload.get("commits", [])
        n = payload.get("size", len(commits))
        head = ""
        if commits:
            msg = commits[-1].get("message", "").split("\n")[0]
            if len(msg) > 60:
                msg = msg[:60] + "\u2026"
            head = get_text(lang, "ev.push_head", msg=msg)
        return get_text(lang, "ev.push", actor=actor, n=n, ref=ref, head=head)
    if etype == "PullRequestEvent":
        action = payload.get("action", "")
        pr = payload.get("pull_request", {})
        num = pr.get("number", "")
        title = pr.get("title", "")
        amap = {
            "opened": get_text(lang, "ev.pr_opened"),
            "closed": get_text(lang, "ev.pr_closed"),
            "reopened": get_text(lang, "ev.pr_reopened"),
        }
        if action == "closed" and pr.get("merged"):
            amap["closed"] = get_text(lang, "ev.pr_merged")
        act = amap.get(action, action)
        return get_text(lang, "ev.pr", actor=actor, action=act, num=num, title=title)
    if etype == "IssuesEvent":
        action = payload.get("action", "")
        iss = payload.get("issue", {})
        amap = {
            "opened": get_text(lang, "ev.issue_opened"),
            "closed": get_text(lang, "ev.issue_closed"),
            "reopened": get_text(lang, "ev.issue_reopened"),
        }
        act = amap.get(action, action)
        return get_text(lang, "ev.issue", actor=actor, action=act, num=iss.get("number", ""), title=iss.get("title", ""))
    if etype == "IssueCommentEvent":
        iss = payload.get("issue", {})
        return get_text(lang, "ev.comment", actor=actor, num=iss.get("number", ""), title=iss.get("title", ""))
    if etype == "ReleaseEvent":
        rel = payload.get("release", {})
        return get_text(lang, "ev.release", actor=actor, tag=rel.get("tag_name", ""))
    if etype == "WatchEvent":
        return get_text(lang, "ev.star", actor=actor)
    if etype == "ForkEvent":
        return get_text(lang, "ev.fork", actor=actor)
    if etype == "CreateEvent":
        return get_text(lang, "ev.create", actor=actor, ref_type=payload.get("ref_type", ""), ref=payload.get("ref", "") or "").rstrip()
    if etype == "DeleteEvent":
        return get_text(lang, "ev.delete", actor=actor, ref_type=payload.get("ref_type", ""), ref=payload.get("ref", "") or "").rstrip()
    if etype == "PullRequestReviewEvent":
        pr = payload.get("pull_request", {})
        return get_text(lang, "ev.review", actor=actor, num=pr.get("number", ""))
    return ""
