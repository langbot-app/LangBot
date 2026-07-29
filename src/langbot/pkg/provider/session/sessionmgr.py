from __future__ import annotations

import asyncio
import dataclasses
import heapq
import time

from langbot_plugin.api.entities.builtin.provider import message as provider_message, prompt as provider_prompt
import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

from ...api.http.context import ExecutionContext
from ...core import app
from ...pipeline.pool import (
    ExecutionContextMismatchError,
    ExecutionContextRequiredError,
    bind_execution_context,
    get_query_execution_context,
)

SessionKey = tuple[
    str,
    str,
    int,
    str,
    str,
    int | str,
]
SessionExpiryEntry = tuple[float, int, SessionKey]

_SESSION_EXPIRY_HEAP_MIN_LIMIT = 64
_SESSION_EXPIRY_HEAP_ACTIVE_MULTIPLIER = 4


def _query_session_key(query: pipeline_query.Query) -> tuple[SessionKey, ExecutionContext]:
    execution_context = get_query_execution_context(query)
    bot_uuid = getattr(query, 'bot_uuid', None)
    if not isinstance(bot_uuid, str) or not bot_uuid.strip():
        raise ExecutionContextRequiredError('Query.bot_uuid is required for session lookup')

    execution_context = bind_execution_context(execution_context, bot_uuid=bot_uuid)
    key: SessionKey = (
        execution_context.instance_uuid,
        execution_context.workspace_uuid,
        execution_context.placement_generation,
        bot_uuid,
        query.launcher_type.value,
        query.launcher_id,
    )
    return key, execution_context


class SessionManager:
    """会话管理器"""

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap
        self._legacy_sessions: list[provider_session.Session] = []
        self._session_index: dict[SessionKey, provider_session.Session] = {}
        self._session_keys_by_workspace: dict[str, set[SessionKey]] = {}
        self._session_expiry_heap: list[SessionExpiryEntry] = []
        self._next_access_revision = 0

    @property
    def session_list(self) -> list[provider_session.Session]:
        """Compatibility view for API services that enumerate sessions."""

        return [
            *self._legacy_sessions,
            *self._session_index.values(),
        ]

    @session_list.setter
    def session_list(self, sessions: list[provider_session.Session]) -> None:
        """Replace the cache while keeping the O(1) index consistent."""

        session_values = list(sessions)
        self._legacy_sessions = []
        self._session_index = {}
        self._session_keys_by_workspace = {}
        self._session_expiry_heap = []
        self._next_access_revision = 0
        now = time.monotonic()
        for session in session_values:
            key = getattr(session, '_langbot_session_key', None)
            if isinstance(key, tuple) and len(key) == 6:
                self._session_index[key] = session
                self._session_keys_by_workspace.setdefault(key[1], set()).add(key)
                last_accessed = getattr(session, '_langbot_last_accessed', None)
                if last_accessed is None:
                    last_accessed = now
                self._touch_session(
                    session,
                    key,
                    float(last_accessed),
                    compact=False,
                )
            else:
                self._legacy_sessions.append(session)
        self._compact_session_expiry_heap(force=True)

    def _retention_config(self) -> dict:
        instance_config = getattr(getattr(self.ap, 'instance_config', None), 'data', {})
        if not isinstance(instance_config, dict):
            return {}
        config = instance_config.get('system', {}).get('session_retention', {})
        return config if isinstance(config, dict) else {}

    def _positive_config_int(self, name: str, default: int) -> int:
        try:
            value = int(self._retention_config().get(name, default))
        except (TypeError, ValueError):
            value = default
        return max(value, 1)

    @staticmethod
    def _session_is_idle(session: provider_session.Session) -> bool:
        semaphore = getattr(session, '_semaphore', None)
        concurrency = getattr(session, '_langbot_session_concurrency', None)
        if semaphore is None or not isinstance(concurrency, int):
            return True
        return getattr(semaphore, '_value', -1) == concurrency

    def _remove_session(self, session: provider_session.Session) -> None:
        key = getattr(session, '_langbot_session_key', None)
        if isinstance(key, tuple) and len(key) == 6 and self._session_index.get(key) is session:
            self._session_index.pop(key, None)
            workspace_keys = self._session_keys_by_workspace.get(key[1])
            if workspace_keys is not None:
                workspace_keys.discard(key)
                if not workspace_keys:
                    self._session_keys_by_workspace.pop(key[1], None)
        else:
            try:
                self._legacy_sessions.remove(session)
            except ValueError:
                pass

    def _touch_session(
        self,
        session: provider_session.Session,
        key: SessionKey,
        now: float,
        *,
        compact: bool = True,
    ) -> None:
        self._next_access_revision += 1
        revision = self._next_access_revision
        object.__setattr__(session, '_langbot_last_accessed', now)
        object.__setattr__(session, '_langbot_access_revision', revision)
        heapq.heappush(
            self._session_expiry_heap,
            (now, revision, key),
        )
        if compact:
            self._compact_session_expiry_heap()

    def _compact_session_expiry_heap(self, *, force: bool = False) -> None:
        limit = max(
            len(self._session_index) * _SESSION_EXPIRY_HEAP_ACTIVE_MULTIPLIER,
            _SESSION_EXPIRY_HEAP_MIN_LIMIT,
        )
        if not force and len(self._session_expiry_heap) <= limit:
            return
        self._session_expiry_heap = [
            (
                float(getattr(session, '_langbot_last_accessed', 0.0)),
                int(getattr(session, '_langbot_access_revision', 0)),
                key,
            )
            for key, session in self._session_index.items()
        ]
        heapq.heapify(self._session_expiry_heap)

    def _pop_current_expiry_entry(
        self,
    ) -> tuple[float, int, SessionKey, provider_session.Session] | None:
        while self._session_expiry_heap:
            last_accessed, revision, key = heapq.heappop(self._session_expiry_heap)
            session = self._session_index.get(key)
            if session is None:
                continue
            if getattr(session, '_langbot_access_revision', None) != revision:
                continue
            return last_accessed, revision, key, session
        return None

    def _prune_expired_sessions(self, now: float) -> None:
        idle_ttl = self._positive_config_int('idle_ttl_seconds', 86400)
        cutoff = now - idle_ttl
        while self._session_expiry_heap:
            last_accessed, _, _ = self._session_expiry_heap[0]
            if last_accessed > cutoff:
                break
            current = self._pop_current_expiry_entry()
            if current is None:
                break
            last_accessed, revision, key, session = current
            if last_accessed > cutoff:
                heapq.heappush(
                    self._session_expiry_heap,
                    (last_accessed, revision, key),
                )
                break
            if self._session_is_idle(session):
                self._remove_session(session)
                continue
            # The session became active without another cache lookup. Give it
            # a fresh TTL instead of repeatedly examining the same expired
            # entry or losing its future expiry record.
            self._touch_session(session, key, now)

    def _prune_workspace_capacity(
        self,
        workspace_uuid: str,
        max_entries_per_workspace: int,
    ) -> None:
        workspace_keys = self._session_keys_by_workspace.get(workspace_uuid, set())
        overflow = len(workspace_keys) - max_entries_per_workspace + 1
        if overflow <= 0:
            return
        idle_workspace_sessions = sorted(
            (
                session
                for key in tuple(workspace_keys)
                if (session := self._session_index.get(key)) is not None and self._session_is_idle(session)
            ),
            key=lambda session: float(getattr(session, '_langbot_last_accessed', 0.0)),
        )
        for session in idle_workspace_sessions[:overflow]:
            self._remove_session(session)

    def _evict_oldest_idle_session(self, now: float) -> bool:
        # At most one current entry per active session is examined. Stale heap
        # revisions do not count and are discarded in O(log N).
        current_probes = 0
        max_probes = len(self._session_index)
        while current_probes < max_probes:
            current = self._pop_current_expiry_entry()
            if current is None:
                return False
            _, _, key, session = current
            current_probes += 1
            if self._session_is_idle(session):
                self._remove_session(session)
                return True
            self._touch_session(session, key, now)
        return False

    def _prune_sessions(self, now: float, workspace_uuid: str) -> None:
        self._prune_expired_sessions(now)
        max_entries_per_workspace = self._positive_config_int('max_entries_per_workspace', 200)
        self._prune_workspace_capacity(
            workspace_uuid,
            max_entries_per_workspace,
        )

        max_entries = self._positive_config_int('max_entries', 2000)
        overflow = len(self._session_index) - max_entries + 1
        if overflow <= 0:
            return
        for _ in range(overflow):
            if not self._evict_oldest_idle_session(now):
                break

    async def initialize(self):
        pass

    async def get_session(self, query: pipeline_query.Query) -> provider_session.Session:
        """获取会话"""
        session_key, execution_context = _query_session_key(query)
        now = time.monotonic()
        session = self._session_index.get(session_key)
        if session is not None:
            self._touch_session(session, session_key, now)
            return session

        self._prune_sessions(now, execution_context.workspace_uuid)
        max_entries_per_workspace = self._positive_config_int('max_entries_per_workspace', 200)
        workspace_entries = len(
            self._session_keys_by_workspace.get(
                execution_context.workspace_uuid,
                (),
            )
        )
        if workspace_entries >= max_entries_per_workspace:
            raise RuntimeError(f'Workspace session cache capacity reached ({max_entries_per_workspace})')
        max_entries = self._positive_config_int('max_entries', 2000)
        if len(self._session_index) >= max_entries:
            raise RuntimeError(f'Session cache capacity reached ({max_entries})')

        session_concurrency = self.ap.instance_config.data['concurrency']['session']

        session = provider_session.Session(
            instance_uuid=execution_context.instance_uuid,
            workspace_uuid=execution_context.workspace_uuid,
            placement_generation=execution_context.placement_generation,
            bot_uuid=query.bot_uuid,
            launcher_type=query.launcher_type,
            launcher_id=query.launcher_id,
            sender_id=query.sender_id,
        )
        session_context = dataclasses.replace(
            execution_context,
            pipeline_uuid=None,
            query_uuid=None,
        )
        # langbot-plugin 0.4.13 ignores Workspace fields. Preserve them until
        # the Workspace-aware SDK becomes the minimum supported version.
        object.__setattr__(session, 'instance_uuid', session_context.instance_uuid)
        object.__setattr__(session, 'workspace_uuid', session_context.workspace_uuid)
        object.__setattr__(
            session,
            'placement_generation',
            session_context.placement_generation,
        )
        object.__setattr__(session, 'bot_uuid', query.bot_uuid)
        object.__setattr__(session, '_execution_context', session_context)
        object.__setattr__(session, '_langbot_session_key', session_key)
        object.__setattr__(session, '_langbot_session_concurrency', session_concurrency)
        session._semaphore = asyncio.Semaphore(session_concurrency)
        self._session_index[session_key] = session
        self._session_keys_by_workspace.setdefault(
            execution_context.workspace_uuid,
            set(),
        ).add(session_key)
        self._touch_session(session, session_key, now)
        return session

    async def get_conversation(
        self,
        query: pipeline_query.Query,
        session: provider_session.Session,
        prompt_config: list[dict],
        pipeline_uuid: str,
        bot_uuid: str,
    ) -> provider_session.Conversation:
        """获取对话或创建对话"""

        session_key, execution_context = _query_session_key(query)
        if getattr(session, '_langbot_session_key', None) != session_key:
            raise ExecutionContextMismatchError('Session does not belong to the Query execution scope')
        execution_context = bind_execution_context(
            execution_context,
            bot_uuid=bot_uuid,
            pipeline_uuid=pipeline_uuid,
        )
        if execution_context.bot_uuid != getattr(session, 'bot_uuid', None):
            raise ExecutionContextMismatchError('Session bot_uuid does not match the Query execution scope')

        if not session.conversations:
            session.conversations = []

        # set prompt
        prompt_messages = []

        for prompt_message in prompt_config:
            prompt_messages.append(provider_message.Message(**prompt_message))

        prompt = provider_prompt.Prompt(
            name='default',
            messages=prompt_messages,
        )

        if (
            session.using_conversation is None
            or session.using_conversation.pipeline_uuid != pipeline_uuid
            or session.using_conversation.bot_uuid != bot_uuid
        ):
            conversation = provider_session.Conversation(
                prompt=prompt,
                messages=[],
                pipeline_uuid=pipeline_uuid,
                bot_uuid=bot_uuid,
            )
            session.conversations.append(conversation)
            max_conversations = self._positive_config_int('max_conversations_per_session', 20)
            if len(session.conversations) > max_conversations:
                del session.conversations[:-max_conversations]
            session.using_conversation = conversation

        return session.using_conversation

    def trim_conversation_messages(
        self,
        conversation: provider_session.Conversation,
        *,
        max_rounds: int,
    ) -> None:
        """Bound retained process-local history after a completed turn."""

        try:
            max_rounds = int(max_rounds)
        except (TypeError, ValueError):
            max_rounds = 10
        max_rounds = max(max_rounds, 1)
        max_messages = self._positive_config_int('max_messages_per_conversation', 100)

        kept_reversed = []
        user_rounds = 0
        for message in reversed(conversation.messages):
            if user_rounds >= max_rounds:
                break
            kept_reversed.append(message)
            if getattr(message, 'role', None) == 'user':
                user_rounds += 1
        retained = list(reversed(kept_reversed))[-max_messages:]
        # Binary payloads are needed for the current model call, but retaining
        # them in process-local history makes a few image/file turns consume
        # hundreds of MB. Historical URL and text references remain intact.
        for message in retained:
            content = getattr(message, 'content', None)
            if not isinstance(content, list):
                continue
            for element in content:
                if getattr(element, 'image_base64', None) is not None:
                    element.image_base64 = None
                if getattr(element, 'file_base64', None) is not None:
                    element.file_base64 = None
        conversation.messages = retained
