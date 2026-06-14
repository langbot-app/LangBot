"""Agent run session registry for proxy action permission validation."""
from __future__ import annotations

import asyncio
import copy
import typing
import time
import threading

from .context_builder import AgentResources


MAX_STEERING_QUEUE_ITEMS = 100

DEFAULT_RESOURCE_OPERATIONS: dict[str, set[str]] = {
    'model': {'invoke', 'stream', 'rerank'},
    'tool': {'detail', 'call'},
    'knowledge_base': {'list', 'retrieve'},
    'file': {'config', 'knowledge'},
    'skill': {'activate'},
}


class AgentRunSessionStatus(typing.TypedDict):
    """Status tracking for agent run session."""
    started_at: int
    last_activity_at: int


class RunAuthorizationSnapshot(typing.TypedDict):
    """Frozen authorization data for one active run.

    ResourceBuilder creates the authorized resource list once before runner
    execution. Runtime proxy handlers must validate against this run-scoped
    snapshot instead of recomputing resource policy.
    """

    resources: AgentResources
    available_apis: dict[str, bool]
    conversation_id: str | None
    bot_id: str | None
    workspace_id: str | None
    thread_id: str | None
    state_policy: dict[str, typing.Any]
    state_context: dict[str, typing.Any]
    authorized_ids: dict[str, set[str]]
    authorized_operations: dict[str, dict[str, set[str]]]


SteeringQueueItem = dict[str, typing.Any]


class AgentRunSession(typing.TypedDict):
    """Session for an active agent runner execution.

    Stored in AgentRunSessionRegistry for proxy action permission validation.

    Fields:
        run_id: Unique run identifier (UUID from AgentRunContext)
        runner_id: Runner descriptor ID (plugin:author/name/runner)
        query_id: Host entry query ID, only present for query-based adapters
        plugin_identity: Plugin identifier (author/name) of the runner
        authorization: Run-scoped authorization snapshot; runtime auth truth
        status: Session status tracking
    """
    run_id: str
    runner_id: str
    query_id: int | None
    plugin_identity: str  # author/name
    authorization: RunAuthorizationSnapshot
    status: AgentRunSessionStatus
    steering_queue: list[SteeringQueueItem]


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
        conversation_id: str | None = None,
        bot_id: str | None = None,
        workspace_id: str | None = None,
        thread_id: str | None = None,
        available_apis: dict[str, bool] | None = None,
        state_policy: dict[str, typing.Any] | None = None,
        state_context: dict[str, typing.Any] | None = None,
    ) -> None:
        """Register a new agent run session.

        Args:
            run_id: Unique run identifier
            runner_id: Runner descriptor ID
            query_id: Host entry query ID, only present for query-based adapters
            plugin_identity: Plugin identifier (author/name)
            resources: Authorized resources for this run
            conversation_id: Conversation ID for history/event access
            bot_id: Bot UUID for history/event access
            workspace_id: Workspace ID for history/event access
            thread_id: Thread ID for history/event access
            available_apis: Run-scoped pull APIs exposed in AgentRunContext
            state_policy: State policy from binding (enable_state, state_scopes)
            state_context: Context for state API (scope_keys, binding_identity, etc.)
        """
        if not isinstance(plugin_identity, str) or not plugin_identity.strip():
            raise ValueError('plugin_identity is required for agent run sessions')

        now = int(time.time())

        available_apis = copy.deepcopy(available_apis or {})

        # Normalize state_policy to defaults if None
        if state_policy is None:
            state_policy = {'enable_state': True, 'state_scopes': ['conversation', 'actor']}

        # Normalize state_context to empty dict if None
        state_context = state_context or {}

        resources_snapshot = copy.deepcopy(resources)
        authorization: RunAuthorizationSnapshot = {
            'resources': resources_snapshot,
            'available_apis': available_apis,
            'conversation_id': conversation_id,
            'bot_id': bot_id,
            'workspace_id': workspace_id,
            'thread_id': thread_id,
            'state_policy': copy.deepcopy(state_policy),
            'state_context': copy.deepcopy(state_context),
            'authorized_ids': self._build_authorized_ids(resources_snapshot),
            'authorized_operations': self._build_authorized_operations(resources_snapshot),
        }

        session: AgentRunSession = {
            'run_id': run_id,
            'runner_id': runner_id,
            'query_id': query_id,
            'plugin_identity': plugin_identity,
            'authorization': authorization,
            'status': {
                'started_at': now,
                'last_activity_at': now,
            },
            'steering_queue': [],
        }

        async with self._lock:
            self._sessions[run_id] = session

    def _build_authorized_ids(self, resources: AgentResources) -> dict[str, set[str]]:
        """Pre-compute authorized resource IDs for O(1) lookup."""
        return {
            'model': {m.get('model_id') for m in resources.get('models', [])},
            'tool': {t.get('tool_name') for t in resources.get('tools', [])},
            'knowledge_base': {kb.get('kb_id') for kb in resources.get('knowledge_bases', [])},
            'skill': {s.get('skill_name') for s in resources.get('skills', [])},
            'file': {f.get('file_id') for f in resources.get('files', [])},
        }

    def _build_authorized_operations(
        self,
        resources: AgentResources,
    ) -> dict[str, dict[str, set[str]]]:
        """Pre-compute resource operations for runtime action validation."""
        return {
            'model': {
                m.get('model_id'): self._resource_operations('model', m)
                for m in resources.get('models', [])
                if m.get('model_id')
            },
            'tool': {
                t.get('tool_name'): self._resource_operations('tool', t)
                for t in resources.get('tools', [])
                if t.get('tool_name')
            },
            'knowledge_base': {
                kb.get('kb_id'): self._resource_operations('knowledge_base', kb)
                for kb in resources.get('knowledge_bases', [])
                if kb.get('kb_id')
            },
            'skill': {
                s.get('skill_name'): self._resource_operations('skill', s)
                for s in resources.get('skills', [])
                if s.get('skill_name')
            },
            'file': {
                f.get('file_id'): self._resource_operations('file', f)
                for f in resources.get('files', [])
                if f.get('file_id')
            },
        }

    @staticmethod
    def _resource_operations(resource_type: str, resource: dict[str, typing.Any]) -> set[str]:
        """Return explicit operations or the compatibility default for old resources."""
        operations = resource.get('operations')
        if isinstance(operations, list) and operations:
            return {str(operation) for operation in operations}
        return set(DEFAULT_RESOURCE_OPERATIONS.get(resource_type, set()))

    async def unregister(self, run_id: str) -> AgentRunSession | None:
        """Unregister an agent run session.

        Args:
            run_id: Unique run identifier

        Returns:
            The removed session, if one existed. Callers can inspect any
            pending in-memory queues before they are discarded.
        """
        async with self._lock:
            return self._sessions.pop(run_id, None)

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

    async def find_steering_target(
        self,
        *,
        conversation_id: str,
        runner_id: str,
        bot_id: str | None = None,
        workspace_id: str | None = None,
        thread_id: str | None = None,
    ) -> str | None:
        """Find the oldest active run that can accept steering for a conversation."""
        async with self._lock:
            candidates: list[tuple[int, str]] = []
            for run_id, session in self._sessions.items():
                authorization = session['authorization']
                if session.get('runner_id') != runner_id:
                    continue
                if authorization.get('conversation_id') != conversation_id:
                    continue
                if authorization.get('bot_id') != bot_id:
                    continue
                if authorization.get('workspace_id') != workspace_id:
                    continue
                if authorization.get('thread_id') != thread_id:
                    continue
                if not authorization.get('available_apis', {}).get('steering_pull', False):
                    continue
                candidates.append((session['status'].get('started_at', 0), run_id))

            if not candidates:
                return None

            candidates.sort(key=lambda item: item[0])
            return candidates[0][1]

    async def enqueue_steering(
        self,
        run_id: str,
        item: SteeringQueueItem,
    ) -> bool:
        """Append one steering item to an active run queue."""
        async with self._lock:
            session = self._sessions.get(run_id)
            if session is None:
                return False
            if len(session['steering_queue']) >= MAX_STEERING_QUEUE_ITEMS:
                return False
            session['steering_queue'].append(copy.deepcopy(item))
            session['status']['last_activity_at'] = int(time.time())
            return True

    async def pull_steering(
        self,
        run_id: str,
        *,
        mode: str = 'all',
        limit: int | None = None,
    ) -> list[SteeringQueueItem]:
        """Pop pending steering items from a run queue."""
        async with self._lock:
            session = self._sessions.get(run_id)
            if session is None:
                return []

            queue = session['steering_queue']
            if not queue:
                return []

            normalized_mode = str(mode or 'all').lower()
            if normalized_mode in {'one', 'one-at-a-time', 'one_at_a_time'}:
                count = 1
            elif isinstance(limit, int) and limit > 0:
                count = min(limit, len(queue))
            else:
                count = len(queue)

            count = max(0, min(count, len(queue), 100))
            items = [copy.deepcopy(item) for item in queue[:count]]
            del queue[:count]
            session['status']['last_activity_at'] = int(time.time())
            return items

    def is_resource_allowed(
        self,
        session: AgentRunSession,
        resource_type: str,
        resource_id: str,
        operation: str | None = None,
    ) -> bool:
        """Check if resource access is allowed for this session.

        Uses pre-computed authorized IDs for O(1) lookup.

        Args:
            session: AgentRunSession to check
            resource_type: Resource type ('model', 'tool', 'knowledge_base', 'storage', 'file')
            resource_id: Resource identifier (model_id, tool_name, kb_id, 'plugin'/'workspace', file_key)
            operation: Optional operation to check within the authorized resource

        Returns:
            True if resource is authorized, False otherwise
        """
        authorization = session['authorization']
        authorized_ids = authorization['authorized_ids']
        resources = authorization['resources']

        if resource_type in ('model', 'tool', 'knowledge_base', 'skill', 'file'):
            if resource_id not in authorized_ids.get(resource_type, set()):
                return False
            if operation is None:
                return True
            operation_map = authorization.get('authorized_operations', {})
            operations = operation_map.get(resource_type, {}).get(resource_id)
            if not operations:
                operations = DEFAULT_RESOURCE_OPERATIONS.get(resource_type, set())
            return operation in operations

        if resource_type == 'storage':
            storage = resources.get('storage', {})
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
