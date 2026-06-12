"""State scope key helpers for AgentRunner host-owned state."""
from __future__ import annotations

import hashlib
import json
import typing

from .descriptor import AgentRunnerDescriptor
from .host_models import AgentBinding, AgentEventEnvelope


VALID_STATE_SCOPES = ('conversation', 'actor', 'subject', 'runner')

STATE_KEY_ALIASES = {
    'conversation_id': 'external.conversation_id',
}


def normalize_state_key(key: str) -> str:
    """Map accepted public aliases to protocol state keys."""
    return STATE_KEY_ALIASES.get(key, key)


def get_binding_identity(binding: AgentBinding) -> str:
    """Return the stable binding identity used for state isolation."""
    if binding.binding_id:
        return binding.binding_id

    scope = binding.scope
    if scope.scope_type and scope.scope_id:
        return f'{scope.scope_type}:{scope.scope_id}'

    return 'unknown_binding'


def _scope_hash(scope: str, parts: dict[str, typing.Any]) -> str:
    """Encode state scope dimensions without separator ambiguity."""
    payload = {
        'version': 2,
        'scope': scope,
        **parts,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return f'{scope}:v2:{hashlib.sha256(raw.encode("utf-8")).hexdigest()}'


def _base_scope_parts(
    event: AgentEventEnvelope,
    binding: AgentBinding,
    descriptor: AgentRunnerDescriptor,
) -> dict[str, typing.Any]:
    return {
        'runner_id': descriptor.id,
        'binding_identity': get_binding_identity(binding),
        'bot_id': event.bot_id,
        'workspace_id': event.workspace_id,
    }


def build_state_scope_key(
    scope: str,
    event: AgentEventEnvelope,
    binding: AgentBinding,
    descriptor: AgentRunnerDescriptor,
) -> str | None:
    """Build the storage key for one state scope.

    Returns None when the event lacks the identity required by that scope.
    """
    base_parts = _base_scope_parts(event, binding, descriptor)

    if scope == 'conversation':
        if not event.conversation_id:
            return None
        return _scope_hash(scope, {
            **base_parts,
            'conversation_id': event.conversation_id,
            'thread_id': event.thread_id,
        })

    if scope == 'actor':
        if not event.actor or not event.actor.actor_id:
            return None
        return _scope_hash(scope, {
            **base_parts,
            'actor_type': event.actor.actor_type or 'user',
            'actor_id': event.actor.actor_id,
        })

    if scope == 'subject':
        if not event.subject or not event.subject.subject_id:
            return None
        return _scope_hash(scope, {
            **base_parts,
            'subject_type': event.subject.subject_type or 'unknown',
            'subject_id': event.subject.subject_id,
        })

    if scope == 'runner':
        return _scope_hash(scope, base_parts)

    return None


def build_state_scope_keys(
    event: AgentEventEnvelope,
    binding: AgentBinding,
    descriptor: AgentRunnerDescriptor,
) -> dict[str, str]:
    """Build all available scope keys for an event/binding pair."""
    scope_keys: dict[str, str] = {}
    for scope in VALID_STATE_SCOPES:
        scope_key = build_state_scope_key(scope, event, binding, descriptor)
        if scope_key:
            scope_keys[scope] = scope_key
    return scope_keys


def build_state_context(
    event: AgentEventEnvelope,
    binding: AgentBinding,
    descriptor: AgentRunnerDescriptor,
) -> dict[str, typing.Any]:
    """Build the State API context stored in the run session."""
    return {
        'scope_keys': build_state_scope_keys(event, binding, descriptor),
        'binding_identity': get_binding_identity(binding),
        'bot_id': event.bot_id,
        'workspace_id': event.workspace_id,
        'conversation_id': event.conversation_id,
        'thread_id': event.thread_id,
        'actor_type': event.actor.actor_type if event.actor else None,
        'actor_id': event.actor.actor_id if event.actor else None,
        'subject_type': event.subject.subject_type if event.subject else None,
        'subject_id': event.subject.subject_id if event.subject else None,
    }
