"""Query entry adapter for converting Query to event-first envelope.

This adapter bridges the current Query entry point with the event-first
Protocol v1 architecture without exposing Query internals to runners.
"""

from __future__ import annotations

import hashlib
import typing

from langbot_plugin.api.entities.builtin.pipeline import query as pipeline_query
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.agent_runner.event import (
    AgentEventContext,
    ConversationContext,
    ActorContext,
    SubjectContext,
    RawEventRef,
)
from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput
from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext

from .host_models import (
    AgentConfig,
    AgentEventEnvelope,
    StatePolicy,
    DeliveryPolicy,
)
from .config_resolver import RunnerConfigResolver
from .resource_policy import ResourcePolicyProjector
from . import events as runner_events
from ...provider.tools.toolmgr import TOOL_SOURCE_REFS_QUERY_KEY


class QueryEntryAdapter:
    """Adapter for converting Query to event-first envelope.

    This adapter is responsible for:
    - Converting Query to AgentEventEnvelope
    - Projecting current Pipeline config to temporary AgentConfig
    - Putting Query-only fields into adapter context
    """

    INTERNAL_PREFIX = '_'
    SENSITIVE_PATTERNS = ('secret', 'token', 'key', 'password', 'credential', 'api_key', 'apikey')
    PERMISSION_VARS = ('_pipeline_bound_plugins', '_authorized', '_permission')
    EVENT_DATA_MAX_STRING_BYTES = 512

    @classmethod
    def query_to_event(
        cls,
        query: pipeline_query.Query,
    ) -> AgentEventEnvelope:
        """Convert Query to AgentEventEnvelope.

        Args:
            query: Current entry query

        Returns:
            AgentEventEnvelope for event-first processing
        """
        # Build event context
        event = cls._build_event_context(query)

        # Build conversation context
        conversation = cls._build_conversation_context(query)

        # Build actor context
        actor = cls._build_actor_context(query)

        # Build subject context
        subject = cls._build_subject_context(query)

        # Build input
        input = cls._build_input(query)

        # Build delivery context
        delivery = cls._build_delivery_context(query)

        # Build raw ref
        raw_ref = cls._build_raw_ref(query)

        return AgentEventEnvelope(
            event_id=event.event_id or str(query.query_id),
            event_type=event.event_type or runner_events.MESSAGE_RECEIVED,
            event_time=event.event_time,
            source='host_adapter',
            source_event_type=event.source_event_type,
            bot_id=query.bot_uuid,
            workspace_id=None,  # Not available in Query
            conversation_id=conversation.conversation_id,
            thread_id=conversation.thread_id,
            actor=actor,
            subject=subject,
            input=input,
            delivery=delivery,
            raw_ref=raw_ref,
            data=event.data,
        )

    @classmethod
    def config_to_agent_config(
        cls,
        query: pipeline_query.Query,
        runner_id: str,
    ) -> AgentConfig:
        """Project the current Pipeline config container into target Agent config."""
        pipeline_config = query.pipeline_config or {}
        runner_config = RunnerConfigResolver.resolve_runner_config(pipeline_config, runner_id)
        agent_id = getattr(query, 'pipeline_uuid', None)

        resource_policy = ResourcePolicyProjector.from_runner_config(
            runner_config,
            resolved_model_uuids=cls._extract_allowed_models(query),
            resolved_tool_names=cls._extract_allowed_tools(query),
            resolved_tool_sources=cls._extract_allowed_tool_sources(query),
            resolved_kb_uuids=cls._extract_allowed_kbs(query),
            resolved_skill_names=cls._extract_allowed_skills(query),
        )

        # Build state policy
        state_policy = StatePolicy(
            enable_state=True,
            state_scopes=['conversation', 'actor', 'subject', 'runner'],
        )

        # Build delivery policy
        delivery_policy = DeliveryPolicy(
            enable_streaming=True,
            enable_reply=True,
        )

        return AgentConfig(
            agent_id=agent_id,
            runner_id=runner_id,
            runner_config=runner_config,
            resource_policy=resource_policy,
            state_policy=state_policy,
            delivery_policy=delivery_policy,
            event_types=[runner_events.MESSAGE_RECEIVED],
            enabled=True,
            metadata={'source': 'pipeline_adapter'},
        )

    @classmethod
    def build_adapter_context(
        cls,
        query: pipeline_query.Query,
        binding: AgentBinding,
    ) -> dict[str, typing.Any]:
        """Build Query-derived fields for the current entry adapter."""
        return {
            'params': cls.build_params(query),
            'query_id': getattr(query, 'query_id', None),
        }

    @classmethod
    def build_params(cls, query: pipeline_query.Query) -> dict[str, typing.Any]:
        """Build adapter params from Pipeline variables with host filtering."""
        params: dict[str, typing.Any] = {}
        variables = getattr(query, 'variables', None)
        if not variables:
            return params

        for key, value in variables.items():
            if key.startswith(cls.INTERNAL_PREFIX):
                continue
            key_lower = key.lower()
            if any(pattern in key_lower for pattern in cls.SENSITIVE_PATTERNS):
                continue
            if any(key == perm_var or key.startswith(perm_var) for perm_var in cls.PERMISSION_VARS):
                continue
            if cls.is_json_serializable(value):
                params[key] = value

        return params

    @classmethod
    def is_json_serializable(cls, value: typing.Any) -> bool:
        """Return whether a value can safely cross the adapter boundary as JSON."""
        if value is None or isinstance(value, (str, int, float, bool)):
            return True
        if isinstance(value, (list, tuple)):
            return all(cls.is_json_serializable(item) for item in value)
        if isinstance(value, dict):
            return all(isinstance(k, str) and cls.is_json_serializable(v) for k, v in value.items())
        return False

    # Private helper methods

    @classmethod
    def _build_event_context(
        cls,
        query: pipeline_query.Query,
    ) -> AgentEventContext:
        """Build AgentEventContext from Query."""
        message_event = getattr(query, 'message_event', None)

        event_data: dict[str, typing.Any] = {}
        if message_event and hasattr(message_event, 'model_dump'):
            try:
                raw_event_data = message_event.model_dump(mode='json')
            except TypeError:
                raw_event_data = message_event.model_dump()
            except Exception:
                raw_event_data = {}
            if isinstance(raw_event_data, dict):
                event_data = cls._compact_event_data(raw_event_data)

        source_event_type = None
        if message_event:
            source_event_type = getattr(message_event, 'type', None)

        message_chain = getattr(query, 'message_chain', None)
        message_id = getattr(message_chain, 'message_id', None)
        if message_id == -1:
            message_id = None

        event_time = None
        if message_event:
            event_time = getattr(message_event, 'time', None)
        if isinstance(event_time, (int, float)):
            event_time = int(event_time)

        source_event_id = str(message_id or query.query_id)
        return AgentEventContext(
            event_id=cls._build_scoped_event_id(query, source_event_id, event_time),
            event_type=runner_events.MESSAGE_RECEIVED,
            event_time=event_time,
            source='host_adapter',
            source_event_type=source_event_type,
            data=event_data,
        )

    @classmethod
    def _compact_event_data(
        cls,
        event_data: dict[str, typing.Any],
    ) -> dict[str, typing.Any]:
        """Keep only small scalar source-event metadata in event.data."""
        compact: dict[str, typing.Any] = {}
        for key, value in event_data.items():
            if key == 'source_platform_object' or key.startswith('_'):
                continue
            if value is None or isinstance(value, (bool, int, float)):
                compact[key] = value
                continue
            if isinstance(value, str):
                if len(value.encode('utf-8')) <= cls.EVENT_DATA_MAX_STRING_BYTES:
                    compact[key] = value
                continue
        return compact

    @classmethod
    def _build_scoped_event_id(
        cls,
        query: pipeline_query.Query,
        source_event_id: str,
        event_time: int | None,
    ) -> str:
        """Build a globally unique host event id from pipeline-local ids."""
        launcher_type = getattr(query, 'launcher_type', None)
        launcher_type_value = getattr(launcher_type, 'value', launcher_type) if launcher_type is not None else None
        scope_parts = [
            'host_adapter',
            getattr(query, 'pipeline_uuid', None),
            getattr(query, 'bot_uuid', None),
            launcher_type_value,
            getattr(query, 'launcher_id', None),
            getattr(query, 'sender_id', None),
            source_event_id,
            event_time,
        ]
        scoped = '|'.join('' if part is None else str(part) for part in scope_parts)
        digest = hashlib.sha256(scoped.encode('utf-8')).hexdigest()[:32]
        return f'host:{digest}'

    @classmethod
    def _build_conversation_context(
        cls,
        query: pipeline_query.Query,
    ) -> ConversationContext:
        """Build ConversationContext from Query."""
        # Handle launcher_type safely
        launcher_type = getattr(query, 'launcher_type', None)
        launcher_type_value = None
        if launcher_type is not None:
            launcher_type_value = getattr(launcher_type, 'value', launcher_type)

        # Handle launcher_id
        launcher_id = getattr(query, 'launcher_id', None)

        # Build session_id from launcher info if available
        session_id = None
        if launcher_type_value and launcher_id:
            session_id = f'{launcher_type_value}_{launcher_id}'

        # Handle session and conversation_id
        conversation_id = None
        session = getattr(query, 'session', None)
        if session:
            conversation = getattr(session, 'using_conversation', None)
            if conversation:
                conversation_id = getattr(conversation, 'uuid', None)

        if not conversation_id:
            variables = getattr(query, 'variables', None) or {}
            conversation_id = variables.get('conversation_id') or None

        if not conversation_id:
            conversation_id = session_id

        # Handle sender_id
        sender_id = getattr(query, 'sender_id', None)
        if sender_id is not None:
            sender_id = str(sender_id)

        # Handle bot_uuid
        bot_uuid = getattr(query, 'bot_uuid', None)

        return ConversationContext(
            conversation_id=str(conversation_id) if conversation_id is not None else None,
            thread_id=None,
            launcher_type=launcher_type_value,
            launcher_id=launcher_id,
            sender_id=sender_id,
            bot_id=bot_uuid,
            workspace_id=None,
            session_id=session_id,
        )

    @classmethod
    def _build_actor_context(
        cls,
        query: pipeline_query.Query,
    ) -> ActorContext:
        """Build ActorContext from Query."""
        message_event = getattr(query, 'message_event', None)
        sender = getattr(message_event, 'sender', None) if message_event else None
        sender_id = getattr(query, 'sender_id', None)
        actor_id = getattr(sender, 'id', None) if sender else None
        if actor_id is None:
            actor_id = sender_id
        actor_name = sender.get_name() if sender and hasattr(sender, 'get_name') else None

        return ActorContext(
            actor_type='user',
            actor_id=str(actor_id) if actor_id is not None else None,
            actor_name=actor_name,
            metadata={},
        )

    @classmethod
    def _build_subject_context(
        cls,
        query: pipeline_query.Query,
    ) -> SubjectContext:
        """Build SubjectContext from Query."""
        message_chain = getattr(query, 'message_chain', None)
        message_id = getattr(message_chain, 'message_id', None) if message_chain else None
        if message_id == -1:
            message_id = None

        query_id = getattr(query, 'query_id', None)

        # Safely get launcher_type
        launcher_type = getattr(query, 'launcher_type', None)
        launcher_type_value = None
        if launcher_type is not None:
            launcher_type_value = getattr(launcher_type, 'value', launcher_type)

        return SubjectContext(
            subject_type='message',
            subject_id=str(message_id or query_id or ''),
            data={
                'launcher_type': launcher_type_value,
                'launcher_id': getattr(query, 'launcher_id', None),
                'sender_id': str(getattr(query, 'sender_id', '')) if getattr(query, 'sender_id', None) else None,
                'bot_uuid': getattr(query, 'bot_uuid', None),
            },
        )

    @classmethod
    def _build_input(
        cls,
        query: pipeline_query.Query,
    ) -> AgentInput:
        """Build AgentInput from Query."""
        text = None
        text_parts: list[str] = []
        contents: list[dict[str, typing.Any]] = []

        user_message = getattr(query, 'user_message', None)
        if user_message:
            content = getattr(user_message, 'content', None)
            if isinstance(content, list):
                for elem in content:
                    elem_dict = None
                    if hasattr(elem, 'model_dump'):
                        elem_dict = elem.model_dump(mode='json')
                    elif isinstance(elem, dict):
                        elem_dict = elem

                    if not isinstance(elem_dict, dict):
                        continue

                    contents.append(elem_dict)
                    if elem_dict.get('type') == 'text':
                        elem_text = elem_dict.get('text')
                        if elem_text:
                            text_parts.append(elem_text)
            elif content is not None:
                text = str(content)
                contents.append({'type': 'text', 'text': text})

        if not contents:
            message_chain = getattr(query, 'message_chain', None) or []
            for component in message_chain:
                if isinstance(component, platform_message.Plain):
                    component_text = getattr(component, 'text', '')
                    if component_text:
                        text_parts.append(component_text)
                        contents.append({'type': 'text', 'text': component_text})
                elif isinstance(component, platform_message.Image):
                    image_base64 = getattr(component, 'base64', None)
                    image_url = getattr(component, 'url', None)
                    if image_base64:
                        contents.append({'type': 'image_base64', 'image_base64': image_base64})
                    elif image_url:
                        contents.append({'type': 'image_url', 'image_url': {'url': image_url}})

        if text_parts:
            text = ''.join(text_parts)

        attachments = cls._build_attachments(query, contents)

        return AgentInput(
            text=text,
            contents=contents,
            attachments=attachments,
        )

    @classmethod
    def _build_attachments(
        cls,
        query: pipeline_query.Query,
        contents: list[dict[str, typing.Any]],
    ) -> list[dict[str, typing.Any]]:
        """Extract attachments from query."""
        attachments: list[dict[str, typing.Any]] = []
        seen_keys: dict[tuple[str, str, str], set[str]] = {}

        def add_attachment(attachment: dict[str, typing.Any]) -> None:
            key = cls._attachment_dedupe_key(attachment)
            if key is not None:
                source = str(attachment.get('source') or '')
                sources = seen_keys.setdefault(key, set())
                if source and sources and source not in sources:
                    return
                if source:
                    sources.add(source)
            attachments.append(attachment)

        for elem in contents:
            elem_type = elem.get('type')

            if elem_type == 'image_url':
                image_url = elem.get('image_url') or {}
                add_attachment(
                    {
                        'type': 'image',
                        'source': 'url',
                        'url': image_url.get('url') if isinstance(image_url, dict) else str(image_url),
                    }
                )
            elif elem_type == 'image_base64':
                add_attachment(
                    {
                        'type': 'image',
                        'source': 'base64',
                        'content': elem.get('image_base64'),
                    }
                )
            elif elem_type == 'file_url':
                add_attachment(
                    {
                        'type': 'file',
                        'source': 'url',
                        'url': elem.get('file_url'),
                        'name': elem.get('file_name'),
                    }
                )
            elif elem_type == 'file_base64':
                add_attachment(
                    {
                        'type': 'file',
                        'source': 'base64',
                        'content': elem.get('file_base64'),
                        'name': elem.get('file_name'),
                    }
                )

        message_chain = getattr(query, 'message_chain', None)
        if message_chain:
            try:
                message_components = iter(message_chain)
            except TypeError:
                message_components = iter(())

            for component in message_components:
                if isinstance(component, platform_message.Image):
                    image_id = component.image_id or None
                    image_url = component.url or None
                    image_base64 = component.base64 or None
                    add_attachment(
                        {
                            'type': 'image',
                            'source': 'message_chain',
                            'id': image_id,
                            'url': image_url,
                            'content': image_base64,
                        }
                    )
                elif isinstance(component, platform_message.File):
                    add_attachment(
                        {
                            'type': 'file',
                            'source': 'message_chain',
                            'id': component.id or None,
                            'name': component.name or None,
                            'url': component.url or None,
                            'content': component.base64 or None,
                        }
                    )
                elif isinstance(component, platform_message.Voice):
                    add_attachment(
                        {
                            'type': 'voice',
                            'source': 'message_chain',
                            'id': component.voice_id or None,
                            'url': component.url or None,
                            'content': component.base64 or None,
                        }
                    )

        return attachments

    @classmethod
    def _attachment_dedupe_key(
        cls,
        attachment: dict[str, typing.Any],
    ) -> tuple[str, str, str] | None:
        """Return a stable key for the same attachment across content sources."""
        attachment_type = attachment.get('type')
        if not attachment_type:
            return None
        for field in ('id', 'url', 'content'):
            value = attachment.get(field)
            if value:
                if field == 'content':
                    value = hashlib.sha256(str(value).encode('utf-8')).hexdigest()
                return str(attachment_type), field, str(value)
        return None

    @classmethod
    def _build_delivery_context(
        cls,
        query: pipeline_query.Query,
    ) -> DeliveryContext:
        """Build DeliveryContext from Query."""
        message_chain = getattr(query, 'message_chain', None)
        return DeliveryContext(
            surface='platform',
            reply_target={
                'message_id': getattr(message_chain, 'message_id', None),
            },
            supports_streaming=True,
            supports_edit=False,
            supports_reaction=False,
            platform_capabilities={},
        )

    @classmethod
    def _build_raw_ref(
        cls,
        query: pipeline_query.Query,
    ) -> RawEventRef | None:
        """Build RawEventRef from Query."""
        # For now, we don't store raw event payload
        return None

    @classmethod
    def _extract_allowed_models(
        cls,
        query: pipeline_query.Query,
    ) -> list[str] | None:
        """Extract allowed model UUIDs from query."""
        model_uuids: list[str] = []
        model_uuid = getattr(query, 'use_llm_model_uuid', None)
        if model_uuid:
            model_uuids.append(model_uuid)

        variables = getattr(query, 'variables', None) or {}
        for fallback_uuid in variables.get('_fallback_model_uuids', []) or []:
            if fallback_uuid and fallback_uuid not in model_uuids:
                model_uuids.append(fallback_uuid)

        return model_uuids or None

    @classmethod
    def _extract_allowed_tools(
        cls,
        query: pipeline_query.Query,
    ) -> list[str] | None:
        """Extract allowed tool names from query."""
        use_funcs = getattr(query, 'use_funcs', None)
        if use_funcs is None:
            return None
        try:
            return ResourcePolicyProjector.extract_tool_names(use_funcs)
        except (TypeError, AttributeError):
            return []

    @classmethod
    def _extract_allowed_tool_sources(
        cls,
        query: pipeline_query.Query,
    ) -> dict[str, typing.Any] | None:
        """Extract the Host-frozen implementation for each allowed tool."""
        variables = getattr(query, 'variables', None)
        if not isinstance(variables, dict):
            return None
        refs = variables.get(TOOL_SOURCE_REFS_QUERY_KEY)
        return refs if isinstance(refs, dict) else None

    @classmethod
    def _extract_allowed_kbs(
        cls,
        query: pipeline_query.Query,
    ) -> list[str] | None:
        """Extract allowed knowledge base UUIDs from query."""
        variables = getattr(query, 'variables', None)
        if not variables:
            return None
        if '_knowledge_base_uuids' not in variables:
            return None
        return ResourcePolicyProjector.normalize_names(variables.get('_knowledge_base_uuids'))

    @classmethod
    def _extract_allowed_skills(
        cls,
        query: pipeline_query.Query,
    ) -> list[str] | None:
        """Extract pipeline-visible skill names from query."""
        variables = getattr(query, 'variables', None)
        if not variables or '_pipeline_bound_skills' not in variables:
            return None
        bound_skills = variables.get('_pipeline_bound_skills')
        if bound_skills is None:
            return None
        if not isinstance(bound_skills, list):
            return []
        return [str(skill_name) for skill_name in bound_skills if skill_name]
