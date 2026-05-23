"""Runner scoped state store for managing AgentRunner state across runs."""
from __future__ import annotations

import typing
import threading

from langbot_plugin.api.entities.builtin.pipeline import query as pipeline_query

from .descriptor import AgentRunnerDescriptor
from .host_models import AgentEventEnvelope


# Valid state scopes for agent runner state updates.
VALID_STATE_SCOPES = ('conversation', 'actor', 'subject', 'runner')

# Key mapping for backward compatibility
LEGACY_KEY_MAPPING = {
    'conversation_id': 'external.conversation_id',
}


class RunnerScopedStateStore:
    """In-memory scoped state store for AgentRunner protocol state.

    IMPORTANT: This is HOST-OWNED protocol state, NOT plugin instance state.

    Key Design Principles:
    1. Host-owned: State is owned and managed by LangBot host, not by the plugin.
       The plugin can only read/write through agent runner state updates.
    2. Scope keys based on stable host identity: Uses host-controlled identifiers
       (runner_id, bot_uuid, pipeline_uuid, launcher_type, launcher_id) rather
       than external/unstable identifiers like external conversation id.
    3. External conversation id is a VALUE: The runner can update external.conversation_id
       in state, which syncs to conversation.uuid. The scope key remains stable,
       preventing state loss when conversation identity changes.

    State scopes:
    - conversation: runner_id + bot_uuid + pipeline_uuid + launcher_type + launcher_id + conversation identity
    - actor: runner_id + bot_uuid + sender_id
    - subject: runner_id + bot_uuid + launcher_type + launcher_id
    - runner: runner_id + pipeline_uuid

    This ensures different runners don't share state and same runner
    has appropriate isolation per scope.

    Note: This is an in-memory store. State only persists within the
    current process lifetime. For production use, a persistent storage
    backend should be implemented.
    """

    def __init__(self):
        # Use thread-safe dict for concurrent access
        self._store: dict[str, dict[str, typing.Any]] = {}
        self._lock = threading.Lock()

    def _make_conversation_scope_key(
        self,
        query: pipeline_query.Query,
        descriptor: AgentRunnerDescriptor,
    ) -> str:
        """Build conversation scope identity key.

        Uses host-owned stable identity, NOT external conversation id.
        External conversation id is a state VALUE, not part of state KEY.

        This prevents state loss when runner updates external.conversation_id:
        - First run: scope key uses stable identity, state saved
        - Runner returns external.conversation_id, synced to conversation.uuid
        - Next run: scope key still uses same stable identity, state accessible
        """
        parts = [
            descriptor.id,
            query.bot_uuid or 'unknown_bot',
            query.pipeline_uuid or 'unknown_pipeline',
        ]

        if query.session:
            parts.append(query.session.launcher_type.value)
            parts.append(query.session.launcher_id)

            # Use stable conversation identity (NOT external uuid)
            # Options:
            # 1. conversation.create_time if available (stable host-owned)
            # 2. Use "conversation" literal as stable identity within launcher scope
            #    (assumes one active conversation per launcher context)
            # We use option 2 for simplicity - conversation state is scoped to
            # launcher (person/group) + bot + pipeline + runner
            # External conversation id is just a VALUE inside this scope
            conv_create_time = getattr(query.session.using_conversation, 'create_time', None)
            if conv_create_time:
                # Use create_time as stable identity if available
                parts.append(str(conv_create_time))
            # else: no additional part - launcher scope identity is sufficient

        return f'conversation:{":".join(parts)}'

    def _make_actor_scope_key(
        self,
        query: pipeline_query.Query,
        descriptor: AgentRunnerDescriptor,
    ) -> str:
        """Build actor scope identity key."""
        parts = [
            descriptor.id,
            query.bot_uuid or 'unknown_bot',
            str(query.sender_id) if query.sender_id else 'unknown_sender',
        ]

        return f'actor:{":".join(parts)}'

    def _make_subject_scope_key(
        self,
        query: pipeline_query.Query,
        descriptor: AgentRunnerDescriptor,
    ) -> str:
        """Build subject scope identity key."""
        parts = [
            descriptor.id,
            query.bot_uuid or 'unknown_bot',
        ]

        if query.session:
            parts.append(query.session.launcher_type.value)
            parts.append(query.session.launcher_id)

        return f'subject:{":".join(parts)}'

    def _make_runner_scope_key(
        self,
        query: pipeline_query.Query,
        descriptor: AgentRunnerDescriptor,
    ) -> str:
        """Build runner scope identity key."""
        parts = [
            descriptor.id,
            query.pipeline_uuid or 'unknown_pipeline',
        ]

        return f'runner:{":".join(parts)}'

    def _get_scope_key(
        self,
        scope: str,
        query: pipeline_query.Query,
        descriptor: AgentRunnerDescriptor,
    ) -> str:
        """Get the storage key for a given scope."""
        if scope == 'conversation':
            return self._make_conversation_scope_key(query, descriptor)
        elif scope == 'actor':
            return self._make_actor_scope_key(query, descriptor)
        elif scope == 'subject':
            return self._make_subject_scope_key(query, descriptor)
        elif scope == 'runner':
            return self._make_runner_scope_key(query, descriptor)
        else:
            raise ValueError(f'Invalid scope: {scope}')

    def build_snapshot(
        self,
        query: pipeline_query.Query,
        descriptor: AgentRunnerDescriptor,
    ) -> dict[str, dict[str, typing.Any]]:
        """Build state snapshot for all scopes.

        Args:
            query: Pipeline query
            descriptor: Runner descriptor

        Returns:
            Dict with 4 scope keys, each containing scope state dict
        """
        snapshot: dict[str, dict[str, typing.Any]] = {
            'conversation': {},
            'actor': {},
            'subject': {},
            'runner': {},
        }

        with self._lock:
            for scope in VALID_STATE_SCOPES:
                scope_key = self._get_scope_key(scope, query, descriptor)
                scope_state = self._store.get(scope_key, {})
                snapshot[scope] = dict(scope_state)  # Copy to avoid mutation

        # Seed external.conversation_id from existing conversation uuid
        if query.session and query.session.using_conversation:
            conv_uuid = getattr(query.session.using_conversation, 'uuid', None)
            if conv_uuid and 'external.conversation_id' not in snapshot['conversation']:
                snapshot['conversation']['external.conversation_id'] = conv_uuid

        return snapshot

    def apply_update(
        self,
        query: pipeline_query.Query,
        descriptor: AgentRunnerDescriptor,
        scope: str,
        key: str,
        value: typing.Any,
        logger: typing.Any = None,
    ) -> bool:
        """Apply a state update to the store.

        Args:
            query: Pipeline query
            descriptor: Runner descriptor
            scope: State scope (conversation, actor, subject, runner)
            key: State key (should use namespace prefix like external.*)
            value: State value (must be JSON-serializable)
            logger: Optional logger for warnings

        Returns:
            True if update applied successfully, False if invalid scope

        Side effects:
            - Updates internal store
            - Syncs external.conversation_id to query.session.using_conversation.uuid
        """
        # Validate scope
        if scope not in VALID_STATE_SCOPES:
            if logger:
                logger.warning(
                    f'Runner {descriptor.id} state.updated with invalid scope: {scope}. '
                    f'Valid scopes: {", ".join(VALID_STATE_SCOPES)}'
                )
            return False

        # Map legacy key names
        if key in LEGACY_KEY_MAPPING:
            mapped_key = LEGACY_KEY_MAPPING[key]
            if logger:
                logger.debug(
                    f'Runner {descriptor.id} state.updated legacy key "{key}" mapped to "{mapped_key}"'
                )
            key = mapped_key

        # Apply update to store
        with self._lock:
            scope_key = self._get_scope_key(scope, query, descriptor)
            if scope_key not in self._store:
                self._store[scope_key] = {}
            self._store[scope_key][key] = value

        # Sync external.conversation_id to query.session.using_conversation.uuid
        if scope == 'conversation' and key == 'external.conversation_id':
            if query.session and query.session.using_conversation:
                # Update conversation uuid for backward compatibility
                # This ensures old conversation continuation behavior works
                setattr(query.session.using_conversation, 'uuid', value)
                if logger:
                    logger.debug(
                        f'Synced external.conversation_id "{value}" to conversation.uuid'
                    )

        return True

    def clear_scope(
        self,
        scope: str,
        query: pipeline_query.Query,
        descriptor: AgentRunnerDescriptor,
    ) -> None:
        """Clear all state for a specific scope.

        Args:
            scope: State scope to clear
            query: Pipeline query
            descriptor: Runner descriptor
        """
        with self._lock:
            scope_key = self._get_scope_key(scope, query, descriptor)
            if scope_key in self._store:
                del self._store[scope_key]

    def clear_all(self) -> None:
        """Clear all stored state (for testing/reset)."""
        with self._lock:
            self._store.clear()

    # ========== Event-first Protocol v1 methods ==========

    def _get_binding_identity(
        self,
        binding: "AgentBinding",
    ) -> str:
        """Get stable binding identity for scope key.

        Uses binding_id if available, falls back to scope_type + scope_id.
        """
        if binding.binding_id:
            return binding.binding_id

        # Fallback to scope identity
        scope = binding.scope
        if scope.scope_type and scope.scope_id:
            return f"{scope.scope_type}:{scope.scope_id}"

        # Last resort - should not happen in production
        return "unknown_binding"

    def _make_conversation_scope_key_from_event(
        self,
        event: AgentEventEnvelope,
        binding: "AgentBinding",
        descriptor: AgentRunnerDescriptor,
    ) -> str | None:
        """Build conversation scope identity key from event and binding.

        Scope key structure: runner_id + binding_id + conversation_id
        This ensures state is isolated per binding and per conversation.

        Returns None if conversation_id is missing.
        """
        if not event.conversation_id:
            return None

        binding_identity = self._get_binding_identity(binding)

        parts = [
            descriptor.id,
            binding_identity,
            event.conversation_id,
        ]

        # Include thread_id if present for thread-scoped state
        if event.thread_id:
            parts.append(event.thread_id)

        return f'conversation:{":".join(parts)}'

    def _make_actor_scope_key_from_event(
        self,
        event: AgentEventEnvelope,
        binding: "AgentBinding",
        descriptor: AgentRunnerDescriptor,
    ) -> str | None:
        """Build actor scope identity key from event and binding.

        Scope key structure: runner_id + binding_id + actor_type + actor_id
        This ensures state is isolated per binding and per actor.

        Returns None if actor_id is missing.
        """
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

    def _make_subject_scope_key_from_event(
        self,
        event: AgentEventEnvelope,
        binding: "AgentBinding",
        descriptor: AgentRunnerDescriptor,
    ) -> str | None:
        """Build subject scope identity key from event and binding.

        Scope key structure: runner_id + binding_id + subject_type + subject_id
        This ensures state is isolated per binding and per subject.

        Returns None if subject_id is missing.
        """
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

    def _make_runner_scope_key_from_event(
        self,
        event: AgentEventEnvelope,
        binding: "AgentBinding",
        descriptor: AgentRunnerDescriptor,
    ) -> str:
        """Build runner scope identity key from event and binding.

        Scope key structure: runner_id + binding_id
        This ensures state is isolated per binding (not shared across bindings).
        """
        binding_identity = self._get_binding_identity(binding)

        parts = [
            descriptor.id,
            binding_identity,
        ]

        return f'runner:{":".join(parts)}'

    def _get_scope_key_from_event(
        self,
        scope: str,
        event: AgentEventEnvelope,
        binding: "AgentBinding",
        descriptor: AgentRunnerDescriptor,
    ) -> str | None:
        """Get the storage key for a given scope from event and binding.

        Returns None if required identity is missing for the scope.
        """
        if scope == 'conversation':
            return self._make_conversation_scope_key_from_event(event, binding, descriptor)
        elif scope == 'actor':
            return self._make_actor_scope_key_from_event(event, binding, descriptor)
        elif scope == 'subject':
            return self._make_subject_scope_key_from_event(event, binding, descriptor)
        elif scope == 'runner':
            return self._make_runner_scope_key_from_event(event, binding, descriptor)
        else:
            return None

    def _check_scope_enabled(
        self,
        scope: str,
        binding: "AgentBinding",
    ) -> bool:
        """Check if a scope is enabled by binding's state_policy.

        Args:
            scope: Scope to check
            binding: Agent binding with state_policy

        Returns:
            True if scope is enabled, False otherwise
        """
        state_policy = binding.state_policy

        # Check if state is disabled entirely
        if not state_policy.enable_state:
            return False

        # Check if scope is in enabled scopes
        return scope in state_policy.state_scopes

    def build_snapshot_from_event(
        self,
        event: AgentEventEnvelope,
        binding: "AgentBinding",
        descriptor: AgentRunnerDescriptor,
    ) -> dict[str, dict[str, typing.Any]]:
        """Build state snapshot for all scopes from event and binding.

        Respects binding.state_policy:
        - If enable_state is False, returns all empty scopes.
        - If a scope is not in state_scopes, returns empty dict for that scope.

        Args:
            event: Event envelope
            binding: Agent binding configuration
            descriptor: Runner descriptor

        Returns:
            Dict with 4 scope keys, each containing scope state dict.
            Scopes without required identity or disabled by policy will have empty dict.
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

        with self._lock:
            for scope in VALID_STATE_SCOPES:
                # Check if scope is enabled by policy
                if not self._check_scope_enabled(scope, binding):
                    continue

                scope_key = self._get_scope_key_from_event(scope, event, binding, descriptor)
                if scope_key:
                    scope_state = self._store.get(scope_key, {})
                    snapshot[scope] = dict(scope_state)  # Copy to avoid mutation

        # Seed external.conversation_id from event.conversation_id if not already set
        # Only if conversation scope is enabled
        if self._check_scope_enabled('conversation', binding) and event.conversation_id:
            if 'external.conversation_id' not in snapshot['conversation']:
                snapshot['conversation']['external.conversation_id'] = event.conversation_id

        return snapshot

    def apply_update_from_event(
        self,
        event: AgentEventEnvelope,
        binding: "AgentBinding",
        descriptor: AgentRunnerDescriptor,
        scope: str,
        key: str,
        value: typing.Any,
        logger: typing.Any = None,
    ) -> bool:
        """Apply a state update to the store from event and binding context.

        Respects binding.state_policy:
        - If enable_state is False, rejects the update.
        - If scope is not in state_scopes, rejects the update.

        Args:
            event: Event envelope
            binding: Agent binding configuration
            descriptor: Runner descriptor
            scope: State scope (conversation, actor, subject, runner)
            key: State key (should use namespace prefix like external.*)
            value: State value (must be JSON-serializable)
            logger: Optional logger for warnings

        Returns:
            True if update applied successfully, False if invalid scope,
            missing identity, or disabled by policy
        """
        state_policy = binding.state_policy

        # Check if state is disabled entirely
        if not state_policy.enable_state:
            if logger:
                logger.warning(
                    f'Runner {descriptor.id} state.updated rejected: '
                    f'state is disabled by binding policy'
                )
            return False

        # Validate scope
        if scope not in VALID_STATE_SCOPES:
            if logger:
                logger.warning(
                    f'Runner {descriptor.id} state.updated with invalid scope: {scope}. '
                    f'Valid scopes: {", ".join(VALID_STATE_SCOPES)}'
                )
            return False

        # Check if scope is enabled by policy
        if not self._check_scope_enabled(scope, binding):
            if logger:
                logger.warning(
                    f'Runner {descriptor.id} state.updated rejected for scope "{scope}": '
                    f'scope not enabled by binding policy. Enabled scopes: {state_policy.state_scopes}'
                )
            return False

        # Map legacy key names
        if key in LEGACY_KEY_MAPPING:
            mapped_key = LEGACY_KEY_MAPPING[key]
            if logger:
                logger.debug(
                    f'Runner {descriptor.id} state.updated legacy key "{key}" mapped to "{mapped_key}"'
                )
            key = mapped_key

        # Get scope key from event and binding
        scope_key = self._get_scope_key_from_event(scope, event, binding, descriptor)
        if scope_key is None:
            if logger:
                logger.warning(
                    f'Runner {descriptor.id} state.updated for scope "{scope}" '
                    f'requires missing identity (conversation_id, actor_id, or subject_id). '
                    f'Skipping update.'
                )
            return False

        # Apply update to store
        with self._lock:
            if scope_key not in self._store:
                self._store[scope_key] = {}
            self._store[scope_key][key] = value

        if logger:
            logger.debug(
                f'Runner {descriptor.id} state.updated: scope={scope}, key={key}'
            )

        return True


# Global singleton state store
_state_store: RunnerScopedStateStore | None = None
_state_store_lock = threading.Lock()


def get_state_store() -> RunnerScopedStateStore:
    """Get the global state store singleton."""
    global _state_store
    with _state_store_lock:
        if _state_store is None:
            _state_store = RunnerScopedStateStore()
        return _state_store


def reset_state_store() -> None:
    """Reset the global state store (for testing)."""
    global _state_store
    with _state_store_lock:
        _state_store = None
