from __future__ import annotations

import asyncio
import copy
import json
import os
from datetime import datetime, timezone, timedelta

from langbot_plugin.api.definition.plugin import BasePlugin

STATE_KEY = "daily_limit_state"

# Process-cache slot used when no installation binding is available (dedicated
# placement). It maps to the legacy storage key so existing dedicated installs
# keep reading their own rows.
DEDICATED_SCOPE = "dedicated"

# Written by the SDK worker launcher. A shared worker must always carry a trusted
# invocation binding; without one it must refuse to touch tenant state instead of
# falling back to a binding-less scope shared by every installation.
RUNTIME_PROFILE_ENV = "LANGBOT_PLUGIN_RUNTIME_PROFILE"

DEFAULT_LIMIT_MESSAGE = "您今天的对话次数已达上限，请明天再来吧~"


def installation_scope(binding) -> str:
    """Return the stable scope token for one installation binding.

    Only the installation identity triple is used. ``runtime_revision`` changes on
    every worker upgrade, so including it would orphan the tenant's persisted rows
    after a restart of the loader.
    """

    return f"{binding.instance_uuid}:{binding.workspace_uuid}:{binding.installation_uuid}"


def storage_key(scope: str) -> str:
    """Return the plugin-storage key for one scope.

    Host rows are keyed by ``[instance, workspace, owner_type, owner, key]`` with no
    installation dimension, so the installation scope has to live in the plugin's
    own key. The binding-less dedicated scope keeps the legacy key unchanged.
    """

    if scope == DEDICATED_SCOPE:
        return STATE_KEY
    return f"{STATE_KEY}:{scope}"


class _InstallationState:
    """Process-local state belonging to exactly one installation binding.

    The same object graph serves every installation of the artifact, so this is
    cached per binding and dropped in ``on_installation_revoked``.
    """

    __slots__ = ("scope", "settings", "sessions", "lock", "loaded")

    def __init__(self, scope: str) -> None:
        self.scope = scope
        self.settings: dict = {}
        self.sessions: dict = {}
        self.lock = asyncio.Lock()
        self.loaded = False


class DailyLimitPlugin(BasePlugin):
    """Daily conversation limit per session.

    Tracks per-session daily usage, supports per-session limit overrides,
    a global default limit for new sessions, manual reset, silent mode and
    timezone-aware daily rollover. State is kept per installation binding and
    persisted via plugin storage, so the management Page component (which shares
    the plugin object) sees the state of the installation that invoked it.

    State shape (persisted JSON, one row per installation scope):

        {
          "settings": {
            "default_limit": 50,
            "limit_message": "...",
            "silent_mode": false,
            "tz_offset": 8,
            "reset_hour": 0
          },
          "sessions": {
            "<session_id>": {
              "label": "person:12345",
              "limit": null,          # null = use default_limit; int = override
              "count": 3,
              "date": "2026-06-20",   # logical day the count belongs to
              "last_active": "2026-06-20T11:20:00+08:00"
            }
          }
        }

    The row lives under ``daily_limit_state:<instance>:<workspace>:<installation>``
    (or the legacy ``daily_limit_state`` for dedicated, binding-less workers).
    """

    def __init__(self):
        super().__init__()
        self._states: dict[str, _InstallationState] = {}

    # ----------------------------------------------------------------- lifecycle

    async def initialize(self) -> None:
        """Process-wide initialization only.

        Under shared placement this runs once per worker with an empty config and
        no installation context, so tenant state is loaded lazily per invocation
        (and per binding) instead.
        """

        return None

    async def on_installation_revoked(self, binding) -> None:
        """Drop the cache of the revoked installation; no Host API is available."""

        self._states.pop(installation_scope(binding), None)

    async def destroy(self) -> None:
        self._states.clear()

    # --------------------------------------------------------------- state scope

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

    async def _state(self) -> _InstallationState:
        """Return the invoking installation's state, loading it on first use."""

        scope = self._current_scope()
        st = self._states.get(scope)
        if st is None:
            st = _InstallationState(scope)
            self._states[scope] = st
        if not st.loaded:
            async with st.lock:
                if not st.loaded:
                    await self._load(st)
                    st.loaded = True
        return st

    async def _load(self, st: _InstallationState) -> None:
        loaded = None
        try:
            raw = await self.get_plugin_storage(storage_key(st.scope))
            if raw:
                loaded = json.loads(raw.decode("utf-8"))
        except Exception as e:
            print(f"[DailyLimit] No saved state for {st.scope} ({e}); seeding from config", flush=True)

        cfg = self.get_config() or {}
        seed = {
            "default_limit": int(cfg.get("daily_limit", 50)),
            "limit_message": cfg.get("limit_message") or DEFAULT_LIMIT_MESSAGE,
            "silent_mode": bool(cfg.get("silent_mode", False)),
            "tz_offset": int(cfg.get("reset_timezone_offset", 8)),
            "reset_hour": int(cfg.get("reset_hour", 0)),
        }

        if loaded and isinstance(loaded, dict):
            st.settings = {**seed, **(loaded.get("settings") or {})}
            st.sessions = loaded.get("sessions") or {}
        else:
            st.settings = seed
            st.sessions = {}
        self._normalize_settings(st.settings)
        print(
            f"[DailyLimit] initialized scope={st.scope}: "
            f"default_limit={st.settings['default_limit']}, "
            f"{len(st.sessions)} tracked sessions",
            flush=True,
        )

    # ------------------------------------------------------------------- helpers

    def _normalize_settings(self, settings: dict) -> None:
        settings["default_limit"] = max(0, int(settings.get("default_limit", 50)))
        settings["tz_offset"] = max(-12, min(14, int(settings.get("tz_offset", 8))))
        settings["reset_hour"] = max(0, min(23, int(settings.get("reset_hour", 0))))
        settings["silent_mode"] = bool(settings.get("silent_mode", False))
        if not settings.get("limit_message"):
            settings["limit_message"] = DEFAULT_LIMIT_MESSAGE

    def _logical_today(self, st: _InstallationState) -> str:
        tz = timezone(timedelta(hours=st.settings["tz_offset"]))
        now_local = datetime.now(tz)
        if now_local.hour < st.settings["reset_hour"]:
            now_local -= timedelta(days=1)
        return now_local.strftime("%Y-%m-%d")

    def _now_iso(self, st: _InstallationState) -> str:
        tz = timezone(timedelta(hours=st.settings["tz_offset"]))
        return datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S%z")

    def _effective_limit(self, st: _InstallationState, sess: dict) -> int:
        override = sess.get("limit")
        if override is None:
            return st.settings["default_limit"]
        return int(override)

    async def persist(self, st: _InstallationState) -> None:
        await self.set_plugin_storage(
            storage_key(st.scope),
            json.dumps(
                {"settings": st.settings, "sessions": st.sessions},
                ensure_ascii=False,
            ).encode("utf-8"),
        )

    async def _transaction(self, mutate, *, rollback: bool = True):
        """Apply one state change of one installation under its installation lock.

        Read, modify, serialize and await the Host write inside the same critical
        section. ``persist`` overwrites the whole row, so two overlapping writers
        of one installation must not interleave: an admin write that serialized an
        older snapshot would otherwise be able to land after a newer one and roll
        it back. Holding the lock across the Host call makes the durable row match
        call order; nothing is ever serialized from state that another writer has
        already moved past.

        ``mutate`` returns ``(changed, result)``; ``result`` is what this method
        returns. With ``rollback`` the in-memory state is restored when the
        mutation raises, the write fails or the call is cancelled, so memory stays
        equal to the last snapshot that actually landed instead of diverging from
        a write that never happened.

        The counter path opts out of ``rollback`` on purpose: a message that was
        already answered keeps consuming quota (never back-credits usage), and the
        next successful write persists the whole snapshot again.
        """

        st = await self._state()
        async with st.lock:
            before = (copy.deepcopy(st.settings), copy.deepcopy(st.sessions)) if rollback else None
            try:
                changed, result = mutate(st)
                if changed:
                    await self.persist(st)
            except BaseException:
                if before is not None:
                    st.settings, st.sessions = before
                raise
            return result

    # --------------------------------------------------------- runtime (listener)

    async def check_and_count(self, session_id: str, label: str) -> tuple[bool, str]:
        """Check the session against its limit and increment if allowed.

        Returns ``(allowed, message)``. When ``allowed`` is False and the
        message is non-empty, the listener should reply with it; an empty
        message means "block silently".
        """

        def count(st: _InstallationState) -> tuple[bool, tuple[bool, str]]:
            today = self._logical_today(st)
            sess = st.sessions.get(session_id)
            if sess is None:
                sess = {"label": label, "limit": None, "count": 0, "date": today}
                st.sessions[session_id] = sess

            # Roll over the day if needed
            if sess.get("date") != today:
                sess["date"] = today
                sess["count"] = 0
            sess["label"] = label
            sess["last_active"] = self._now_iso(st)

            limit = self._effective_limit(st, sess)

            # 0 means unlimited
            if limit <= 0:
                sess["count"] = int(sess.get("count", 0)) + 1
                return True, (True, "")

            if int(sess.get("count", 0)) >= limit:
                if st.settings.get("silent_mode"):
                    return True, (False, "")
                return True, (False, st.settings.get("limit_message") or DEFAULT_LIMIT_MESSAGE)

            sess["count"] = int(sess.get("count", 0)) + 1
            return True, (True, "")

        return await self._transaction(count, rollback=False)

    # ----------------------------------------------------------- management (page)

    async def snapshot(self) -> dict:
        """Return a JSON-serializable view of the invoking installation's state."""
        st = await self._state()
        async with st.lock:
            today = self._logical_today(st)
            rows = []
            for sid, sess in st.sessions.items():
                count = int(sess.get("count", 0)) if sess.get("date") == today else 0
                rows.append(
                    {
                        "id": sid,
                        "label": sess.get("label", sid),
                        "limit": sess.get("limit"),
                        "effective_limit": self._effective_limit(st, sess),
                        "count": count,
                        "date": sess.get("date"),
                        "last_active": sess.get("last_active"),
                    }
                )
            rows.sort(key=lambda r: (r.get("last_active") or ""), reverse=True)
            return {
                "settings": dict(st.settings),
                "today": today,
                "sessions": rows,
            }

    async def update_settings(self, patch: dict) -> None:
        allowed = {"default_limit", "limit_message", "silent_mode", "tz_offset", "reset_hour"}

        def apply(st: _InstallationState) -> tuple[bool, None]:
            candidate = dict(st.settings)
            for k, v in (patch or {}).items():
                if k in allowed and v is not None:
                    candidate[k] = v
            # Validate on the copy first, then swap: a rejected value must not
            # leave a half-updated settings dict behind.
            self._normalize_settings(candidate)
            st.settings = candidate
            return True, None

        await self._transaction(apply)

    async def set_session_limit(self, session_id: str, limit) -> bool:
        def apply(st: _InstallationState) -> tuple[bool, bool]:
            sess = st.sessions.get(session_id)
            if sess is None:
                return False, False
            if limit is None or limit == "":
                sess["limit"] = None
            else:
                sess["limit"] = max(0, int(limit))
            return True, True

        return await self._transaction(apply)

    async def reset_session(self, session_id: str) -> bool:
        def apply(st: _InstallationState) -> tuple[bool, bool]:
            sess = st.sessions.get(session_id)
            if sess is None:
                return False, False
            sess["count"] = 0
            sess["date"] = self._logical_today(st)
            return True, True

        return await self._transaction(apply)

    async def reset_all(self) -> int:
        def apply(st: _InstallationState) -> tuple[bool, int]:
            today = self._logical_today(st)
            for sess in st.sessions.values():
                sess["count"] = 0
                sess["date"] = today
            return True, len(st.sessions)

        return await self._transaction(apply)

    async def delete_session(self, session_id: str) -> bool:
        def apply(st: _InstallationState) -> tuple[bool, bool]:
            if session_id not in st.sessions:
                return False, False
            del st.sessions[session_id]
            return True, True

        return await self._transaction(apply)
