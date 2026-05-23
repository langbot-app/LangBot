"""Pipeline compatibility adapter for converting Query to event-first envelope.

This adapter bridges the legacy Query/Pipeline approach with the new
event-first Protocol v1 architecture. It is a compatibility layer only.
"""
from __future__ import annotations

import typing
import time

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
from langbot_plugin.api.entities.builtin.agent_runner.trigger import AgentTrigger

from .host_models import (
    AgentEventEnvelope,
    AgentBinding,
    BindingScope,
    ResourcePolicy,
    StatePolicy,
    DeliveryPolicy,
)
from . import events as runner_events


class PipelineCompatAdapter:
    """Adapter for converting Pipeline Query to event-first envelope.

    This adapter is responsible for:
    - Converting Query to AgentEventEnvelope
    - Converting Pipeline config to temporary AgentBinding
    - Handling legacy max-round as bootstrap policy
    - Putting Query-only fields into compatibility context
    """

    @classmethod
    def query_to_event(
        cls,
        query: pipeline_query.Query,
    ) -> AgentEventEnvelope:
        """Convert Pipeline Query to AgentEventEnvelope.

        Args:
            query: Pipeline query

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
            source="pipeline_compat",
            bot_id=query.bot_uuid,
            workspace_id=None,  # Not available in Query
            conversation_id=conversation.conversation_id,
            thread_id=conversation.thread_id,
            actor=actor,
            subject=subject,
            input=input,
            delivery=delivery,
            raw_ref=raw_ref,
        )

    @classmethod
    def pipeline_config_to_binding(
        cls,
        query: pipeline_query.Query,
        runner_id: str,
    ) -> AgentBinding:
        """Convert Pipeline config to temporary AgentBinding.

        Args:
            query: Pipeline query
            runner_id: Resolved runner ID

        Returns:
            AgentBinding for this run
        """
        pipeline_config = query.pipeline_config or {}
        ai_config = pipeline_config.get('ai', {})
        runner_config = ai_config.get('runner_config', {}).get(runner_id, {})

        # Extract max_round for compatibility (used in bootstrap, not Protocol v1)
        max_round = runner_config.get('max_round') or ai_config.get('max-round')

        # Build scope
        scope = BindingScope(
            scope_type="pipeline",
            scope_id=query.pipeline_uuid,
        )

        # Build resource policy from pipeline config
        resource_policy = ResourcePolicy(
            allowed_model_uuids=cls._extract_allowed_models(query),
            allowed_tool_names=cls._extract_allowed_tools(query),
            allowed_kb_uuids=cls._extract_allowed_kbs(query),
        )

        # Build state policy
        state_policy = StatePolicy(
            enable_state=True,
            state_scopes=["conversation", "actor", "subject", "runner"],
        )

        # Build delivery policy
        output_config = pipeline_config.get('output', {})
        delivery_policy = DeliveryPolicy(
            enable_streaming=True,
            enable_reply=True,
        )

        return AgentBinding(
            binding_id=f"pipeline_{query.pipeline_uuid or 'default'}_{runner_id}",
            scope=scope,
            event_types=[runner_events.MESSAGE_RECEIVED],
            runner_id=runner_id,
            runner_config=runner_config,
            resource_policy=resource_policy,
            state_policy=state_policy,
            delivery_policy=delivery_policy,
            enabled=True,
            pipeline_uuid=query.pipeline_uuid,
            max_round=max_round,
        )

    @classmethod
    def build_bootstrap_from_binding(
        cls,
        query: pipeline_query.Query,
        binding: AgentBinding,
    ) -> dict[str, typing.Any]:
        """Build bootstrap context from binding for legacy max-round.

        This method handles the legacy max-round -> bootstrap conversion.
        max-round is NOT part of Protocol v1, only used by compatibility adapter.

        Args:
            query: Pipeline query
            binding: Agent binding with max_round

        Returns:
            Bootstrap context data
        """
        max_round = binding.max_round

        # If no max_round or self_managed_context, return empty bootstrap
        if max_round is None or max_round <= 0:
            return {
                "messages": [],
                "summary": None,
                "artifacts": [],
                "metadata": {
                    "policy": "self_managed",
                    "legacy_max_round": None,
                },
            }

        # Legacy max-round packaging (will be handled by context_packager)
        return {
            "messages": [],  # Will be filled by context_packager
            "summary": None,
            "artifacts": [],
            "metadata": {
                "policy": "legacy_max_round",
                "legacy_max_round": max_round,
            },
        }

    @classmethod
    def build_compatibility_context(
        cls,
        query: pipeline_query.Query,
    ) -> dict[str, typing.Any]:
        """Build compatibility context for legacy Query/Pipeline fields.

        These fields are for migration purposes only.
        Runners should NOT depend on them for long-term capabilities.

        Args:
            query: Pipeline query

        Returns:
            Compatibility context data
        """
        return {
            "query_id": query.query_id,
            "pipeline_uuid": query.pipeline_uuid,
            "max_round": None,  # Moved to binding, not here
            "legacy_messages": [],  # Will be filled by context_packager
            "extra": {
                "bot_uuid": query.bot_uuid,
                "sender_id": str(query.sender_id) if query.sender_id else None,
                "launcher_type": query.launcher_type.value if query.launcher_type else None,
                "launcher_id": query.launcher_id,
            },
        }

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
                event_data = message_event.model_dump(mode='json')
            except TypeError:
                event_data = message_event.model_dump()
            except Exception:
                event_data = {}
            event_data.pop('source_platform_object', None)

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

        return AgentEventContext(
            event_id=str(message_id or query.query_id),
            event_type=runner_events.MESSAGE_RECEIVED,
            event_time=event_time,
            source="pipeline_compat",
            source_event_type=source_event_type,
            data=event_data,
        )

    @classmethod
    def _build_conversation_context(
        cls,
        query: pipeline_query.Query,
    ) -> ConversationContext:
        """Build ConversationContext from Query."""
        # Handle session and conversation_id
        conversation_id = None
        session = getattr(query, 'session', None)
        if session:
            conversation = getattr(session, 'using_conversation', None)
            if conversation:
                conversation_id = getattr(conversation, 'uuid', None)

        # Handle launcher_type safely
        launcher_type = getattr(query, 'launcher_type', None)
        launcher_type_value = None
        if launcher_type is not None:
            launcher_type_value = getattr(launcher_type, 'value', launcher_type)

        # Handle launcher_id
        launcher_id = getattr(query, 'launcher_id', None)

        # Handle sender_id
        sender_id = getattr(query, 'sender_id', None)
        if sender_id is not None:
            sender_id = str(sender_id)

        # Handle bot_uuid
        bot_uuid = getattr(query, 'bot_uuid', None)

        # Handle pipeline_uuid
        pipeline_uuid = getattr(query, 'pipeline_uuid', None)

        # Build session_id from launcher info if available
        session_id = None
        if launcher_type_value and launcher_id:
            session_id = f'{launcher_type_value}_{launcher_id}'

        return ConversationContext(
            conversation_id=conversation_id,
            thread_id=None,
            launcher_type=launcher_type_value,
            launcher_id=launcher_id,
            sender_id=sender_id,
            bot_id=bot_uuid,
            workspace_id=None,
            session_id=session_id,
            pipeline_uuid=pipeline_uuid,
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
            actor_type="user",
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
            subject_type="message",
            subject_id=str(message_id or query_id or ''),
            data={
                "launcher_type": launcher_type_value,
                "launcher_id": getattr(query, 'launcher_id', None),
                "sender_id": str(getattr(query, 'sender_id', '')) if getattr(query, 'sender_id', None) else None,
                "bot_uuid": getattr(query, 'bot_uuid', None),
                "pipeline_uuid": getattr(query, 'pipeline_uuid', None),
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
                    # Handle both real objects and mocks
                    if hasattr(elem, 'model_dump'):
                        contents.append(elem.model_dump(mode='json'))
                    elif isinstance(elem, dict):
                        contents.append(elem)
                    else:
                        # For mocks, extract type and text attributes
                        elem_type = getattr(elem, 'type', None)
                        if elem_type == 'text':
                            elem_text = getattr(elem, 'text', None)
                            contents.append({'type': 'text', 'text': elem_text})
                            if elem_text:
                                text_parts.append(elem_text)
                        continue

                    # Extract text for the text field
                    if hasattr(elem, 'type') and getattr(elem, 'type', None) == 'text':
                        elem_text = getattr(elem, 'text', None)
                        if elem_text:
                            text_parts.append(elem_text)
            elif content is not None:
                text = str(content)
                contents.append({'type': 'text', 'text': text})

        if text_parts:
            text = ''.join(text_parts)

        message_chain_dict = None
        message_chain = getattr(query, 'message_chain', None)
        if message_chain:
            if hasattr(message_chain, 'model_dump'):
                message_chain_dict = message_chain.model_dump(mode='json')

        attachments = cls._build_attachments(query, contents)

        return AgentInput(
            text=text,
            contents=contents,
            message_chain=message_chain_dict,
            attachments=attachments,
        )

    @classmethod
    def _build_attachments(
        cls,
        query: pipeline_query.Query,
        contents: list[dict[str, typing.Any]],
    ) -> list[dict[str, typing.Any]]:
        """Extract attachments from query."""
        import uuid

        attachments: list[dict[str, typing.Any]] = []

        for elem in contents:
            elem_type = elem.get('type')
            artifact_id = str(uuid.uuid4())  # Generate unique ID

            if elem_type == 'image_url':
                image_url = elem.get('image_url') or {}
                attachments.append({
                    'artifact_id': artifact_id,
                    'artifact_type': 'image',
                    'source': 'url',
                    'url': image_url.get('url') if isinstance(image_url, dict) else str(image_url),
                })
            elif elem_type == 'image_base64':
                attachments.append({
                    'artifact_id': artifact_id,
                    'artifact_type': 'image',
                    'source': 'base64',
                    'content': elem.get('image_base64'),
                })
            elif elem_type == 'file_url':
                attachments.append({
                    'artifact_id': artifact_id,
                    'artifact_type': 'file',
                    'source': 'url',
                    'url': elem.get('file_url'),
                    'name': elem.get('file_name'),
                })
            elif elem_type == 'file_base64':
                attachments.append({
                    'artifact_id': artifact_id,
                    'artifact_type': 'file',
                    'source': 'base64',
                    'content': elem.get('file_base64'),
                    'name': elem.get('file_name'),
                })

        message_chain = getattr(query, 'message_chain', None)
        if message_chain:
            try:
                for component in message_chain:
                    artifact_id = str(uuid.uuid4())  # Generate unique ID

                    if isinstance(component, platform_message.Image):
                        attachments.append({
                            'artifact_id': artifact_id,
                            'artifact_type': 'image',
                            'source': 'message_chain',
                            'id': component.image_id or None,
                            'url': component.url or None,
                        })
                    elif isinstance(component, platform_message.File):
                        attachments.append({
                            'artifact_id': artifact_id,
                            'artifact_type': 'file',
                            'source': 'message_chain',
                            'id': component.id or None,
                            'name': component.name or None,
                        })
                    elif isinstance(component, platform_message.Voice):
                        attachments.append({
                            'artifact_id': artifact_id,
                            'artifact_type': 'voice',
                            'source': 'message_chain',
                            'id': component.voice_id or None,
                            'url': component.url or None,
                        })
            except TypeError:
                # message_chain is not iterable (e.g., a Mock object)
                pass

        return attachments

    @classmethod
    def _build_delivery_context(
        cls,
        query: pipeline_query.Query,
    ) -> DeliveryContext:
        """Build DeliveryContext from Query."""
        return DeliveryContext(
            surface="platform",
            reply_target={
                "message_id": getattr(query.message_chain, 'message_id', None),
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
        model_uuid = getattr(query, 'use_llm_model_uuid', None)
        if model_uuid:
            return [model_uuid]
        return None

    @classmethod
    def _extract_allowed_tools(
        cls,
        query: pipeline_query.Query,
    ) -> list[str] | None:
        """Extract allowed tool names from query."""
        use_funcs = getattr(query, 'use_funcs', None)
        if not use_funcs:
            return None
        try:
            return [func.get('name') for func in use_funcs if isinstance(func, dict) and func.get('name')]
        except (TypeError, AttributeError):
            return None

    @classmethod
    def _extract_allowed_kbs(
        cls,
        query: pipeline_query.Query,
    ) -> list[str] | None:
        """Extract allowed knowledge base UUIDs from query."""
        variables = getattr(query, 'variables', None)
        if not variables:
            return None
        kb_uuids = variables.get('_knowledge_base_uuids')
        if kb_uuids:
            return kb_uuids
        return None
