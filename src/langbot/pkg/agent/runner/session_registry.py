"""Agent run session registry for proxy action permission validation."""
from __future__ import annotations

import asyncio
import typing
import time
import threading

from .context_builder import AgentResources


class AgentRunSessionStatus(typing.TypedDict):
    """Status tracking for agent run session."""
    started_at: int
    last_activity_at: int


class AgentRunSession(typing.TypedDict):
    """Session for an active agent runner execution.

    Stored in AgentRunSessionRegistry for proxy action permission validation.

    Fields:
        run_id: Unique run identifier (UUID from AgentRunContext)
        runner_id: Runner descriptor ID (plugin:author/name/runner)
        query_id: Pipeline query ID
        plugin_identity: Plugin identifier (author/name) of the runner
        resources: Authorized resources for this run (from AgentResources)
        status: Session status tracking
        _authorized_ids: Pre-computed authorized resource IDs for O(1) lookup
    """
    run_id: str
    runner_id: str
    query_id: int | None
    plugin_identity: str  # author/name
    resources: AgentResources
    status: AgentRunSessionStatus
    _authorized_ids: dict[str, set[str]]  # Pre-computed sets for O(1) lookup


class AgentRunSessionRegistry:
    """Registry for active agent run sessions.

    Host-owned registry for tracking active AgentRunner executions.
    Used by proxy actions in handler.py to validate resource access.

    Key: run_id (UUID from AgentRunContext)
    Value: AgentRunSession with authorized resources

    Thread-safe via asyncio.Lock.
    """

    _sessions: dict[str, AgentRunSession]
    _lock: asyncio.Lock

    def __init__(self):
        self._sessions = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        run_id: str,
        runner_id: str,
        query_id: int | None,
        plugin_identity: str,
        resources: AgentResources,
    ) -> None:
        """Register a new agent run session.

        Args:
            run_id: Unique run identifier
            runner_id: Runner descriptor ID
            query_id: Pipeline query ID
            plugin_identity: Plugin identifier (author/name)
            resources: Authorized resources for this run
        """
        now = int(time.time())

        # Pre-compute authorized resource IDs for O(1) lookup
        authorized_ids: dict[str, set[str]] = {
            'model': {m.get('model_id') for m in resources.get('models', [])},
            'tool': {t.get('tool_name') for t in resources.get('tools', [])},
            'knowledge_base': {kb.get('kb_id') for kb in resources.get('knowledge_bases', [])},
        }

        session: AgentRunSession = {
            'run_id': run_id,
            'runner_id': runner_id,
            'query_id': query_id,
            'plugin_identity': plugin_identity,
            'resources': resources,
            'status': {
                'started_at': now,
                'last_activity_at': now,
            },
            '_authorized_ids': authorized_ids,
        }

        async with self._lock:
            self._sessions[run_id] = session

    async def unregister(self, run_id: str) -> None:
        """Unregister an agent run session.

        Args:
            run_id: Unique run identifier
        """
        async with self._lock:
            if run_id in self._sessions:
                del self._sessions[run_id]

    async def get(self, run_id: str) -> AgentRunSession | None:
        """Get session by run_id.

        Args:
            run_id: Unique run identifier

        Returns:
            AgentRunSession if found, None otherwise
        """
        async with self._lock:
            return self._sessions.get(run_id)

    async def update_activity(self, run_id: str) -> None:
        """Update last activity timestamp for session.

        Args:
            run_id: Unique run identifier
        """
        async with self._lock:
            if run_id in self._sessions:
                self._sessions[run_id]['status']['last_activity_at'] = int(time.time())

    def is_resource_allowed(
        self,
        session: AgentRunSession,
        resource_type: str,
        resource_id: str,
    ) -> bool:
        """Check if resource access is allowed for this session.

        Uses pre-computed authorized IDs for O(1) lookup.

        Args:
            session: AgentRunSession to check
            resource_type: Resource type ('model', 'tool', 'knowledge_base', 'storage')
            resource_id: Resource identifier (model_id, tool_name, kb_id)

        Returns:
            True if resource is authorized, False otherwise
        """
        authorized_ids = session.get('_authorized_ids', {})

        if resource_type in ('model', 'tool', 'knowledge_base'):
            return resource_id in authorized_ids.get(resource_type, set())

        if resource_type == 'storage':
            storage = session['resources'].get('storage', {})
            if resource_id == 'plugin':
                return storage.get('plugin_storage', False)
            elif resource_id == 'workspace':
                return storage.get('workspace_storage', False)
            return False

        return False

    async def list_active_runs(self) -> list[AgentRunSession]:
        """List all active run sessions.

        Returns:
            List of active AgentRunSession dicts
        """
        async with self._lock:
            return list(self._sessions.values())

    async def cleanup_stale_sessions(self, max_age_seconds: int = 3600) -> int:
        """Cleanup sessions that have been inactive for too long.

        Args:
            max_age_seconds: Maximum inactivity time in seconds (default 1 hour)

        Returns:
            Number of sessions cleaned up
        """
        now = int(time.time())
        cleaned = 0

        async with self._lock:
            stale_run_ids = []
            for run_id, session in self._sessions.items():
                last_activity = session['status'].get('last_activity_at', 0)
                if now - last_activity > max_age_seconds:
                    stale_run_ids.append(run_id)

            for run_id in stale_run_ids:
                del self._sessions[run_id]
                cleaned += 1

        return cleaned


# Global registry instance (singleton)
_global_registry: AgentRunSessionRegistry | None = None
_global_registry_lock = threading.Lock()


def get_session_registry() -> AgentRunSessionRegistry:
    """Get global session registry instance (thread-safe singleton).

    Returns:
        AgentRunSessionRegistry singleton
    """
    global _global_registry
    with _global_registry_lock:
        if _global_registry is None:
            _global_registry = AgentRunSessionRegistry()
        return _global_registry