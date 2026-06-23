from __future__ import annotations

import asyncio
import json
import re
import time
import traceback
import typing
import uuid
import sqlalchemy

from ..core import app, entities as core_entities, taskmgr

from ..discover import engine

from ..entity.persistence import bot as persistence_bot
from ..entity.persistence import pipeline as persistence_pipeline

from ..entity.errors import platform as platform_errors
from ..agent.runner.host_models import (
    AgentBinding,
    AgentEventEnvelope,
    BindingScope,
    DeliveryPolicy,
    ResourcePolicy,
    StatePolicy,
)

from .logger import EventLogger

import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.events as plugin_events
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot_plugin.api.entities.builtin.agent_runner.event import (
    ActorContext,
    SubjectContext,
    RawEventRef,
)
from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput
from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext


class RuntimeBot:
    """运行时机器人"""

    ap: app.Application

    bot_entity: persistence_bot.Bot

    enable: bool

    adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter

    task_wrapper: taskmgr.TaskWrapper

    task_context: taskmgr.TaskContext

    logger: EventLogger

    def __init__(
        self,
        ap: app.Application,
        bot_entity: persistence_bot.Bot,
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        logger: EventLogger,
    ):
        self.ap = ap
        self.bot_entity = bot_entity
        self.enable = bot_entity.enable
        self.adapter = adapter
        self.task_context = taskmgr.TaskContext()
        self.logger = logger

    @staticmethod
    def _match_operator(actual: str, operator: str, expected: str) -> bool:
        """Evaluate a single operator condition."""
        if operator == 'eq':
            return actual == expected
        elif operator == 'neq':
            return actual != expected
        elif operator == 'contains':
            return expected in actual
        elif operator == 'not_contains':
            return expected not in actual
        elif operator == 'starts_with':
            return actual.startswith(expected)
        elif operator == 'regex':
            try:
                return bool(re.search(expected, actual))
            except re.error:
                return False
        return False

    PIPELINE_DISCARD = '__discard__'
    PIPELINE_DISCARD_DISPLAY_NAME = 'Discarded'
    EVENT_DATA_MAX_STRING_BYTES = 512

    @staticmethod
    def _eba_event_to_plugin_event(event: platform_events.EBAEvent) -> plugin_events.BaseEventModel | None:
        """Map a platform EBA event to a plugin EventListener event model."""
        event_mapping: list[tuple[type[platform_events.EBAEvent], type[plugin_events.BaseEventModel]]] = [
            (platform_events.MessageReceivedEvent, plugin_events.MessageReceived),
            (platform_events.MessageEditedEvent, plugin_events.MessageEdited),
            (platform_events.MessageDeletedEvent, plugin_events.MessageDeleted),
            (platform_events.MessageReactionEvent, plugin_events.MessageReactionReceived),
            (platform_events.FeedbackReceivedEvent, plugin_events.FeedbackReceived),
            (platform_events.MemberJoinedEvent, plugin_events.GroupMemberJoined),
            (platform_events.MemberLeftEvent, plugin_events.GroupMemberLeft),
            (platform_events.MemberBannedEvent, plugin_events.GroupMemberBanned),
            (platform_events.BotInvitedToGroupEvent, plugin_events.BotInvitedToGroup),
            (platform_events.BotRemovedFromGroupEvent, plugin_events.BotRemovedFromGroup),
            (platform_events.BotMutedEvent, plugin_events.BotMuted),
            (platform_events.BotUnmutedEvent, plugin_events.BotUnmuted),
            (platform_events.PlatformSpecificEvent, plugin_events.PlatformSpecificEventReceived),
        ]

        for platform_event_type, plugin_event_type in event_mapping:
            if isinstance(event, platform_event_type):
                return plugin_event_type.from_platform_event(event)

        return None

    @staticmethod
    def _match_event_pattern(event_type: str, pattern: str) -> bool:
        if not event_type or not pattern:
            return False
        if pattern == '*':
            return True
        if pattern.endswith('.*'):
            return event_type.startswith(f'{pattern[:-2]}.')
        return event_type == pattern

    @classmethod
    def _is_message_event_type(cls, event_type: str) -> bool:
        return cls._match_event_pattern(event_type, 'message.*')

    @classmethod
    def _agent_supports_event_type(
        cls,
        supported_patterns: list[str] | None,
        event_type: str,
    ) -> bool:
        return any(cls._match_event_pattern(event_type, pattern) for pattern in (supported_patterns or ['*']))

    @staticmethod
    def _get_nested_value(data: dict[str, typing.Any], path: str) -> typing.Any:
        current: typing.Any = data
        for key in path.split('.'):
            if isinstance(current, dict):
                current = current.get(key)
            else:
                current = getattr(current, key, None)
            if current is None:
                return None
        return current

    @classmethod
    def _match_event_filter(
        cls,
        event_data: dict[str, typing.Any],
        event_filter: dict[str, typing.Any],
    ) -> bool:
        field = str(event_filter.get('field') or event_filter.get('path') or '').strip()
        if not field:
            return True

        operator = str(event_filter.get('operator') or 'eq')
        expected = event_filter.get('value')
        actual = cls._get_nested_value(event_data, field)

        if operator == 'eq':
            return actual == expected
        if operator == 'neq':
            return actual != expected
        if operator == 'contains':
            if isinstance(actual, (list, tuple, set)):
                return expected in actual
            return str(expected) in str(actual or '')
        if operator == 'not_contains':
            if isinstance(actual, (list, tuple, set)):
                return expected not in actual
            return str(expected) not in str(actual or '')
        if operator == 'starts_with':
            return str(actual or '').startswith(str(expected))
        if operator == 'regex':
            try:
                return bool(re.search(str(expected), str(actual or '')))
            except re.error:
                return False
        return False

    @classmethod
    def _match_event_filters(
        cls,
        event: platform_events.EBAEvent,
        filters: typing.Any,
    ) -> bool:
        if not filters:
            return True
        if not isinstance(filters, list):
            return False

        event_data = cls._safe_model_dump(event)
        return all(
            cls._match_event_filter(event_data, event_filter)
            for event_filter in filters
            if isinstance(event_filter, dict)
        )

    def _resolve_eba_event_binding(
        self,
        event: platform_events.EBAEvent,
        event_type: str,
    ) -> dict[str, typing.Any] | None:
        """Resolve the highest priority Bot event binding for a platform event."""
        raw_bindings = self.bot_entity.event_bindings or []
        if isinstance(raw_bindings, str):
            try:
                raw_bindings = json.loads(raw_bindings)
            except json.JSONDecodeError:
                raw_bindings = []
        if not isinstance(raw_bindings, list):
            return None

        matched: list[tuple[int, int, dict[str, typing.Any]]] = []
        for index, binding in enumerate(raw_bindings):
            if not isinstance(binding, dict) or not binding.get('enabled', True):
                continue

            event_pattern = str(binding.get('event_pattern') or '')
            if not self._match_event_pattern(event_type, event_pattern):
                continue
            if not self._match_event_filters(event, binding.get('filters')):
                continue

            priority = int(binding.get('priority') or 0)
            order = int(binding.get('order', index))
            matched.append((priority, -order, binding))

        if not matched:
            return None

        matched.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return matched[0][2]

    @staticmethod
    def _safe_model_dump(model: typing.Any) -> dict[str, typing.Any]:
        if model is None:
            return {}
        if hasattr(model, 'model_dump'):
            try:
                return model.model_dump(mode='json')
            except TypeError:
                try:
                    return model.model_dump()
                except Exception:
                    return {}
            except Exception:
                return {}
        if isinstance(model, dict):
            return model
        return {}

    @classmethod
    def _compact_event_data(cls, event: platform_events.EBAEvent) -> dict[str, typing.Any]:
        raw_event_data = cls._safe_model_dump(event)
        compact: dict[str, typing.Any] = {}
        for key, value in raw_event_data.items():
            if key == 'source_platform_object' or key.startswith('_'):
                continue
            if value is None or isinstance(value, (bool, int, float)):
                compact[key] = value
                continue
            if isinstance(value, str):
                if len(value.encode('utf-8')) <= cls.EVENT_DATA_MAX_STRING_BYTES:
                    compact[key] = value
                continue
            if isinstance(value, (list, dict)):
                try:
                    encoded = json.dumps(value, ensure_ascii=False)
                except (TypeError, ValueError):
                    continue
                if len(encoded.encode('utf-8')) <= cls.EVENT_DATA_MAX_STRING_BYTES:
                    compact[key] = value
        return compact

    @staticmethod
    def _get_entity_id(entity: typing.Any) -> str | None:
        entity_id = getattr(entity, 'id', None)
        if entity_id is None and isinstance(entity, dict):
            entity_id = entity.get('id')
        if entity_id is None or entity_id == '':
            return None
        return str(entity_id)

    @staticmethod
    def _get_entity_name(entity: typing.Any) -> str | None:
        if entity is None:
            return None
        if hasattr(entity, 'get_name'):
            try:
                name = entity.get_name()
                if name:
                    return str(name)
            except Exception:
                pass
        for attr in ('nickname', 'member_name', 'name', 'display_name'):
            value = getattr(entity, attr, None)
            if value:
                return str(value)
        if isinstance(entity, dict):
            for attr in ('nickname', 'member_name', 'name', 'display_name'):
                value = entity.get(attr)
                if value:
                    return str(value)
        return None

    @classmethod
    def _infer_actor_context(cls, event: platform_events.EBAEvent) -> ActorContext | None:
        actor = getattr(event, 'sender', None) or getattr(event, 'member', None) or getattr(event, 'user', None)
        actor_id = cls._get_entity_id(actor)
        actor_name = cls._get_entity_name(actor)

        if actor_id is None:
            user_id = getattr(event, 'user_id', None)
            if user_id:
                actor_id = str(user_id)

        if actor_id is None:
            return None

        return ActorContext(
            actor_type='user',
            actor_id=actor_id,
            actor_name=actor_name,
            metadata={},
        )

    @classmethod
    def _infer_subject_context(cls, event: platform_events.EBAEvent) -> SubjectContext:
        group = getattr(event, 'group', None)
        if group is not None:
            group_id = cls._get_entity_id(group)
            return SubjectContext(
                subject_type='group',
                subject_id=group_id,
                data={'group_name': cls._get_entity_name(group)},
            )

        message_id = getattr(event, 'message_id', None)
        if message_id:
            return SubjectContext(
                subject_type='message',
                subject_id=str(message_id),
                data={},
            )

        feedback_id = getattr(event, 'feedback_id', None)
        if feedback_id:
            return SubjectContext(
                subject_type='feedback',
                subject_id=str(feedback_id),
                data={'message_id': getattr(event, 'message_id', None)},
            )

        action = getattr(event, 'action', None)
        if action:
            return SubjectContext(
                subject_type='platform_action',
                subject_id=str(action),
                data={},
            )

        return SubjectContext(
            subject_type='event',
            subject_id=getattr(event, 'type', None),
            data={},
        )

    @staticmethod
    def _session_to_reply_target(session_id: str | None) -> tuple[str | None, str | None]:
        if not session_id or '_' not in session_id:
            return None, None
        target_type, target_id = session_id.split('_', 1)
        if target_type == 'person':
            target_type = 'person'
        elif target_type == 'group':
            target_type = 'group'
        else:
            return None, None
        return target_type, target_id or None

    @classmethod
    def _infer_reply_target(
        cls,
        event: platform_events.EBAEvent,
    ) -> tuple[str | None, str | None, dict[str, typing.Any]]:
        metadata: dict[str, typing.Any] = {}
        group = getattr(event, 'group', None)
        group_id = cls._get_entity_id(group)
        if group_id:
            metadata['group_id'] = group_id
            return 'group', group_id, metadata

        chat_id = getattr(event, 'chat_id', None)
        chat_type = getattr(event, 'chat_type', None)
        chat_type_value = getattr(chat_type, 'value', chat_type)
        if chat_id:
            metadata['chat_id'] = str(chat_id)
            if chat_type_value == 'group':
                return 'group', str(chat_id), metadata
            return 'person', str(chat_id), metadata

        session_target_type, session_target_id = cls._session_to_reply_target(getattr(event, 'session_id', None))
        if session_target_type and session_target_id:
            return session_target_type, session_target_id, metadata

        raw_data = getattr(event, 'data', None)
        if isinstance(raw_data, dict):
            target_type = raw_data.get('target_type') or raw_data.get('chat_type')
            target_id = (
                raw_data.get('target_id')
                or raw_data.get('chat_id')
                or raw_data.get('group_id')
                or raw_data.get('user_id')
            )
            if target_type and target_id:
                return str(target_type), str(target_id), metadata

        return None, None, metadata

    @classmethod
    def _build_agent_input(cls, event: platform_events.EBAEvent) -> AgentInput:
        text = None
        contents: list[dict[str, typing.Any]] = []

        message_chain = getattr(event, 'message_chain', None)
        if message_chain:
            text_parts: list[str] = []
            try:
                for component in message_chain:
                    if isinstance(component, platform_message.Plain):
                        text_parts.append(component.text)
                    elif isinstance(component, platform_message.Image):
                        if component.url:
                            contents.append({'type': 'image_url', 'image_url': {'url': component.url}})
                        elif component.base64:
                            contents.append({'type': 'image_base64', 'image_base64': component.base64})
            except TypeError:
                text_parts.append(str(message_chain))
            text = ''.join(text_parts) or str(message_chain)

        if text is None:
            feedback_content = getattr(event, 'feedback_content', None)
            if feedback_content:
                text = str(feedback_content)
            elif getattr(event, 'action', None):
                text = str(getattr(event, 'action'))
            else:
                text = str(getattr(event, 'type', 'event'))

        if text:
            contents.insert(0, {'type': 'text', 'text': text})

        return AgentInput(
            text=text,
            contents=contents,
            attachments=[],
        )

    def _eba_event_to_agent_envelope(
        self,
        event: platform_events.EBAEvent,
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
    ) -> AgentEventEnvelope:
        event_type = getattr(event, 'type', None) or event.__class__.__name__
        event_time = getattr(event, 'timestamp', None) or time.time()
        event_id = (
            getattr(event, 'message_id', None) or getattr(event, 'feedback_id', None) or f'{event_type}:{uuid.uuid4()}'
        )
        target_type, target_id, target_metadata = self._infer_reply_target(event)

        conversation_id = None
        if target_type and target_id:
            conversation_id = f'{target_type}_{target_id}'
        elif getattr(event, 'session_id', None):
            conversation_id = str(getattr(event, 'session_id'))

        return AgentEventEnvelope(
            event_id=f'platform:{self.bot_entity.uuid}:{event_id}',
            event_type=event_type,
            event_time=int(event_time) if isinstance(event_time, (int, float)) else None,
            source='platform',
            source_event_type=event_type,
            bot_id=self.bot_entity.uuid,
            workspace_id=None,
            conversation_id=conversation_id,
            thread_id=None,
            actor=self._infer_actor_context(event),
            subject=self._infer_subject_context(event),
            input=self._build_agent_input(event),
            delivery=DeliveryContext(
                surface='platform',
                reply_target={
                    'target_type': target_type,
                    'target_id': target_id,
                    'message_id': getattr(event, 'message_id', None),
                    **target_metadata,
                },
                supports_streaming=False,
                supports_edit=False,
                supports_reaction=False,
                platform_capabilities={
                    'adapter': adapter.__class__.__name__,
                    'event_type': event_type,
                },
            ),
            raw_ref=RawEventRef(ref_id=str(event_id), storage_key=None),
            data=self._compact_event_data(event),
        )

    @staticmethod
    def _agent_product_to_binding(
        agent: dict[str, typing.Any],
        event_binding: dict[str, typing.Any],
        event_type: str,
        bot_uuid: str,
    ) -> AgentBinding | None:
        config = agent.get('config') if isinstance(agent, dict) else None
        if not isinstance(config, dict):
            return None

        runner = config.get('runner')
        runner_id = None
        if isinstance(runner, dict):
            runner_id = runner.get('id')
        runner_id = runner_id or agent.get('component_ref')
        if not runner_id:
            return None

        runner_config_map = config.get('runner_config')
        runner_config = {}
        if isinstance(runner_config_map, dict):
            runner_config = runner_config_map.get(runner_id) or {}

        return AgentBinding(
            binding_id=f'bot:{bot_uuid}:{event_binding.get("id") or uuid.uuid4()}',
            scope=BindingScope(scope_type='bot', scope_id=bot_uuid),
            event_types=[event_type],
            runner_id=runner_id,
            runner_config=runner_config,
            resource_policy=ResourcePolicy(),
            state_policy=StatePolicy(state_scopes=['conversation', 'actor', 'subject', 'runner']),
            delivery_policy=DeliveryPolicy(enable_streaming=False, enable_reply=True),
            enabled=True,
            agent_id=agent.get('uuid'),
        )

    @staticmethod
    def _provider_content_to_text(content: typing.Any) -> str:
        if content is None:
            return ''
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                item_data = item.model_dump(mode='json') if hasattr(item, 'model_dump') else item
                if isinstance(item_data, dict):
                    if item_data.get('type') == 'text' and item_data.get('text') is not None:
                        parts.append(str(item_data.get('text')))
                    elif item_data.get('text') is not None:
                        parts.append(str(item_data.get('text')))
                elif item_data is not None:
                    parts.append(str(item_data))
            return ''.join(parts)
        return str(content)

    @classmethod
    def _provider_output_to_text(cls, result: provider_message.Message | provider_message.MessageChunk) -> str:
        if getattr(result, 'all_content', None):
            return str(getattr(result, 'all_content'))
        return cls._provider_content_to_text(getattr(result, 'content', None))

    async def _deliver_agent_outputs(
        self,
        envelope: AgentEventEnvelope,
        outputs: list[provider_message.Message | provider_message.MessageChunk],
    ) -> None:
        if not outputs or not envelope.delivery.reply_target:
            return

        reply_target = envelope.delivery.reply_target
        target_type = reply_target.get('target_type')
        target_id = reply_target.get('target_id')
        if not target_type or not target_id:
            return

        final_text = ''
        for output in outputs:
            output_text = self._provider_output_to_text(output)
            if isinstance(output, provider_message.Message):
                final_text = output_text or final_text
            elif output_text:
                final_text = output_text

        if not final_text:
            return

        await self.adapter.send_message(
            str(target_type),
            str(target_id),
            platform_message.MessageChain([platform_message.Plain(text=final_text)]),
        )

    async def _dispatch_eba_event_to_agent(
        self,
        event: platform_events.EBAEvent,
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
    ) -> None:
        event_type = getattr(event, 'type', None) or event.__class__.__name__

        event_binding = self._resolve_eba_event_binding(event, event_type)
        if event_binding is None:
            if isinstance(event, platform_events.MessageReceivedEvent):
                await self._dispatch_eba_message_to_pipeline(event, adapter)
            return

        target_type = event_binding.get('target_type')
        if target_type == 'discard':
            if isinstance(event, platform_events.MessageReceivedEvent):
                await self._dispatch_eba_message_to_pipeline(
                    event,
                    adapter,
                    pipeline_uuid=self.PIPELINE_DISCARD,
                    routed_by_event_binding=True,
                )
                return
            await self.logger.info(f'EBA event {event_type} discarded by event binding')
            return
        if target_type == 'pipeline':
            if not self._is_message_event_type(event_type):
                await self.logger.warning(f'EBA event {event_type} ignored Pipeline target for non-message event')
                return
            await self._dispatch_eba_message_to_pipeline(
                event,
                adapter,
                pipeline_uuid=event_binding.get('target_uuid'),
                routed_by_event_binding=True,
            )
            return
        if target_type != 'agent':
            await self.logger.warning(f'EBA event {event_type} ignored unsupported target type {target_type}')
            return

        target_uuid = event_binding.get('target_uuid')
        agent = await self.ap.agent_service.get_agent(target_uuid)
        if not agent or agent.get('kind') != 'agent':
            await self.logger.warning(f'EBA event {event_type} target agent not found: {target_uuid}')
            return
        if not agent.get('enabled', True):
            await self.logger.info(f'EBA event {event_type} target agent disabled: {target_uuid}')
            return
        if not self._agent_supports_event_type(agent.get('supported_event_patterns'), event_type):
            await self.logger.info(f'EBA event {event_type} target agent does not support this event: {target_uuid}')
            return

        binding = self._agent_product_to_binding(agent, event_binding, event_type, self.bot_entity.uuid)
        if binding is None:
            await self.logger.warning(f'EBA event {event_type} target agent has no runner: {target_uuid}')
            return

        envelope = self._eba_event_to_agent_envelope(event, adapter)
        outputs: list[provider_message.Message | provider_message.MessageChunk] = []
        try:
            async for output in self.ap.agent_run_orchestrator.run(envelope, binding):
                outputs.append(output)
        except Exception:
            await self.logger.error(f'Failed to run Agent for EBA event {event_type}: {traceback.format_exc()}')
            return

        try:
            await self._deliver_agent_outputs(envelope, outputs)
        except Exception:
            await self.logger.error(
                f'Failed to deliver Agent output for EBA event {event_type}: {traceback.format_exc()}'
            )

    def resolve_pipeline_uuid(
        self,
        launcher_type: str,
        launcher_id: str,
        message_text: str,
        message_element_types: list[str] | None = None,
    ) -> tuple[str | None, bool]:
        """Resolve pipeline UUID based on routing rules.

        Rules are evaluated in order; first match wins.
        Falls back to use_pipeline_uuid if no rule matches.

        Rule types:
          - launcher_type: session type ("person" / "group")
          - launcher_id: session / group id
          - message_content: message text content
          - message_has_element: message contains element of given type
            (Image, Voice, File, Forward, Face, At, AtAll, Quote)
            Operators: eq (has), neq (doesn't have)

        Operators: eq, neq, contains, not_contains, starts_with, regex

        When pipeline_uuid is ``__discard__``, the message should be
        silently dropped by the caller.

        Returns:
            tuple: (pipeline_uuid, routed_by_rule) - routed_by_rule is True
            when a routing rule matched, False when falling back to default.
        """
        rules = self.bot_entity.pipeline_routing_rules or []
        element_type_set = set(message_element_types or [])

        for rule in rules:
            rule_type = rule.get('type')
            operator = rule.get('operator', 'eq')
            rule_value = rule.get('value', '')
            target_uuid = rule.get('pipeline_uuid')
            if not rule_type or not target_uuid:
                continue

            if rule_type == 'launcher_type':
                if self._match_operator(launcher_type, operator, rule_value):
                    return target_uuid, True
            elif rule_type == 'launcher_id':
                if self._match_operator(str(launcher_id), operator, str(rule_value)):
                    return target_uuid, True
            elif rule_type == 'message_content':
                if self._match_operator(message_text, operator, rule_value):
                    return target_uuid, True
            elif rule_type == 'message_has_element':
                has_element = rule_value in element_type_set
                if operator == 'eq' and has_element:
                    return target_uuid, True
                elif operator == 'neq' and not has_element:
                    return target_uuid, True

        return self.bot_entity.use_pipeline_uuid, False

    async def _record_discarded_message(
        self,
        launcher_type: provider_session.LauncherTypes,
        launcher_id: str | int,
        sender_id: str | int,
        message_event: platform_events.MessageEvent,
        message_chain: platform_message.MessageChain,
    ) -> None:
        """Record a discarded message in the monitoring system."""
        try:
            if hasattr(message_chain, 'model_dump'):
                message_content = json.dumps(message_chain.model_dump(), ensure_ascii=False)
            else:
                message_content = str(message_chain)

            sender_name = None
            if hasattr(message_event, 'sender'):
                if hasattr(message_event.sender, 'nickname'):
                    sender_name = message_event.sender.nickname
                elif hasattr(message_event.sender, 'member_name'):
                    sender_name = message_event.sender.member_name

            # Use the same session_id format as monitoring_helper.py
            session_id = f'{launcher_type}_{launcher_id}'
            platform = launcher_type.value if hasattr(launcher_type, 'value') else str(launcher_type)

            await self.ap.monitoring_service.record_message(
                bot_id=self.bot_entity.uuid,
                bot_name=self.bot_entity.name or self.bot_entity.uuid,
                pipeline_id=self.PIPELINE_DISCARD,
                pipeline_name=self.PIPELINE_DISCARD_DISPLAY_NAME,
                message_content=message_content,
                session_id=session_id,
                status='discarded',
                level='info',
                platform=platform,
                user_id=str(sender_id),
                user_name=sender_name,
            )

            # Ensure the session exists so the message appears in the session monitor.
            # Don't overwrite pipeline info — a session may have messages from
            # multiple pipelines; discarding shouldn't change the displayed pipeline.
            session_updated = await self.ap.monitoring_service.update_session_activity(
                session_id,
            )
            if not session_updated:
                # No session yet (first message for this launcher was discarded).
                await self.ap.monitoring_service.record_session_start(
                    session_id=session_id,
                    bot_id=self.bot_entity.uuid,
                    bot_name=self.bot_entity.name or self.bot_entity.uuid,
                    pipeline_id=self.PIPELINE_DISCARD,
                    pipeline_name=self.PIPELINE_DISCARD_DISPLAY_NAME,
                    platform=platform,
                    user_id=str(sender_id),
                    user_name=sender_name,
                )
        except Exception as e:
            await self.logger.error(f'Failed to record discarded message: {e}')

    async def _handle_legacy_message_event(
        self,
        event: platform_events.FriendMessage | platform_events.GroupMessage,
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        pipeline_uuid_override: str | None = None,
        routed_by_event_binding: bool = False,
    ) -> None:
        is_group_message = isinstance(event, platform_events.GroupMessage)
        launcher_kind = 'group' if is_group_message else 'person'
        launcher_type = (
            provider_session.LauncherTypes.GROUP if is_group_message else provider_session.LauncherTypes.PERSON
        )
        launcher_id = event.group.id if is_group_message else event.sender.id
        sender_id = event.sender.id

        image_components = [
            component for component in event.message_chain if isinstance(component, platform_message.Image)
        ]

        await self.logger.info(
            f'{event.message_chain}',
            images=image_components,
            message_session_id=f'{launcher_kind}_{launcher_id}',
        )

        skip_pipeline = False
        if hasattr(self.ap, 'webhook_pusher') and self.ap.webhook_pusher:
            if is_group_message:
                skip_pipeline = await self.ap.webhook_pusher.push_group_message(
                    event, self.bot_entity.uuid, adapter.__class__.__name__
                )
            else:
                skip_pipeline = await self.ap.webhook_pusher.push_person_message(
                    event, self.bot_entity.uuid, adapter.__class__.__name__
                )

        if skip_pipeline:
            await self.logger.info(f'Pipeline skipped for {launcher_kind} message due to webhook response')
            return

        if hasattr(adapter, 'get_launcher_id'):
            custom_launcher_id = adapter.get_launcher_id(event)
            if custom_launcher_id:
                launcher_id = custom_launcher_id

        if pipeline_uuid_override is None:
            message_text = str(event.message_chain)
            element_types = [comp.type for comp in event.message_chain]
            pipeline_uuid, routed_by_rule = self.resolve_pipeline_uuid(
                launcher_kind, launcher_id, message_text, element_types
            )
        else:
            pipeline_uuid = pipeline_uuid_override
            routed_by_rule = routed_by_event_binding

        if pipeline_uuid == self.PIPELINE_DISCARD:
            await self.logger.info(f'{launcher_kind.title()} message discarded by routing rule')
            await self._record_discarded_message(
                launcher_type,
                launcher_id,
                sender_id,
                event,
                event.message_chain,
            )
            return

        await self.ap.msg_aggregator.add_message(
            bot_uuid=self.bot_entity.uuid,
            launcher_type=launcher_type,
            launcher_id=launcher_id,
            sender_id=sender_id,
            message_event=event,
            message_chain=event.message_chain,
            adapter=adapter,
            pipeline_uuid=pipeline_uuid,
            routed_by_rule=routed_by_rule,
        )

    async def _dispatch_eba_message_to_pipeline(
        self,
        event: platform_events.EBAEvent,
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        pipeline_uuid: str | None = None,
        routed_by_event_binding: bool = False,
    ) -> None:
        if not isinstance(event, platform_events.MessageReceivedEvent):
            event_type = getattr(event, 'type', None) or event.__class__.__name__
            await self.logger.warning(f'EBA event {event_type} cannot be dispatched to legacy Pipeline')
            return

        await self._handle_legacy_message_event(
            event.to_legacy_event(),
            adapter,
            pipeline_uuid_override=pipeline_uuid,
            routed_by_event_binding=routed_by_event_binding,
        )

    async def initialize(self):
        async def on_friend_message(
            event: platform_events.FriendMessage,
            adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        ):
            await self._handle_legacy_message_event(event, adapter)

        async def on_group_message(
            event: platform_events.GroupMessage,
            adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        ):
            await self._handle_legacy_message_event(event, adapter)

        self.adapter.register_listener(platform_events.FriendMessage, on_friend_message)
        self.adapter.register_listener(platform_events.GroupMessage, on_group_message)

        # Register feedback listener (only effective on adapters that support it)
        async def on_feedback(
            event: platform_events.FeedbackEvent,
            adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        ):
            try:
                # Resolve pipeline name
                pipeline_name = ''
                if self.bot_entity.use_pipeline_uuid:
                    try:
                        pipeline_result = await self.ap.persistence_mgr.execute_async(
                            sqlalchemy.select(persistence_pipeline.LegacyPipeline.name).where(
                                persistence_pipeline.LegacyPipeline.uuid == self.bot_entity.use_pipeline_uuid
                            )
                        )
                        pipeline_row = pipeline_result.first()
                        if pipeline_row:
                            pipeline_name = pipeline_row[0]
                    except Exception:
                        pass

                await self.ap.monitoring_service.record_feedback(
                    feedback_id=event.feedback_id,
                    feedback_type=event.feedback_type,
                    feedback_content=event.feedback_content,
                    inaccurate_reasons=event.inaccurate_reasons,
                    bot_id=self.bot_entity.uuid,
                    bot_name=self.bot_entity.name,
                    pipeline_id=self.bot_entity.use_pipeline_uuid or '',
                    pipeline_name=pipeline_name,
                    session_id=event.session_id,
                    message_id=event.message_id,
                    stream_id=event.stream_id,
                    user_id=event.user_id,
                    platform=adapter.__class__.__name__,
                )
                await self.logger.info(
                    f'Recorded feedback: feedback_id={event.feedback_id}, type={event.feedback_type}'
                )
            except Exception:
                await self.logger.error(f'Failed to record feedback: {traceback.format_exc()}')

        self.adapter.register_listener(platform_events.FeedbackEvent, on_feedback)

        async def on_eba_event(
            event: platform_events.EBAEvent,
            adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        ):
            event.bot_uuid = self.bot_entity.uuid
            plugin_event = self._eba_event_to_plugin_event(event)

            if plugin_event is not None:
                try:
                    await self.ap.plugin_connector.emit_event(plugin_event)
                except Exception:
                    await self.logger.error(f'Failed to dispatch EBA event to plugins: {traceback.format_exc()}')

            await self._dispatch_eba_event_to_agent(event, adapter)

        self.adapter.register_listener(platform_events.EBAEvent, on_eba_event)

    async def run(self):
        async def exception_wrapper():
            try:
                self.task_context.set_current_action('Running...')
                await self.adapter.run_async()
                self.task_context.set_current_action('Exited.')
            except Exception as e:
                if isinstance(e, asyncio.CancelledError):
                    self.task_context.set_current_action('Exited.')
                    return

                traceback_str = traceback.format_exc()
                self.task_context.set_current_action('Exited with error.')
                await self.logger.error(f'平台适配器运行出错:\n{e}\n{traceback_str}')

        self.task_wrapper = self.ap.task_mgr.create_task(
            exception_wrapper(),
            kind='platform-adapter',
            name=f'platform-adapter-{self.adapter.__class__.__name__}',
            context=self.task_context,
            scopes=[
                core_entities.LifecycleControlScope.APPLICATION,
                core_entities.LifecycleControlScope.PLATFORM,
            ],
        )

    async def shutdown(self):
        await self.adapter.kill()

        self.ap.task_mgr.cancel_task(self.task_wrapper.id)


# 控制QQ消息输入输出的类
class PlatformManager:
    # ====== 4.0 ======
    ap: app.Application = None

    bots: list[RuntimeBot]

    websocket_proxy_bot: RuntimeBot

    adapter_components: list[engine.Component]

    adapter_dict: dict[str, type[abstract_platform_adapter.AbstractMessagePlatformAdapter]]

    def __init__(self, ap: app.Application = None):
        self.ap = ap
        self.bots = []
        self.adapter_components = []
        self.adapter_dict = {}

    async def initialize(self):
        # delete all bot log images
        await self.ap.storage_mgr.storage_provider.delete_dir_recursive('bot_log_images')

        disabled_adapters = self.ap.instance_config.data.get('system', {}).get('disabled_adapters', []) or []

        self.adapter_components = self.ap.discover.get_components_by_kind('MessagePlatformAdapter')
        adapter_dict: dict[str, type[abstract_platform_adapter.AbstractMessagePlatformAdapter]] = {}
        for component in self.adapter_components:
            if component.metadata.name in disabled_adapters:
                continue
            adapter_dict[component.metadata.name] = component.get_python_component_class()
        self.adapter_dict = adapter_dict

        # Filter out disabled adapters from components list (for API responses)
        if disabled_adapters:
            self.adapter_components = [c for c in self.adapter_components if c.metadata.name not in disabled_adapters]

        # initialize websocket adapter
        websocket_adapter_class = self.adapter_dict['websocket']
        websocket_logger = EventLogger(name='websocket-adapter', ap=self.ap)
        websocket_adapter_inst = websocket_adapter_class(
            {},
            websocket_logger,
            ap=self.ap,
        )

        self.websocket_proxy_bot = RuntimeBot(
            ap=self.ap,
            bot_entity=persistence_bot.Bot(
                uuid='websocket-proxy-bot',
                name='WebSocket',
                description='',
                adapter='websocket',
                adapter_config={},
                enable=True,
            ),
            adapter=websocket_adapter_inst,
            logger=websocket_logger,
        )
        await self.websocket_proxy_bot.initialize()

        await self.load_bots_from_db()

    def get_running_adapters(self) -> list[abstract_platform_adapter.AbstractMessagePlatformAdapter]:
        return [bot.adapter for bot in self.bots if bot.enable]

    async def load_bots_from_db(self):
        self.ap.logger.info('Loading bots from db...')

        self.bots = []

        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_bot.Bot))

        bots = result.all()

        for bot in bots:
            # load all bots here, enable or disable will be handled in runtime
            try:
                await self.load_bot(bot)
            except platform_errors.AdapterNotFoundError as e:
                self.ap.logger.warning(f'Adapter {e.adapter_name} not found, skipping bot {bot.uuid}')
            except Exception as e:
                self.ap.logger.error(f'Failed to load bot {bot.uuid}: {e}\n{traceback.format_exc()}')

    async def load_bot(
        self,
        bot_entity: persistence_bot.Bot | sqlalchemy.Row[persistence_bot.Bot] | dict,
    ) -> RuntimeBot:
        """加载机器人"""
        if isinstance(bot_entity, sqlalchemy.Row):
            bot_entity = persistence_bot.Bot(**bot_entity._mapping)
        elif isinstance(bot_entity, dict):
            bot_entity = persistence_bot.Bot(**bot_entity)

        logger = EventLogger(name=f'platform-adapter-{bot_entity.name}', ap=self.ap)

        if bot_entity.adapter not in self.adapter_dict:
            raise platform_errors.AdapterNotFoundError(bot_entity.adapter)

        adapter_inst = self.adapter_dict[bot_entity.adapter](
            bot_entity.adapter_config,
            logger,
        )

        # 如果 adapter 支持 set_bot_uuid 方法，设置 bot_uuid（用于统一 webhook）
        if hasattr(adapter_inst, 'set_bot_uuid'):
            adapter_inst.set_bot_uuid(bot_entity.uuid)

        runtime_bot = RuntimeBot(ap=self.ap, bot_entity=bot_entity, adapter=adapter_inst, logger=logger)

        await runtime_bot.initialize()

        self.bots.append(runtime_bot)

        return runtime_bot

    async def get_bot_by_uuid(self, bot_uuid: str) -> RuntimeBot | None:
        if self.websocket_proxy_bot and self.websocket_proxy_bot.bot_entity.uuid == bot_uuid:
            return self.websocket_proxy_bot
        for bot in self.bots:
            if bot.bot_entity.uuid == bot_uuid:
                return bot
        return None

    async def remove_bot(self, bot_uuid: str):
        for bot in self.bots[:]:
            if bot.bot_entity.uuid == bot_uuid:
                if bot.enable:
                    await bot.shutdown()
                self.bots.remove(bot)
                return

    def get_available_adapters_info(self) -> list[dict]:
        return [
            component.to_plain_dict() for component in self.adapter_components if component.metadata.name != 'websocket'
        ]

    def get_available_adapter_info_by_name(self, name: str) -> dict | None:
        for component in self.adapter_components:
            if component.metadata.name == name:
                return component.to_plain_dict()
        return None

    def get_available_adapter_manifest_by_name(self, name: str) -> engine.Component | None:
        for component in self.adapter_components:
            if component.metadata.name == name:
                return component
        return None

    async def run(self):
        # This method will only be called when the application launching
        await self.websocket_proxy_bot.run()

        for bot in self.bots:
            if bot.enable:
                await bot.run()

    async def shutdown(self):
        for bot in self.bots:
            if bot.enable:
                await bot.shutdown()
        self.ap.task_mgr.cancel_by_scope(core_entities.LifecycleControlScope.PLATFORM)
