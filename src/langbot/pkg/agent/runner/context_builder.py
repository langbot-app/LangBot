"""Agent run context builder for provisioning AgentRunContext envelopes."""
from __future__ import annotations

import uuid
import time
import typing

from langbot_plugin.api.entities.builtin.pipeline import query as pipeline_query
from langbot_plugin.api.entities.builtin.platform import message as platform_message

from ...core import app
from .descriptor import AgentRunnerDescriptor
from .config_migration import ConfigMigration
from .context_packager import AgentContextPackager
from .state_store import get_state_store
from . import events as runner_events
from .host_models import AgentEventEnvelope, AgentBinding
from .pipeline_compat_adapter import PipelineCompatAdapter


DEFAULT_RUNNER_TIMEOUT_SECONDS = 300


# Internal models for the agent runner context protocol.


class AgentTrigger(typing.TypedDict):
    """Agent trigger information."""
    type: str
    source: str  # 'pipeline' or 'event_router'
    timestamp: int | None


class ConversationContext(typing.TypedDict):
    """Conversation context."""
    session_id: str | None
    conversation_id: str | None
    launcher_type: str | None
    launcher_id: str | None
    sender_id: str | None
    bot_uuid: str | None
    pipeline_uuid: str | None


class AgentInput(typing.TypedDict):
    """Agent input."""
    text: str | None
    contents: list[dict[str, typing.Any]]
    message_chain: dict[str, typing.Any] | None
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


class ToolResource(typing.TypedDict):
    """Tool resource payload."""
    tool_name: str
    tool_type: str | None
    description: str | None


class KnowledgeBaseResource(typing.TypedDict):
    """Knowledge base resource payload."""
    kb_id: str
    kb_name: str | None
    kb_type: str | None


class FileResource(typing.TypedDict):
    """File resource payload."""
    file_id: str
    file_name: str | None
    mime_type: str | None
    source: str | None


class StorageResource(typing.TypedDict):
    """Storage resource payload."""
    plugin_storage: bool
    workspace_storage: bool


class AgentResources(typing.TypedDict):
    """Agent resources payload."""
    models: list[ModelResource]
    tools: list[ToolResource]
    knowledge_bases: list[KnowledgeBaseResource]
    files: list[FileResource]
    storage: StorageResource
    platform_capabilities: dict[str, typing.Any]


class AgentRuntimeContext(typing.TypedDict):
    """Agent runtime context."""
    langbot_version: str | None
    sdk_protocol_version: str
    query_id: int | None
    trace_id: str | None
    deadline_at: float | None
    metadata: dict[str, typing.Any]


class AgentRunContextPayload(typing.TypedDict):
    """AgentRunContext payload passed to an agent runner.

    Protocol v1 structure - matches SDK AgentRunContext.

    Note: The 'config' field contains the binding config from ai.runner_config[runner_id],
    which is Pipeline's configuration for this specific runner binding (not plugin instance config).
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
    config: dict[str, typing.Any]  # Binding config from ai.runner_config[runner_id]
    bootstrap: dict[str, typing.Any] | None  # Optional bootstrap context
    compatibility: dict[str, typing.Any] | None  # Legacy compatibility context
    metadata: dict[str, typing.Any]  # Additional metadata


class AgentRunContextBuilder:
    """Builder for provisioning AgentRunContext.

    Two entry points:
    - build_context_from_event(event, binding): Event-first Protocol v1
    - build_context(query, descriptor, resources): Legacy Query-based (calls event-based internally)

    Responsibilities:
    - Generate new run_id (UUID, not query id)
    - Set trigger type based on source
    - Build conversation context from session/event
    - Build input from user_message/event
    - Build params with filtering
    - Build state snapshot from state_store
    - Build runtime context with host info, trace_id, deadline
    - Set config from runner binding configuration
    """

    ap: app.Application

    # Params filtering rules
    # Exclude variables starting with underscore (internal)
    INTERNAL_PREFIX = '_'

    # Exclude variables with sensitive naming patterns
    SENSITIVE_PATTERNS = ('secret', 'token', 'key', 'password', 'credential', 'api_key', 'apikey')

    # Exclude permission/control variables
    PERMISSION_VARS = ('_pipeline_bound_plugins', '_authorized', '_permission')

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.context_packager = AgentContextPackager()

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
            binding: Agent binding configuration
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
                'session_id': None,  # Legacy field
                'conversation_id': event.conversation_id,
                'thread_id': event.thread_id,
                'launcher_type': None,  # Will be filled from actor/subject if needed
                'launcher_id': None,
                'sender_id': event.actor.actor_id if event.actor else None,
                'bot_uuid': event.bot_id,
                'pipeline_uuid': binding.pipeline_uuid,  # Legacy
            }

        # Build event context (Protocol v1 event-first)
        event_context = {
            'event_id': event.event_id,
            'event_type': event.event_type,
            'event_time': event.event_time,
            'source': event.source,
            'source_event_type': None,
            'data': {},
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
                'subject_data': event.subject.data,
            }

        # Build input from event
        input: AgentInput = {
            'text': event.input.text,
            'contents': [c.model_dump(mode='json') if hasattr(c, 'model_dump') else c for c in event.input.contents],
            'message_chain': event.input.message_chain,
            'attachments': [a.model_dump(mode='json') if hasattr(a, 'model_dump') else a for a in event.input.attachments],
        }

        # Build context access (no history inlined by default for Protocol v1)
        # Populate with actual values from stores
        context_access = await self._build_context_access(event, descriptor)

        # Build state snapshot from event context
        state_store = get_state_store()
        state: AgentRunState = state_store.build_snapshot_from_event(event, binding, descriptor)

        # Build runtime context
        runtime: AgentRuntimeContext = {
            'langbot_version': self.ap.ver_mgr.get_current_version(),
            'sdk_protocol_version': descriptor.protocol_version,
            'query_id': None,  # No query_id in event-first mode
            'trace_id': run_id,
            'deadline_at': self._build_deadline_from_binding(binding),
            'metadata': {
                'bot_id': event.bot_id,
                'workspace_id': event.workspace_id,
                'streaming_supported': event.delivery.supports_streaming,
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

        # Build compatibility context (empty for event-first)
        compatibility_context = {
            'query_id': None,
            'pipeline_uuid': binding.pipeline_uuid,
            'max_round': binding.max_round,  # For reference only
            'legacy_messages': [],
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
            'bootstrap': None,  # Optional - no messages inlined by default
            'compatibility': compatibility_context,
            'metadata': {},  # Additional metadata
        }

        return context

    async def build_context(
        self,
        query: pipeline_query.Query,
        descriptor: AgentRunnerDescriptor,
        resources: AgentResources,
    ) -> AgentRunContextPayload:
        """Build AgentRunContext envelope from Query.

        This is a compatibility wrapper that converts Query to event + binding
        and delegates to build_context_from_event().

        For Protocol v1, messages are NOT inlined by default.
        Legacy max-round only affects bootstrap (via compatibility adapter),
        NOT Protocol v1 entities.

        Args:
            query: Pipeline query
            descriptor: Runner descriptor
            resources: Built resources from AgentResourceBuilder

        Returns:
            AgentRunContext payload for the plugin runner
        """
        # Resolve runner config for binding
        runner_id = descriptor.id
        runner_config = ConfigMigration.resolve_runner_config(
            query.pipeline_config,
            runner_id,
        )

        # Extract max_round for compatibility (NOT Protocol v1)
        # Note: config uses 'max-round' with hyphen, not 'max_round'
        max_round = runner_config.get('max-round')
        if max_round is None:
            ai_config = query.pipeline_config.get('ai', {}) if query.pipeline_config else {}
            max_round = ai_config.get('max-round')

        # Build trigger
        trigger: AgentTrigger = {
            'type': runner_events.MESSAGE_RECEIVED,
            'source': 'pipeline',
            'timestamp': int(time.time()),
        }

        # Build conversation context
        conversation: ConversationContext | None = None
        session = getattr(query, 'session', None)
        if session:
            conversation = {
                'session_id': f'{getattr(session, "launcher_type", "").value if hasattr(getattr(session, "launcher_type", ""), "value") else getattr(session, "launcher_type", "")}_{getattr(session, "launcher_id", "")}',
                'conversation_id': getattr(getattr(session, 'using_conversation', None), 'uuid', None),
                'launcher_type': getattr(session, 'launcher_type', None).value if hasattr(getattr(session, 'launcher_type', None), 'value') else getattr(session, 'launcher_type', None),
                'launcher_id': getattr(session, 'launcher_id', None),
                'sender_id': str(getattr(query, 'sender_id', '')) if getattr(query, 'sender_id', None) else None,
                'bot_uuid': getattr(query, 'bot_uuid', None),
                'pipeline_uuid': getattr(query, 'pipeline_uuid', None),
            }

        # Build input
        input: AgentInput = self._build_input(query)

        # Build params from query.variables with filtering
        params = self._build_params(query)

        # Build state snapshot from state_store
        state_store = get_state_store()
        state: AgentRunState = state_store.build_snapshot(query, descriptor)

        streaming_supported = await self._is_stream_output_supported(query)
        remove_think = query.pipeline_config.get('output', {}).get('misc', {}).get('remove-think', False) if query.pipeline_config else False

        # Build runtime context
        run_id = str(uuid.uuid4())
        runtime: AgentRuntimeContext = {
            'langbot_version': self.ap.ver_mgr.get_current_version(),
            'sdk_protocol_version': descriptor.protocol_version,
            'query_id': query.query_id,
            'trace_id': run_id,  # Use run_id as trace_id for now
            'deadline_at': self._build_deadline(runner_config),
            'metadata': {
                'bot_name': query.variables.get('_monitoring_bot_name', 'Unknown') if query.variables else 'Unknown',
                'pipeline_name': query.variables.get('_monitoring_pipeline_name', 'Unknown') if query.variables else 'Unknown',
                'streaming_supported': streaming_supported,
                'remove_think': remove_think,
            },
        }

        # Build delivery context from query adapter capabilities
        delivery_context = {
            'surface': 'pipeline',  # Legacy pipeline surface
            'reply_target': None,
            'supports_streaming': streaming_supported,
            'supports_edit': False,
            'supports_reaction': False,
            'max_message_size': None,
            'platform_capabilities': {},
        }

        # Build context access (for legacy, minimal API availability)
        context_access = {
            'conversation_id': conversation.get('conversation_id') if conversation else None,
            'thread_id': None,
            'latest_cursor': None,
            'event_seq': None,
            'transcript_seq': None,
            'has_history_before': False,
            'inline_policy': {
                'mode': 'current_event',
                'delivered_count': 0,
                'source_total_count': None,
                'messages_complete': False,
                'reason': 'legacy_pipeline',
            },
            'available_apis': {
                'history_page': False,
                'history_search': False,
                'event_get': False,
                'event_page': False,
                'artifact_metadata': False,
                'artifact_read': False,
                'state': True,
                'storage': True,
            },
        }

        # Build compatibility context (for legacy Query/Pipeline fields)
        compatibility_context = {
            'query_id': query.query_id,
            'pipeline_uuid': getattr(query, 'pipeline_uuid', None),
            'max_round': max_round,  # For reference only
            'legacy_messages': [],  # Will be filled if max_round is set
            'extra': {
                'params': params,  # Put params in compatibility.extra
                'prompt': self._build_prompt(query),  # Put prompt in compatibility.extra
            },
        }

        # Build bootstrap context (optional, for legacy max-round)
        bootstrap_context = None

        # For legacy compatibility: add bootstrap messages if max_round is set
        # This goes into bootstrap.messages, NOT top-level messages
        if max_round and max_round > 0:
            packaged_context = self.context_packager.package_messages(query, runner_config)
            legacy_messages = self._build_messages(packaged_context.messages)
            # Put in bootstrap for Protocol v1
            bootstrap_context = {
                'messages': legacy_messages,
                'summary': None,
                'artifacts': [],
                'metadata': {},
            }
            # Also update compatibility for legacy runners
            compatibility_context['legacy_messages'] = legacy_messages
            # Update runtime metadata
            runtime['metadata']['context_packaging'] = {
                'policy': packaged_context.policy,
                'history': packaged_context.history,
            }

        # Build full context - Protocol v1 structure
        context: AgentRunContextPayload = {
            'run_id': run_id,
            'trigger': trigger,
            'conversation': conversation,
            'event': self._build_event(query),  # REQUIRED
            'actor': self._build_actor(query),
            'subject': self._build_subject(query),
            'input': input,
            'delivery': delivery_context,  # REQUIRED
            'resources': resources,
            'context': context_access,  # ContextAccess - REQUIRED
            'state': state,
            'runtime': runtime,
            'config': runner_config,
            'bootstrap': bootstrap_context,  # Optional bootstrap
            'compatibility': compatibility_context,  # Legacy compatibility
            'metadata': {},  # Additional metadata
        }

        return context

    def _build_input(self, query: pipeline_query.Query) -> AgentInput:
        """Build AgentInput from query."""
        text = None
        text_parts: list[str] = []
        contents: list[dict[str, typing.Any]] = []

        if query.user_message:
            # Extract text if content is single text element
            if isinstance(query.user_message.content, list):
                for elem in query.user_message.content:
                    contents.append(elem.model_dump(mode='json'))
                    if elem.type == 'text':
                        elem_text = getattr(elem, 'text', None)
                        if elem_text:
                            text_parts.append(elem_text)
            else:
                # Single string content
                text = str(query.user_message.content)
                contents.append({'type': 'text', 'text': text})

        if text_parts:
            text = ''.join(text_parts)

        # Include message_chain for platform-specific format
        message_chain_dict = None
        if query.message_chain:
            message_chain_dict = query.message_chain.model_dump(mode='json')

        return {
            'text': text,
            'contents': contents,
            'message_chain': message_chain_dict,
            'attachments': self._build_attachments(query, contents),
        }

    def _build_attachments(
        self,
        query: pipeline_query.Query,
        contents: list[dict[str, typing.Any]],
    ) -> list[dict[str, typing.Any]]:
        """Extract runner-consumable attachment data from input contents."""
        attachments: list[dict[str, typing.Any]] = []

        for elem in contents:
            elem_type = elem.get('type')
            if elem_type == 'image_url':
                image_url = elem.get('image_url') or {}
                attachments.append(
                    {
                        'type': 'image',
                        'source': 'url',
                        'url': image_url.get('url') if isinstance(image_url, dict) else str(image_url),
                    }
                )
            elif elem_type == 'image_base64':
                image_base64 = elem.get('image_base64')
                attachments.append(
                    {
                        'type': 'image',
                        'source': 'base64',
                        'content': image_base64,
                        'content_type': self._infer_base64_content_type(image_base64, 'image/jpeg'),
                        'name': 'image',
                        'has_content': bool(image_base64),
                    }
                )
            elif elem_type == 'file_url':
                attachments.append(
                    {
                        'type': 'file',
                        'source': 'url',
                        'url': elem.get('file_url'),
                        'name': elem.get('file_name'),
                    }
                )
            elif elem_type == 'file_base64':
                file_base64 = elem.get('file_base64')
                attachments.append(
                    {
                        'type': 'file',
                        'source': 'base64',
                        'name': elem.get('file_name'),
                        'content': file_base64,
                        'content_type': self._infer_base64_content_type(file_base64, 'application/octet-stream'),
                        'has_content': bool(file_base64),
                    }
                )

        message_chain = getattr(query, 'message_chain', None)
        if message_chain:
            for component in message_chain:
                if isinstance(component, platform_message.Image):
                    attachments.append(
                        {
                            'type': 'image',
                            'source': 'message_chain',
                            'id': component.image_id or None,
                            'url': component.url or None,
                            'path': str(component.path) if component.path else None,
                            'content': component.base64 or None,
                            'content_type': self._infer_base64_content_type(component.base64, 'image/jpeg'),
                            'name': 'image',
                            'has_content': bool(component.base64),
                        }
                    )
                elif isinstance(component, platform_message.File):
                    attachments.append(
                        {
                            'type': 'file',
                            'source': 'message_chain',
                            'id': component.id or None,
                            'name': component.name or None,
                            'size': component.size or 0,
                            'url': component.url or None,
                            'path': component.path or None,
                            'content': component.base64 or None,
                            'content_type': self._infer_base64_content_type(component.base64, 'application/octet-stream'),
                            'has_content': bool(component.base64),
                        }
                    )
                elif isinstance(component, platform_message.Voice):
                    attachments.append(
                        {
                            'type': 'voice',
                            'source': 'message_chain',
                            'id': component.voice_id or None,
                            'url': component.url or None,
                            'path': component.path or None,
                            'duration': component.length or 0,
                            'content': component.base64 or None,
                            'content_type': self._infer_base64_content_type(component.base64, 'audio/mpeg'),
                            'name': 'voice',
                            'has_content': bool(component.base64),
                        }
                    )

        return attachments

    def _infer_base64_content_type(self, value: typing.Any, default: str) -> str:
        """Infer MIME type from a data URL base64 value."""
        if not isinstance(value, str):
            return default
        if value.startswith('data:') and ';base64,' in value:
            return value[5:value.find(';base64,')] or default
        return default

    def _build_event(self, query: pipeline_query.Query) -> dict[str, typing.Any]:
        """Build a minimal EBA-compatible event envelope from the message query.

        The public event_type must be a stable AgentRunner protocol name. Keep
        platform or SDK class names inside event_data so future EventRouter
        events can share the same top-level naming contract.
        """
        message_event = getattr(query, 'message_event', None)
        event_data: dict[str, typing.Any] = {}

        if message_event and hasattr(message_event, 'model_dump'):
            try:
                event_data = message_event.model_dump(mode='json')
            except TypeError:
                event_data = message_event.model_dump()
            except Exception:
                event_data = {}
            event_data.pop('source_platform_object', None)

        source_event_type = getattr(message_event, 'type', None) if message_event else None
        if source_event_type:
            event_data.setdefault('source_event_type', source_event_type)

        message_chain = getattr(query, 'message_chain', None)
        message_id = getattr(message_chain, 'message_id', None)
        if message_id == -1:
            message_id = None

        event_time = getattr(message_event, 'time', None) if message_event else None
        event_timestamp = int(event_time) if isinstance(event_time, (int, float)) else None

        return {
            'event_type': runner_events.MESSAGE_RECEIVED,
            'event_id': str(message_id or getattr(query, 'query_id', '')),
            'event_timestamp': event_timestamp,
            'event_data': event_data,
        }

    def _build_actor(self, query: pipeline_query.Query) -> dict[str, typing.Any]:
        """Build actor context for the sender that triggered the run."""
        message_event = getattr(query, 'message_event', None)
        sender = getattr(message_event, 'sender', None) if message_event else None
        actor_id = getattr(sender, 'id', None) or getattr(query, 'sender_id', None)
        actor_name = sender.get_name() if sender and hasattr(sender, 'get_name') else None

        return {
            'actor_type': 'user',
            'actor_id': str(actor_id) if actor_id is not None else None,
            'actor_name': actor_name,
        }

    def _build_subject(self, query: pipeline_query.Query) -> dict[str, typing.Any]:
        """Build subject context for the current message."""
        message_chain = getattr(query, 'message_chain', None)
        message_id = getattr(message_chain, 'message_id', None)
        if message_id == -1:
            message_id = None

        launcher_type = getattr(query, 'launcher_type', None)
        launcher_type_value = getattr(launcher_type, 'value', launcher_type)

        return {
            'subject_type': 'message',
            'subject_id': str(message_id or getattr(query, 'query_id', '')),
            'subject_data': {
                'launcher_type': launcher_type_value,
                'launcher_id': getattr(query, 'launcher_id', None),
                'sender_id': str(getattr(query, 'sender_id', '')),
                'bot_uuid': getattr(query, 'bot_uuid', None),
                'pipeline_uuid': getattr(query, 'pipeline_uuid', None),
            },
        }

    def _build_deadline(self, runner_config: dict[str, typing.Any]) -> float | None:
        """Build deadline timestamp from runner timeout config.

        A missing timeout uses the host default. Explicit null, zero, or negative
        values disable the total run deadline for advanced deployments.
        """
        timeout = runner_config.get('timeout', DEFAULT_RUNNER_TIMEOUT_SECONDS)
        if timeout is None:
            return None

        try:
            timeout_seconds = float(timeout)
        except (TypeError, ValueError):
            return None

        if timeout_seconds <= 0:
            return None

        return time.time() + timeout_seconds

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

    async def _is_stream_output_supported(self, query: pipeline_query.Query) -> bool:
        """Check whether the current adapter can consume streaming chunks."""
        try:
            return await query.adapter.is_stream_output_supported()
        except AttributeError:
            return False
        except Exception:
            return False

    def _build_prompt(self, query: pipeline_query.Query) -> list[dict[str, typing.Any]]:
        """Build effective prompt messages from query.prompt after preprocessing."""
        prompt_messages: list[dict[str, typing.Any]] = []

        prompt = getattr(query, 'prompt', None)
        messages = getattr(prompt, 'messages', None)
        if not messages:
            return prompt_messages

        for msg in messages:
            prompt_messages.append(msg.model_dump(mode='json'))

        return prompt_messages

    def _build_messages(self, source_messages: list[typing.Any]) -> list[dict[str, typing.Any]]:
        """Build messages list from packaged source messages."""
        messages: list[dict[str, typing.Any]] = []

        for msg in source_messages:
            messages.append(msg.model_dump(mode='json'))

        return messages

    def _build_params(self, query: pipeline_query.Query) -> dict[str, typing.Any]:
        """Build params from query.variables with filtering.

        Filtering rules:
        1. Exclude variables starting with underscore (internal)
        2. Exclude variables with sensitive naming patterns (secret, token, key, password)
        3. Exclude permission/control variables
        4. Keep only JSON-serializable values

        Args:
            query: Pipeline query

        Returns:
            Filtered params dict
        """
        params: dict[str, typing.Any] = {}

        if not query.variables:
            return params

        for key, value in query.variables.items():
            # Filter internal variables (starting with underscore)
            if key.startswith(self.INTERNAL_PREFIX):
                continue

            # Filter sensitive naming patterns
            key_lower = key.lower()
            if any(pattern in key_lower for pattern in self.SENSITIVE_PATTERNS):
                continue

            # Filter permission variables
            if any(key == perm_var or key.startswith(perm_var) for perm_var in self.PERMISSION_VARS):
                continue

            # Keep only JSON-serializable values
            if self._is_json_serializable(value):
                params[key] = value

        return params

    def _is_json_serializable(self, value: typing.Any) -> bool:
        """Check if value is JSON-serializable.

        Note: set is NOT JSON-serializable. json.dumps({"x": {1}}) fails.
        Only list and tuple are allowed as collection types.

        Args:
            value: Value to check

        Returns:
            True if JSON-serializable, False otherwise
        """
        if value is None:
            return True
        if isinstance(value, (str, int, float, bool)):
            return True
        # Only allow list and tuple, NOT set (set is not JSON-serializable)
        if isinstance(value, (list, tuple)):
            return all(self._is_json_serializable(item) for item in value)
        if isinstance(value, dict):
            return all(
                isinstance(k, str) and self._is_json_serializable(v)
                for k, v in value.items()
            )
        # Pydantic models and other complex types are not directly serializable
        # as params (they may have internal structure not meant for runners)
        return False

    async def _build_context_access(
        self,
        event: AgentEventEnvelope,
        descriptor: AgentRunnerDescriptor,
    ) -> dict[str, typing.Any]:
        """Build ContextAccess with actual values from stores.

        Args:
            event: Event envelope
            descriptor: Runner descriptor

        Returns:
            ContextAccess dict
        """
        conversation_id = event.conversation_id

        # Check if history APIs are available for this runner
        # Based on runner permissions
        permissions = descriptor.permissions or {}
        history_permissions = permissions.get('history', [])
        event_permissions = permissions.get('events', [])
        artifact_permissions = permissions.get('artifacts', [])

        history_page_enabled = 'page' in history_permissions and conversation_id is not None
        history_search_enabled = 'search' in history_permissions and conversation_id is not None
        event_get_enabled = 'get' in event_permissions
        event_page_enabled = 'page' in event_permissions and conversation_id is not None
        artifact_metadata_enabled = 'metadata' in artifact_permissions
        artifact_read_enabled = 'read' in artifact_permissions

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
                'reason': 'self_managed_context',
            },
            'available_apis': {
                'history_page': history_page_enabled,
                'history_search': history_search_enabled,
                'event_get': event_get_enabled,
                'event_page': event_page_enabled,
                'artifact_metadata': artifact_metadata_enabled,
                'artifact_read': artifact_read_enabled,
                'state': True,
                'storage': True,
            },
        }
