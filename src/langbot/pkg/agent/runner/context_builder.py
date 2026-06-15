"""Agent run context builder for provisioning AgentRunContext envelopes."""

from __future__ import annotations

import uuid
import time
import typing

from ...core import app
from .descriptor import AgentRunnerDescriptor
from .persistent_state_store import get_persistent_state_store
from .host_models import AgentEventEnvelope, AgentBinding


DEFAULT_RUNNER_TIMEOUT_SECONDS = 300


# Internal models for the agent runner context protocol.


class AgentTrigger(typing.TypedDict):
    """Agent trigger information."""

    type: str
    source: str
    timestamp: int | None


class ConversationContext(typing.TypedDict):
    """Conversation context."""

    conversation_id: str | None
    thread_id: str | None
    launcher_type: str | None
    launcher_id: str | None
    sender_id: str | None
    bot_id: str | None
    workspace_id: str | None
    session_id: str | None


class AgentInput(typing.TypedDict):
    """Agent input."""

    text: str | None
    contents: list[dict[str, typing.Any]]
    attachments: list[dict[str, typing.Any]]


class AgentRunState(typing.TypedDict):
    """Agent run state with 4 scopes."""

    conversation: dict[str, typing.Any]
    actor: dict[str, typing.Any]
    subject: dict[str, typing.Any]
    runner: dict[str, typing.Any]


# Resource payload models matching langbot-plugin-sdk/resources.py.


class ModelResource(typing.TypedDict):
    """Model resource payload."""

    model_id: str
    model_type: str | None
    provider: str | None
    operations: list[str]


class ToolResource(typing.TypedDict):
    """Tool resource payload."""

    tool_name: str
    tool_type: str | None
    description: str | None
    operations: list[str]


class KnowledgeBaseResource(typing.TypedDict):
    """Knowledge base resource payload."""

    kb_id: str
    kb_name: str | None
    kb_type: str | None
    operations: list[str]


class SkillResource(typing.TypedDict):
    """Skill resource payload."""

    skill_name: str
    display_name: str | None
    description: str | None


class FileResource(typing.TypedDict):
    """File resource payload."""

    file_id: str
    file_name: str | None
    mime_type: str | None
    source: str | None
    operations: list[str]


class StorageResource(typing.TypedDict):
    """Storage resource payload."""

    plugin_storage: bool
    workspace_storage: bool


class AgentResources(typing.TypedDict):
    """Agent resources payload."""

    models: list[ModelResource]
    tools: list[ToolResource]
    knowledge_bases: list[KnowledgeBaseResource]
    skills: list[SkillResource]
    files: list[FileResource]
    storage: StorageResource
    platform_capabilities: dict[str, typing.Any]


class AgentRuntimeContext(typing.TypedDict):
    """Agent runtime context."""

    langbot_version: str | None
    trace_id: str | None
    deadline_at: float | None
    metadata: dict[str, typing.Any]


class AgentRunContextPayload(typing.TypedDict):
    """AgentRunContext payload passed to an agent runner.

    Protocol v1 structure - matches SDK AgentRunContext.

    Note: The 'config' field contains the current Agent/runner config
    from ai.runner_config[runner_id] while the current Query entry remains
    a temporary configuration container. It is not plugin instance config.
    """

    run_id: str
    trigger: AgentTrigger
    conversation: ConversationContext | None
    event: dict[str, typing.Any]  # REQUIRED for Protocol v1
    actor: dict[str, typing.Any] | None
    subject: dict[str, typing.Any] | None
    input: AgentInput
    delivery: dict[str, typing.Any]  # REQUIRED for Protocol v1
    resources: AgentResources
    context: dict[str, typing.Any]  # ContextAccess - REQUIRED for Protocol v1
    state: AgentRunState
    runtime: AgentRuntimeContext
    config: dict[str, typing.Any]  # Agent/runner config from ai.runner_config[runner_id]
    adapter: dict[str, typing.Any] | None  # Entry adapter context
    metadata: dict[str, typing.Any]  # Additional metadata


class AgentRunContextBuilder:
    """Builder for provisioning AgentRunContext.

    Responsibilities:
    - Generate new run_id (UUID, not query id)
    - Set trigger type based on event source
    - Build conversation context from event
    - Build input from event
    - Build state snapshot from PersistentStateStore
    - Build runtime context with host info, trace_id, deadline
    - Set config from current Agent/runner configuration.

    Query adaptation belongs to QueryEntryAdapter, not this builder.
    """

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    @staticmethod
    def _positive_int(value: typing.Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.isdigit():
            parsed_value = int(value)
            if parsed_value > 0:
                return parsed_value
        return None

    @staticmethod
    def _is_llm_model_resource(model_resource: ModelResource) -> bool:
        operations = model_resource.get('operations')
        if isinstance(operations, list) and operations:
            return bool({'invoke', 'stream'} & {str(operation) for operation in operations})
        return model_resource.get('model_type') != 'rerank'

    async def _build_model_context_window_tokens(self, resources: AgentResources) -> int | None:
        model_mgr = getattr(self.ap, 'model_mgr', None)
        if model_mgr is None:
            return None

        for model_resource in resources.get('models', []):
            if not self._is_llm_model_resource(model_resource):
                continue

            model_uuid = model_resource.get('model_id')
            if not isinstance(model_uuid, str) or not model_uuid:
                continue

            try:
                model = await model_mgr.get_model_by_uuid(model_uuid)
            except Exception as exc:
                logger = getattr(self.ap, 'logger', None)
                if logger is not None:
                    logger.debug(f'Failed to resolve model context window for {model_uuid}: {exc}')
                continue

            model_entity = getattr(model, 'model_entity', None)
            context_length = self._positive_int(getattr(model_entity, 'context_length', None))
            return context_length

        return None

    async def build_context_from_event(
        self,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        descriptor: AgentRunnerDescriptor,
        resources: AgentResources,
    ) -> AgentRunContextPayload:
        """Build AgentRunContext from event-first envelope.

        This is the main entry point for Protocol v1.
        Does NOT inline full history by default.

        Args:
            event: Event envelope
            binding: Agent binding
            descriptor: Runner descriptor
            resources: Built resources

        Returns:
            AgentRunContextPayload for the runner
        """
        # Generate new run_id
        run_id = str(uuid.uuid4())

        # Build trigger from event
        trigger: AgentTrigger = {
            'type': event.event_type,
            'source': event.source,
            'timestamp': event.event_time or int(time.time()),
        }

        # Build conversation context from event
        conversation: ConversationContext | None = None
        if event.conversation_id:
            conversation = {
                'session_id': None,
                'conversation_id': event.conversation_id,
                'thread_id': event.thread_id,
                'launcher_type': None,  # Will be filled from actor/subject if needed
                'launcher_id': None,
                'sender_id': event.actor.actor_id if event.actor else None,
                'bot_id': event.bot_id,
                'workspace_id': event.workspace_id,
            }

        # Build event context (Protocol v1 event-first)
        event_context = {
            'event_id': event.event_id,
            'event_type': event.event_type,
            'event_time': event.event_time,
            'source': event.source,
            'source_event_type': event.source_event_type,
            'raw_ref': event.raw_ref.model_dump(mode='json') if event.raw_ref else None,
            'data': event.data,
        }

        # Build actor context
        actor_context = None
        if event.actor:
            actor_context = {
                'actor_type': event.actor.actor_type,
                'actor_id': event.actor.actor_id,
                'actor_name': event.actor.actor_name,
            }

        # Build subject context
        subject_context = None
        if event.subject:
            subject_context = {
                'subject_type': event.subject.subject_type,
                'subject_id': event.subject.subject_id,
                'data': event.subject.data,
            }

        # Build input from event
        input: AgentInput = {
            'text': event.input.text,
            'contents': [c.model_dump(mode='json') if hasattr(c, 'model_dump') else c for c in event.input.contents],
            'attachments': [
                a.model_dump(mode='json') if hasattr(a, 'model_dump') else a for a in event.input.attachments
            ],
        }

        # Build context access (no history inlined by default for Protocol v1)
        # Populate with actual values from stores
        context_access = await self._build_context_access(event, descriptor, binding)

        # Build state snapshot from persistent state store (event-first Protocol v1)
        persistent_state_store = get_persistent_state_store(self.ap.persistence_mgr.get_db_engine())
        state: AgentRunState = await persistent_state_store.build_snapshot_from_event(event, binding, descriptor)

        model_context_window_tokens = await self._build_model_context_window_tokens(resources)

        # Build runtime context
        runtime: AgentRuntimeContext = {
            'langbot_version': self.ap.ver_mgr.get_current_version(),
            'trace_id': run_id,
            'deadline_at': self._build_deadline_from_binding(binding),
            'metadata': {
                'bot_id': event.bot_id,
                'workspace_id': event.workspace_id,
                'streaming_supported': event.delivery.supports_streaming,
                'model_context_window_tokens': model_context_window_tokens,
            },
        }

        # Build delivery context
        delivery_context = {
            'surface': event.delivery.surface,
            'reply_target': event.delivery.reply_target,
            'supports_streaming': event.delivery.supports_streaming,
            'supports_edit': event.delivery.supports_edit,
            'supports_reaction': event.delivery.supports_reaction,
            'max_message_size': event.delivery.max_message_size,
            'platform_capabilities': event.delivery.platform_capabilities,
        }

        # Build adapter context (empty for event-first)
        adapter_context = {
            'extra': {},
        }

        # Build full context - Protocol v1 structure
        context: AgentRunContextPayload = {
            'run_id': run_id,
            'trigger': trigger,
            'conversation': conversation,
            'event': event_context,  # REQUIRED
            'actor': actor_context,
            'subject': subject_context,
            'input': input,
            'delivery': delivery_context,  # REQUIRED
            'resources': resources,
            'context': context_access,  # ContextAccess - REQUIRED
            'state': state,
            'runtime': runtime,
            'config': binding.runner_config,
            'adapter': adapter_context,
            'metadata': {},  # Additional metadata
        }

        return context

    def _build_deadline_from_binding(self, binding: AgentBinding) -> float | None:
        """Build deadline timestamp from binding timeout config.

        Args:
            binding: Agent binding with runner_config

        Returns:
            Deadline timestamp or None
        """
        timeout = binding.runner_config.get('timeout', DEFAULT_RUNNER_TIMEOUT_SECONDS)
        if timeout is None:
            return None

        try:
            timeout_seconds = float(timeout)
        except (TypeError, ValueError):
            return None

        if timeout_seconds <= 0:
            return None

        return time.time() + timeout_seconds

    async def _build_context_access(
        self,
        event: AgentEventEnvelope,
        descriptor: AgentRunnerDescriptor,
        binding: AgentBinding | None = None,
    ) -> dict[str, typing.Any]:
        """Build ContextAccess with actual values from stores.

        Args:
            event: Event envelope
            descriptor: Runner descriptor
            binding: Agent binding (required for state_policy in event-first mode)

        Returns:
            ContextAccess dict
        """
        conversation_id = event.conversation_id
        permissions = descriptor.permissions
        history_perms = set(permissions.history)
        event_perms = set(permissions.events)
        artifact_perms = set(permissions.artifacts)
        storage_perms = set(permissions.storage)

        history_page_enabled = 'page' in history_perms and conversation_id is not None
        history_search_enabled = 'search' in history_perms and conversation_id is not None
        event_get_enabled = 'get' in event_perms
        event_page_enabled = 'page' in event_perms and conversation_id is not None
        artifact_metadata_enabled = 'metadata' in artifact_perms
        artifact_read_enabled = 'read' in artifact_perms
        steering_pull_enabled = (
            bool(getattr(descriptor.capabilities, 'steering', False)) and conversation_id is not None
        )
        run_get_enabled = True
        run_list_enabled = conversation_id is not None
        run_events_page_enabled = True
        run_cancel_enabled = True
        run_append_result_enabled = False
        run_finalize_enabled = False
        run_claim_enabled = False
        run_renew_claim_enabled = False
        run_release_claim_enabled = False
        runtime_register_enabled = False
        runtime_heartbeat_enabled = False
        runtime_list_enabled = False

        # Determine state API availability based on binding state_policy.
        state_enabled = False
        storage_enabled = False
        if binding is not None:
            state_policy = binding.state_policy
            if state_policy.enable_state and state_policy.state_scopes:
                state_enabled = True

            resource_policy = binding.resource_policy
            storage_enabled = ('plugin' in storage_perms and resource_policy.allow_plugin_storage) or (
                'workspace' in storage_perms and resource_policy.allow_workspace_storage
            )

        # Get latest cursor and has_history_before if conversation exists
        latest_cursor = None
        has_history_before = False

        if conversation_id:
            try:
                from .transcript_store import TranscriptStore

                store = TranscriptStore(self.ap.persistence_mgr.get_db_engine())

                latest_cursor = await store.get_latest_cursor(conversation_id)
                if latest_cursor:
                    has_history_before = True
            except Exception as e:
                self.ap.logger.warning(f'Failed to get transcript cursor: {e}')

        return {
            'conversation_id': conversation_id,
            'thread_id': event.thread_id,
            'latest_cursor': latest_cursor,
            'event_seq': None,  # Will be populated when EventLog is written
            'transcript_seq': int(latest_cursor) if latest_cursor else None,
            'has_history_before': has_history_before,
            'inline_policy': {
                'mode': 'current_event',
                'delivered_count': 0,
                'source_total_count': None,
                'messages_complete': False,
                'reason': 'current_event_only',
            },
            'available_apis': {
                'prompt_get': False,
                'history_page': history_page_enabled,
                'history_search': history_search_enabled,
                'event_get': event_get_enabled,
                'event_page': event_page_enabled,
                'artifact_metadata': artifact_metadata_enabled,
                'artifact_read': artifact_read_enabled,
                'state': state_enabled,
                'storage': storage_enabled,
                'steering_pull': steering_pull_enabled,
                'run_get': run_get_enabled,
                'run_list': run_list_enabled,
                'run_events_page': run_events_page_enabled,
                'run_cancel': run_cancel_enabled,
                'run_append_result': run_append_result_enabled,
                'run_finalize': run_finalize_enabled,
                'run_claim': run_claim_enabled,
                'run_renew_claim': run_renew_claim_enabled,
                'run_release_claim': run_release_claim_enabled,
                'runtime_register': runtime_register_enabled,
                'runtime_heartbeat': runtime_heartbeat_enabled,
                'runtime_list': runtime_list_enabled,
            },
        }
