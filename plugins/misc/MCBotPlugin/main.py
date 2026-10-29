from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import time
from typing import Any

from langbot_plugin.api.definition.plugin import BasePlugin

logger = logging.getLogger("MCBotPlugin")

# Plugin storage keys. The Host row key is [instance, workspace, owner, key] and
# carries no installation dimension, so per-installation state is written under
# ``<key>:<installation scope>``. Dedicated placement (an invocation without an
# installation binding) keeps the legacy unscoped key so existing data survives.
BINDINGS_KEY = "mcbot_bindings"  # {group_key: "addr:port"}
RECORDS_KEY = "mcbot_records"    # [{"server","players","duration","ts"}, ...]

# Keep at most 14 days of online records to bound storage growth
RECORD_RETENTION_SECONDS = 14 * 24 * 60 * 60

# Scope used when the active invocation carries no installation binding.
LEGACY_SCOPE = ""

# Bounded wait for a revoked installation's tracker to observe cancellation.
TRACK_STOP_TIMEOUT = 5.0

# Delay before the first tracker sample, so the invoking request settles.
TRACK_STARTUP_DELAY = 10


def _start_detached(coro: Any) -> asyncio.Task:
    """Start tenant work with a context of its own.

    A task created inside an invocation inherits that invocation's authority,
    which is revoked as soon as the invocation returns — every Host call it
    makes afterwards then fails with "Plugin invocation has ended". The tracker
    therefore runs in a fresh context and holds no invocation authority at all:
    it may only touch process-local, installation-keyed state, and every Host
    call happens later, inside an invocation of the same installation.
    """
    return contextvars.Context().run(asyncio.create_task, coro)


class MCBotPlugin(BasePlugin):
    """Minecraft server helper plugin.

    Binds a Minecraft server to a chat group, reports live server status and
    online players, and tracks per-player online time via a background poller.

    Migrated from the legacy QChatGPT/LangBot plugin: MongoDB storage is
    replaced by the built-in plugin key-value storage, and the synchronous
    `mctools` ping plus thread-based routine are replaced by async `mcstatus`
    and an asyncio background task.
    """

    def __init__(self):
        super().__init__()
        # Installation-keyed process state. One object graph serves every
        # installation of this artifact digest, so nothing tenant-bearing may be
        # a plain instance attribute or a module global. Entries are released in
        # on_installation_revoked().
        self._states: dict[str, dict[str, Any]] = {}
        self._state_locks: dict[str, asyncio.Lock] = {}
        self._track_tasks: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def initialize(self) -> None:
        # Process-scoped only: no host config, no client, no tenant state. The
        # per-installation bindings/records are loaded lazily from the storage of
        # the binding's own key during that binding's first invocation.
        logger.info("[MCBot] initialized")

    async def on_installation_revoked(self, binding) -> None:
        """Drop one installation's caches and stop its tracking task.

        Runs without an invocation context, so only process-local state is
        touched. The Host row created under this binding's storage key is owned
        by the Host installation and is left for the Host to reclaim.
        """
        scope = self._scope(binding)
        await self._stop_tracker(scope)
        self._states.pop(scope, None)
        self._state_locks.pop(scope, None)

    def __del__(self):
        for task in list(getattr(self, "_track_tasks", {}).values()):
            if not task.done():
                task.cancel()

    # ------------------------------------------------------------------ #
    # Installation scoping
    # ------------------------------------------------------------------ #
    def _scope(self, binding: Any | None = None) -> str:
        """Return this invocation's installation scope.

        The full binding (instance, workspace, installation) is used so two
        Workspaces that happen to reuse an installation UUID never share a cache
        or a storage row. Only the installation identity matters: a worker
        upgrade revokes the superseded binding, and the successor must keep
        reading the same playtime history.
        """
        if binding is None:
            binding = self.get_installation_binding()
        if binding is None:
            return LEGACY_SCOPE
        return f"{binding.instance_uuid}:{binding.workspace_uuid}:{binding.installation_uuid}"

    @staticmethod
    def _storage_key(base: str, scope: str) -> str:
        return f"{base}:{scope}" if scope else base

    # ------------------------------------------------------------------ #
    # Storage helpers
    # ------------------------------------------------------------------ #
    async def _state(self, scope: str) -> dict[str, Any]:
        """Load (once) the bindings/records cache owned by one installation."""
        state = self._states.get(scope)
        if state is not None:
            return state

        lock = self._state_locks.setdefault(scope, asyncio.Lock())
        async with lock:
            state = self._states.get(scope)
            if state is None:
                state = {
                    "bindings": await self._load_json(
                        self._storage_key(BINDINGS_KEY, scope), default={}
                    ),
                    "records": await self._load_json(
                        self._storage_key(RECORDS_KEY, scope), default=[]
                    ),
                    "records_dirty": False,
                }
                self._states[scope] = state
            return state

    async def _flush(self, scope: str, state: dict[str, Any]) -> None:
        """Persist records the detached tracker appended since the last flush.

        The tracker performs no Host call, so its samples are written by the
        next invocation of the same installation, which owns the authority for
        this installation's storage row. A failed write keeps the flag set so
        the next invocation retries with the still-current in-memory records.
        """
        if not state.get("records_dirty"):
            return
        state["records_dirty"] = not await self._save_records(scope, state)

    async def _load_json(self, key: str, default: Any) -> Any:
        try:
            raw = await self.get_plugin_storage(key)
            if not raw:
                return default
            return json.loads(raw.decode("utf-8"))
        except Exception:
            # Missing key / version mismatch — start fresh.
            return default

    async def _save_bindings(self, scope: str, state: dict[str, Any]) -> None:
        try:
            data = json.dumps(state["bindings"], ensure_ascii=False).encode("utf-8")
            await self.set_plugin_storage(self._storage_key(BINDINGS_KEY, scope), data)
        except Exception as e:
            logger.error("[MCBot] failed to persist bindings: %s", e)

    async def _save_records(self, scope: str, state: dict[str, Any]) -> bool:
        try:
            data = json.dumps(state["records"], ensure_ascii=False).encode("utf-8")
            await self.set_plugin_storage(self._storage_key(RECORDS_KEY, scope), data)
            return True
        except Exception as e:
            logger.error("[MCBot] failed to persist records: %s", e)
            return False

    # ------------------------------------------------------------------ #
    # Binding management (used by commands)
    # ------------------------------------------------------------------ #
    @staticmethod
    def group_key(launcher_type: str, launcher_id: str | int) -> str:
        return f"{launcher_type}_{launcher_id}"

    async def bind_server(self, group_key: str, server_addr: str) -> None:
        scope = self._scope()
        state = await self._state(scope)
        await self._flush(scope, state)
        state["bindings"][group_key] = server_addr
        await self._save_bindings(scope, state)
        self._ensure_tracker(scope, state)

    async def unbind_server(self, group_key: str) -> bool:
        scope = self._scope()
        state = await self._state(scope)
        await self._flush(scope, state)
        if group_key not in state["bindings"]:
            return False
        del state["bindings"][group_key]
        await self._save_bindings(scope, state)
        return True

    async def get_bound_server(self, group_key: str) -> str | None:
        scope = self._scope()
        state = await self._state(scope)
        await self._flush(scope, state)
        self._ensure_tracker(scope, state)
        return state["bindings"].get(group_key)

    # ------------------------------------------------------------------ #
    # Minecraft server ping (async, via mcstatus)
    # ------------------------------------------------------------------ #
    def _ping_timeout(self) -> float:
        try:
            return float(self.get_config().get("ping_timeout", 10))
        except Exception:
            return 10.0

    async def ping_server(
        self, server_addr: str, timeout: float | None = None
    ) -> dict[str, Any]:
        """Ping a Minecraft Java server and return normalized status info.

        Returns a dict: {"motd": str, "version": str, "online": int,
        "max": int, "players": [name, ...]}. Raises on failure.
        """
        from mcstatus import JavaServer

        if timeout is None:
            # Inside an invocation, so the tenant's own config is used.
            timeout = self._ping_timeout()
        server = await JavaServer.async_lookup(server_addr, timeout=timeout)
        status = await server.async_status()

        sample = []
        if status.players.sample:
            sample = [p.name for p in status.players.sample]

        # MOTD: prefer plain text rendering across mcstatus versions.
        motd = ""
        try:
            motd = status.motd.to_plain()
        except Exception:
            try:
                motd = status.description if isinstance(status.description, str) else ""
            except Exception:
                motd = ""

        return {
            "motd": motd,
            "version": status.version.name,
            "online": status.players.online,
            "max": status.players.max,
            "players": sample,
        }

    # ------------------------------------------------------------------ #
    # Playtime tracking
    # ------------------------------------------------------------------ #
    def _track_interval(self) -> int:
        try:
            return max(15, int(self.get_config().get("track_interval", 60)))
        except Exception:
            return 60

    def _ensure_tracker(self, scope: str, state: dict[str, Any]) -> None:
        """Start (or restart) one installation's background tracker.

        Called from an invocation of that installation, so the sampling interval
        and ping timeout are read from the invocation config while it is still
        active and handed to the task. A config revision revokes the binding and
        its task, and the successor binding reads config again; the loop itself
        never touches invocation-scoped APIs and runs in a fresh context.
        """
        if not state["bindings"]:
            return
        task = self._track_tasks.get(scope)
        if task is not None and not task.done():
            return
        self._track_tasks[scope] = _start_detached(
            self._track_loop(scope, self._track_interval(), self._ping_timeout())
        )

    async def _stop_tracker(self, scope: str) -> None:
        task = self._track_tasks.pop(scope, None)
        if task is None:
            return
        task.cancel()
        done, _pending = await asyncio.wait({task}, timeout=TRACK_STOP_TIMEOUT)
        if not done:
            logger.warning(
                "[MCBot] tracker for installation scope %s did not stop in %ss",
                scope,
                TRACK_STOP_TIMEOUT,
            )

    async def _track_loop(self, scope: str, interval: int, timeout: float) -> None:
        """Background task: periodically ping all bound servers and record
        which players were online, to build playtime statistics.

        Runs in a fresh context (see ``_start_detached``): it makes no Host call,
        so persistence is deferred to the next invocation of this installation.
        """
        # Small startup delay so the invoking request fully settles.
        await asyncio.sleep(TRACK_STARTUP_DELAY)
        while True:
            try:
                await self._track_once(scope, interval, timeout)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("[MCBot] track loop error: %s", e)
            await asyncio.sleep(interval)

    async def _track_once(self, scope: str, duration: int, timeout: float) -> None:
        state = self._states.get(scope)
        if state is None:
            # The installation was revoked while this sample was pending.
            return
        servers = sorted(set(state["bindings"].values()))
        if not servers:
            return

        changed = False
        now = time.time()
        for server_addr in servers:
            try:
                info = await self.ping_server(server_addr, timeout=timeout)
            except Exception:
                # Server offline / unreachable — skip this cycle.
                continue
            players = info["players"]
            if players:
                state["records"].append({
                    "server": server_addr,
                    "players": players,
                    "duration": duration,
                    "ts": now,
                })
                changed = True

        # Trim old records.
        cutoff = now - RECORD_RETENTION_SECONDS
        before = len(state["records"])
        state["records"] = [r for r in state["records"] if r.get("ts", 0) >= cutoff]
        if len(state["records"]) != before:
            changed = True

        if changed:
            # Persistence needs an invocation's authority; the next invocation
            # of this installation flushes the flag through _flush().
            state["records_dirty"] = True

    async def count_playtime(
        self, server_addr: str, period_minutes: int
    ) -> list[tuple[str, int]]:
        """Aggregate per-player online seconds for a server over the last
        `period_minutes`. Returns a list of (player, seconds) sorted desc."""
        scope = self._scope()
        state = await self._state(scope)
        await self._flush(scope, state)
        self._ensure_tracker(scope, state)

        cutoff = time.time() - period_minutes * 60
        totals: dict[str, int] = {}
        for rec in state["records"]:
            if rec.get("server") != server_addr:
                continue
            if rec.get("ts", 0) < cutoff:
                continue
            duration = rec.get("duration", 0)
            for player in rec.get("players", []):
                totals[player] = totals.get(player, 0) + duration
        return sorted(totals.items(), key=lambda x: x[1], reverse=True)
