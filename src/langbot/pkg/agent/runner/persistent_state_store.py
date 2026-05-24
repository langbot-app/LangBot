"""Persistent state store for AgentRunner protocol state.

This module provides a database-backed state store for event-first Protocol v1.
"""
from __future__ import annotations

import typing
import json
import asyncio
import threading
from datetime import datetime

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import select, delete, update

from langbot_plugin.api.entities.builtin.pipeline import query as pipeline_query

from .descriptor import AgentRunnerDescriptor
from .host_models import AgentEventEnvelope, AgentBinding
from ...entity.persistence.agent_runner_state import AgentRunnerState


# Valid state scopes for agent runner state updates.
VALID_STATE_SCOPES = ('conversation', 'actor', 'subject', 'runner')

# External-facing key aliases accepted from runners.
STATE_KEY_ALIASES = {
    'conversation_id': 'external.conversation_id',
}

# Maximum value_json size (256KB)
MAX_VALUE_JSON_BYTES = 256 * 1024


class PersistentStateStore:
    """Database-backed state store for AgentRunner protocol state.

    IMPORTANT: This is HOST-OWNED protocol state, NOT plugin instance state.

    This store provides:
    1. Persistent storage across runs via database
    2. Scope isolation by runner_id + binding_identity + scope
    3. Policy enforcement (enable_state, state_scopes)
    4. JSON value validation and size limits

    Used by:
    - Event-first Protocol v1 (async methods)
    - State API handlers (get/set/delete/list)
    """

    def __init__(self, db_engine: AsyncEngine):
        self._db_engine = db_engine

    # ========== Scope Key Building (shared with in-memory store) ==========

    def _get_binding_identity(self, binding: AgentBinding) -> str:
        """Get stable binding identity for scope key."""
        if binding.binding_id:
            return binding.binding_id
        scope = binding.scope
        if scope.scope_type and scope.scope_id:
            return f"{scope.scope_type}:{scope.scope_id}"
        return "unknown_binding"

    def _make_conversation_scope_key(
        self,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        descriptor: AgentRunnerDescriptor,
    ) -> str | None:
        """Build conversation scope key from event and binding."""
        if not event.conversation_id:
            return None

        binding_identity = self._get_binding_identity(binding)
        parts = [
            descriptor.id,
            binding_identity,
            event.conversation_id,
        ]
        if event.thread_id:
            parts.append(event.thread_id)
        return f'conversation:{":".join(parts)}'

    def _make_actor_scope_key(
        self,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        descriptor: AgentRunnerDescriptor,
    ) -> str | None:
        """Build actor scope key from event and binding."""
        if not event.actor or not event.actor.actor_id:
            return None

        binding_identity = self._get_binding_identity(binding)
        parts = [
            descriptor.id,
            binding_identity,
            event.actor.actor_type or 'user',
            event.actor.actor_id,
        ]
        return f'actor:{":".join(parts)}'

    def _make_subject_scope_key(
        self,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        descriptor: AgentRunnerDescriptor,
    ) -> str | None:
        """Build subject scope key from event and binding."""
        if not event.subject or not event.subject.subject_id:
            return None

        binding_identity = self._get_binding_identity(binding)
        parts = [
            descriptor.id,
            binding_identity,
            event.subject.subject_type or 'unknown',
            event.subject.subject_id,
        ]
        return f'subject:{":".join(parts)}'

    def _make_runner_scope_key(
        self,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        descriptor: AgentRunnerDescriptor,
    ) -> str:
        """Build runner scope key from event and binding."""
        binding_identity = self._get_binding_identity(binding)
        parts = [
            descriptor.id,
            binding_identity,
        ]
        return f'runner:{":".join(parts)}'

    def _get_scope_key(
        self,
        scope: str,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        descriptor: AgentRunnerDescriptor,
    ) -> str | None:
        """Get scope key for given scope."""
        if scope == 'conversation':
            return self._make_conversation_scope_key(event, binding, descriptor)
        elif scope == 'actor':
            return self._make_actor_scope_key(event, binding, descriptor)
        elif scope == 'subject':
            return self._make_subject_scope_key(event, binding, descriptor)
        elif scope == 'runner':
            return self._make_runner_scope_key(event, binding, descriptor)
        return None

    def _check_scope_enabled(self, scope: str, binding: AgentBinding) -> bool:
        """Check if scope is enabled by binding's state_policy."""
        state_policy = binding.state_policy
        if not state_policy.enable_state:
            return False
        return scope in state_policy.state_scopes

    def _validate_json_value(
        self,
        value: typing.Any,
        logger: typing.Any = None,
    ) -> tuple[str | None, str | None]:
        """Validate and serialize value to JSON.

        Returns:
            Tuple of (json_string, error_message). If error_message is not None,
            json_string will be None.
        """
        try:
            json_str = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            return None, f'Value is not JSON-serializable: {e}'

        # Check size limit
        json_bytes = len(json_str.encode('utf-8'))
        if json_bytes > MAX_VALUE_JSON_BYTES:
            return None, f'Value size {json_bytes} bytes exceeds limit {MAX_VALUE_JSON_BYTES} bytes'

        return json_str, None

    # ========== Async DB Operations ==========

    async def build_snapshot_from_event(
        self,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        descriptor: AgentRunnerDescriptor,
    ) -> dict[str, dict[str, typing.Any]]:
        """Build state snapshot for all scopes from event and binding.

        Reads from database, respects state_policy.
        """
        state_policy = binding.state_policy

        # If state is disabled, return all empty scopes
        if not state_policy.enable_state:
            return {
                'conversation': {},
                'actor': {},
                'subject': {},
                'runner': {},
            }

        snapshot: dict[str, dict[str, typing.Any]] = {
            'conversation': {},
            'actor': {},
            'subject': {},
            'runner': {},
        }

        async with self._db_engine.connect() as conn:
            for scope in VALID_STATE_SCOPES:
                if not self._check_scope_enabled(scope, binding):
                    continue

                scope_key = self._get_scope_key(scope, event, binding, descriptor)
                if not scope_key:
                    continue

                # Query all state entries for this scope_key
                result = await conn.execute(
                    select(AgentRunnerState.state_key, AgentRunnerState.value_json)
                    .where(AgentRunnerState.scope_key == scope_key)
                )
                rows = result.fetchall()

                for row in rows:
                    key = row.state_key
                    value_json = row.value_json
                    if value_json:
                        try:
                            snapshot[scope][key] = json.loads(value_json)
                        except json.JSONDecodeError:
                            pass  # Skip invalid JSON

        # Seed external.conversation_id from event.conversation_id if not set
        if self._check_scope_enabled('conversation', binding) and event.conversation_id:
            if 'external.conversation_id' not in snapshot['conversation']:
                snapshot['conversation']['external.conversation_id'] = event.conversation_id

        return snapshot

    async def apply_update_from_event(
        self,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        descriptor: AgentRunnerDescriptor,
        scope: str,
        key: str,
        value: typing.Any,
        logger: typing.Any = None,
    ) -> tuple[bool, str | None]:
        """Apply a state update from event context.

        Returns:
            Tuple of (success, error_message). If success is False, error_message
            contains the reason.
        """
        state_policy = binding.state_policy

        # Check if state is disabled
        if not state_policy.enable_state:
            return False, 'State is disabled by binding policy'

        # Validate scope
        if scope not in VALID_STATE_SCOPES:
            return False, f'Invalid scope: {scope}'

        # Check if scope is enabled
        if not self._check_scope_enabled(scope, binding):
            return False, f'Scope "{scope}" not enabled by binding policy'

        # Map accepted key aliases
        if key in STATE_KEY_ALIASES:
            key = STATE_KEY_ALIASES[key]

        # Get scope key
        scope_key = self._get_scope_key(scope, event, binding, descriptor)
        if not scope_key:
            return False, f'Missing identity for scope "{scope}"'

        # Validate and serialize value
        value_json, error = self._validate_json_value(value, logger)
        if error:
            return False, error

        # Build context fields
        binding_identity = self._get_binding_identity(binding)

        async with self._db_engine.begin() as conn:
            # Check if entry exists
            result = await conn.execute(
                select(AgentRunnerState.id)
                .where(AgentRunnerState.scope_key == scope_key)
                .where(AgentRunnerState.state_key == key)
            )
            existing = result.first()

            now = datetime.utcnow()

            if existing:
                # Update existing entry
                await conn.execute(
                    update(AgentRunnerState)
                    .where(AgentRunnerState.id == existing.id)
                    .values(
                        value_json=value_json,
                        updated_at=now,
                    )
                )
            else:
                # Insert new entry
                await conn.execute(
                    sqlalchemy.insert(AgentRunnerState).values(
                        runner_id=descriptor.id,
                        binding_identity=binding_identity,
                        scope=scope,
                        scope_key=scope_key,
                        state_key=key,
                        value_json=value_json,
                        bot_id=event.bot_id,
                        workspace_id=event.workspace_id,
                        conversation_id=event.conversation_id,
                        thread_id=event.thread_id,
                        actor_type=event.actor.actor_type if event.actor else None,
                        actor_id=event.actor.actor_id if event.actor else None,
                        subject_type=event.subject.subject_type if event.subject else None,
                        subject_id=event.subject.subject_id if event.subject else None,
                        created_at=now,
                        updated_at=now,
                    )
                )

        return True, None

    async def state_get(
        self,
        scope_key: str,
        state_key: str,
    ) -> typing.Any:
        """Get a single state value by scope_key and state_key.

        Used by State API handlers.
        """
        async with self._db_engine.connect() as conn:
            result = await conn.execute(
                select(AgentRunnerState.value_json)
                .where(AgentRunnerState.scope_key == scope_key)
                .where(AgentRunnerState.state_key == state_key)
            )
            row = result.first()

            if not row or not row.value_json:
                return None

            try:
                return json.loads(row.value_json)
            except json.JSONDecodeError:
                return None

    async def state_set(
        self,
        scope_key: str,
        state_key: str,
        value: typing.Any,
        runner_id: str,
        binding_identity: str,
        scope: str,
        context: dict[str, typing.Any] | None = None,
        logger: typing.Any = None,
    ) -> tuple[bool, str | None]:
        """Set a state value.

        Used by State API handlers.
        Context contains optional fields like bot_id, conversation_id, etc.
        """
        # Validate and serialize value
        value_json, error = self._validate_json_value(value, logger)
        if error:
            return False, error

        context = context or {}

        async with self._db_engine.begin() as conn:
            # Check if entry exists
            result = await conn.execute(
                select(AgentRunnerState.id)
                .where(AgentRunnerState.scope_key == scope_key)
                .where(AgentRunnerState.state_key == state_key)
            )
            existing = result.first()

            now = datetime.utcnow()

            if existing:
                # Update existing entry
                await conn.execute(
                    update(AgentRunnerState)
                    .where(AgentRunnerState.id == existing.id)
                    .values(
                        value_json=value_json,
                        updated_at=now,
                    )
                )
            else:
                # Insert new entry
                await conn.execute(
                    sqlalchemy.insert(AgentRunnerState).values(
                        runner_id=runner_id,
                        binding_identity=binding_identity,
                        scope=scope,
                        scope_key=scope_key,
                        state_key=state_key,
                        value_json=value_json,
                        bot_id=context.get('bot_id'),
                        workspace_id=context.get('workspace_id'),
                        conversation_id=context.get('conversation_id'),
                        thread_id=context.get('thread_id'),
                        actor_type=context.get('actor_type'),
                        actor_id=context.get('actor_id'),
                        subject_type=context.get('subject_type'),
                        subject_id=context.get('subject_id'),
                        created_at=now,
                        updated_at=now,
                    )
                )

        return True, None

    async def state_delete(
        self,
        scope_key: str,
        state_key: str,
    ) -> bool:
        """Delete a state value.

        Returns True if deleted, False if not found.
        """
        async with self._db_engine.begin() as conn:
            result = await conn.execute(
                delete(AgentRunnerState)
                .where(AgentRunnerState.scope_key == scope_key)
                .where(AgentRunnerState.state_key == state_key)
                .returning(AgentRunnerState.id)
            )
            deleted = result.first()
            return deleted is not None

    async def state_list(
        self,
        scope_key: str,
        prefix: str | None = None,
        limit: int = 100,
    ) -> tuple[list[str], bool]:
        """List state keys in a scope.

        Returns tuple of (keys, has_more).
        """
        # Enforce limit cap
        limit = min(limit, 100)

        async with self._db_engine.connect() as conn:
            query = (
                select(AgentRunnerState.state_key)
                .where(AgentRunnerState.scope_key == scope_key)
                .order_by(AgentRunnerState.state_key)
                .limit(limit + 1)  # Fetch one extra to check has_more
            )

            if prefix:
                query = query.where(
                    AgentRunnerState.state_key.like(f'{prefix}%')
                )

            result = await conn.execute(query)
            rows = result.fetchall()

            keys = [row.state_key for row in rows[:limit]]
            has_more = len(rows) > limit

            return keys, has_more

    async def clear_all(self) -> None:
        """Clear all state entries (for testing)."""
        async with self._db_engine.begin() as conn:
            await conn.execute(delete(AgentRunnerState))


# Global singleton persistent state store
_persistent_state_store: PersistentStateStore | None = None
_persistent_state_store_lock = threading.Lock()


def get_persistent_state_store(db_engine: AsyncEngine | None = None) -> PersistentStateStore:
    """Get the global persistent state store singleton.

    Args:
        db_engine: Database engine (required on first call)

    Returns:
        PersistentStateStore singleton
    """
    global _persistent_state_store
    with _persistent_state_store_lock:
        if _persistent_state_store is None:
            if db_engine is None:
                raise RuntimeError("db_engine required for first call to get_persistent_state_store")
            _persistent_state_store = PersistentStateStore(db_engine)
        return _persistent_state_store


def reset_persistent_state_store() -> None:
    """Reset the global persistent state store (for testing)."""
    global _persistent_state_store
    with _persistent_state_store_lock:
        _persistent_state_store = None
