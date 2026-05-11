"""Agent run context builder for converting Query to SDK v1 AgentRunContext."""
from __future__ import annotations

import uuid
import time
import typing

from langbot_plugin.api.entities.builtin.pipeline import query as pipeline_query

from ...core import app
from .descriptor import AgentRunnerDescriptor
from .config_migration import ConfigMigration
from .state_store import get_state_store


# Internal models for SDK v1 context protocol matching SDK v1 resources.py


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


# SDK v1 Protocol resource models - matching langbot-plugin-sdk/resources.py


class ModelResource(typing.TypedDict):
    """Model resource per SDK v1."""
    model_id: str
    model_type: str | None
    provider: str | None


class ToolResource(typing.TypedDict):
    """Tool resource per SDK v1."""
    tool_name: str
    tool_type: str | None
    description: str | None


class KnowledgeBaseResource(typing.TypedDict):
    """Knowledge base resource per SDK v1."""
    kb_id: str
    kb_name: str | None
    kb_type: str | None


class FileResource(typing.TypedDict):
    """File resource per SDK v1."""
    file_id: str
    file_name: str | None
    mime_type: str | None
    source: str | None


class StorageResource(typing.TypedDict):
    """Storage resource per SDK v1."""
    plugin_storage: bool
    workspace_storage: bool


class AgentResources(typing.TypedDict):
    """Agent resources per SDK v1."""
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
    deadline_at: int | None
    metadata: dict[str, typing.Any]


class AgentRunContextV1(typing.TypedDict):
    """SDK v1 AgentRunContext per PROTOCOL_V1.md.

    Note: The 'config' field contains the binding config from ai.runner_config[runner_id],
    which is Pipeline's configuration for this specific runner binding (not plugin instance config).
    """
    run_id: str
    trigger: AgentTrigger
    conversation: ConversationContext | None
    event: dict[str, typing.Any] | None  # Reserved for EBA
    actor: dict[str, typing.Any] | None  # Reserved for EBA
    subject: dict[str, typing.Any] | None  # Reserved for EBA
    messages: list[dict[str, typing.Any]]
    input: AgentInput
    params: dict[str, typing.Any]
    resources: AgentResources
    state: AgentRunState
    runtime: AgentRuntimeContext
    config: dict[str, typing.Any]  # Binding config from ai.runner_config[runner_id]


class AgentRunContextBuilder:
    """Builder for converting Query to SDK v1 AgentRunContext.

    Responsibilities:
    - Generate new run_id (UUID, not query id)
    - Set trigger type to 'message.received' for pipeline
    - Build conversation context from session
    - Convert messages to SDK format
    - Build input from user_message and message_chain
    - Build params from query.variables with filtering
    - Build state snapshot from state_store
    - Set resources from AgentResourceBuilder result
    - Build runtime context with host info, trace_id, deadline
    - Set config from runner binding configuration (ai.runner_config[runner_id])
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

    async def build_context(
        self,
        query: pipeline_query.Query,
        descriptor: AgentRunnerDescriptor,
        resources: AgentResources,
    ) -> AgentRunContextV1:
        """Build AgentRunContext from Query.

        Args:
            query: Pipeline query
            descriptor: Runner descriptor
            resources: Built resources from AgentResourceBuilder

        Returns:
            AgentRunContextV1 dict matching PROTOCOL_V1.md
        """
        # Generate new run_id
        run_id = str(uuid.uuid4())

        # Build trigger
        trigger: AgentTrigger = {
            'type': 'message.received',
            'source': 'pipeline',
            'timestamp': int(time.time()),
        }

        # Build conversation context
        conversation: ConversationContext | None = None
        if query.session:
            conversation = {
                'session_id': f'{query.session.launcher_type.value}_{query.session.launcher_id}',
                'conversation_id': getattr(query.session.using_conversation, 'uuid', None),
                'launcher_type': query.session.launcher_type.value,
                'launcher_id': query.session.launcher_id,
                'sender_id': str(query.sender_id),
                'bot_uuid': query.bot_uuid,
                'pipeline_uuid': query.pipeline_uuid,
            }

        # Build input
        input: AgentInput = self._build_input(query)

        # Build messages
        messages = self._build_messages(query)

        # Build params from query.variables with filtering
        params = self._build_params(query)

        # Build state snapshot from state_store
        state_store = get_state_store()
        state: AgentRunState = state_store.build_snapshot(query, descriptor)

        # Get runner binding config from ai.runner_config[runner_id]
        # This is Pipeline's configuration for this specific runner binding,
        # passed through AgentRunContext.config to the runner
        runner_config = ConfigMigration.resolve_runner_config(
            query.pipeline_config,
            descriptor.id,
        )

        # Build runtime context
        runtime: AgentRuntimeContext = {
            'langbot_version': self.ap.ver_mgr.get_current_version(),
            'sdk_protocol_version': descriptor.protocol_version,
            'query_id': query.query_id,
            'trace_id': run_id,  # Use run_id as trace_id for now
            'deadline_at': None,  # TODO: set from runner config timeout
            'metadata': {
                'bot_name': query.variables.get('_monitoring_bot_name', 'Unknown'),
                'pipeline_name': query.variables.get('_monitoring_pipeline_name', 'Unknown'),
            },
        }

        # Build full context
        context: AgentRunContextV1 = {
            'run_id': run_id,
            'trigger': trigger,
            'conversation': conversation,
            'event': None,  # Reserved for EBA
            'actor': None,  # Reserved for EBA
            'subject': None,  # Reserved for EBA
            'messages': messages,
            'input': input,
            'params': params,
            'resources': resources,
            'state': state,
            'runtime': runtime,
            'config': runner_config,
        }

        return context

    def _build_input(self, query: pipeline_query.Query) -> AgentInput:
        """Build AgentInput from query."""
        text = None
        contents: list[dict[str, typing.Any]] = []

        if query.user_message:
            # Extract text if content is single text element
            if isinstance(query.user_message.content, list):
                for elem in query.user_message.content:
                    contents.append(elem.model_dump(mode='json'))
                    if elem.type == 'text':
                        text = getattr(elem, 'text', None)
            else:
                # Single string content
                text = str(query.user_message.content)
                contents.append({'type': 'text', 'text': text})

        # Include message_chain for platform-specific format
        message_chain_dict = None
        if query.message_chain:
            message_chain_dict = query.message_chain.model_dump(mode='json')

        return {
            'text': text,
            'contents': contents,
            'message_chain': message_chain_dict,
            'attachments': [],  # TODO: extract attachments from message_chain
        }

    def _build_messages(self, query: pipeline_query.Query) -> list[dict[str, typing.Any]]:
        """Build messages list from query."""
        messages: list[dict[str, typing.Any]] = []

        if query.messages:
            for msg in query.messages:
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