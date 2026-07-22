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
from ..entity.errors import platform as platform_errors
from ..agent.runner.config_resolver import RunnerConfigResolver
from ..agent.runner.host_models import (
    AgentBinding,
    AgentEventEnvelope,
    BindingScope,
    DeliveryPolicy,
    StatePolicy,
)
from ..agent.runner.resource_policy import ResourcePolicyProjector

from .logger import EventLogger

import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.events as plugin_events
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot_plugin.api.entities.builtin.agent_runner.event import (
    ActorContext,
    SubjectContext,
    RawEventRef,
)
from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput
from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext


class SyntheticRouteTestAdapter:
    """Adapter wrapper that suppresses outbound platform delivery for test events."""

    SIDE_EFFECT_API_NAMES = {
        'send_message',
        'reply_message',
        'reply_message_chunk',
        'create_message_card',
        'edit_message',
        'delete_message',
        'add_reaction',
        'remove_reaction',
        'forward_message',
        'set_group_name',
        'mute_member',
        'unmute_member',
        'kick_member',
        'leave_group',
        'approve_friend_request',
        'approve_group_invite',
        'upload_file',
        'call_platform_api',
    }

    def __init__(self, source: abstract_platform_adapter.AbstractMessagePlatformAdapter):
        self.source = source
        self.bot_account_id = getattr(source, 'bot_account_id', '')
        self.config = getattr(source, 'config', {})
        self.logger = getattr(source, 'logger', None)
        self.suppressed_outputs: list[dict[str, typing.Any]] = []

    @staticmethod
    def _message_to_payload(message: platform_message.MessageChain) -> typing.Any:
        return message.model_dump() if hasattr(message, 'model_dump') else str(message)

    def _suppress(self, method: str, **payload: typing.Any) -> None:
        self.suppressed_outputs.append({'method': method, **payload})

    def __getattr__(self, name: str) -> typing.Any:
        return getattr(self.source, name)

    def get_supported_apis(self) -> list[str]:
        get_supported_apis = getattr(self.source, 'get_supported_apis', None)
        if not callable(get_supported_apis):
            return []
        return [api_name for api_name in get_supported_apis() if api_name not in self.SIDE_EFFECT_API_NAMES]

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ) -> dict[str, typing.Any]:
        self._suppress(
            'send_message',
            target_type=target_type,
            target_id=target_id,
            message=self._message_to_payload(message),
        )
        return {'suppressed': True}

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ) -> dict[str, typing.Any]:
        self._suppress(
            'reply_message',
            message=self._message_to_payload(message),
            quote_origin=quote_origin,
        )
        return {'suppressed': True}

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message: dict,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ) -> dict[str, typing.Any]:
        self._suppress(
            'reply_message_chunk',
            message=self._message_to_payload(message),
            quote_origin=quote_origin,
            is_final=is_final,
        )
        return {'suppressed': True}

    async def create_message_card(
        self,
        message_id: str | int,
        event: platform_events.MessageEvent,
    ) -> bool:
        self._suppress('create_message_card', message_id=str(message_id))
        return False

    async def is_stream_output_supported(self) -> bool:
        return False

    async def edit_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
        new_content: platform_message.MessageChain,
    ) -> None:
        self._suppress(
            'edit_message',
            chat_type=str(chat_type),
            chat_id=str(chat_id),
            message_id=str(message_id),
            new_content=self._message_to_payload(new_content),
        )

    async def delete_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
    ) -> None:
        self._suppress(
            'delete_message',
            chat_type=str(chat_type),
            chat_id=str(chat_id),
            message_id=str(message_id),
        )

    async def forward_message(
        self,
        from_chat_type: str,
        from_chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
        to_chat_type: str,
        to_chat_id: typing.Union[int, str],
    ) -> platform_events.MessageResult:
        self._suppress(
            'forward_message',
            from_chat_type=str(from_chat_type),
            from_chat_id=str(from_chat_id),
            message_id=str(message_id),
            to_chat_type=str(to_chat_type),
            to_chat_id=str(to_chat_id),
        )
        return platform_events.MessageResult(raw={'suppressed': True})

    async def set_group_name(
        self,
        group_id: typing.Union[int, str],
        name: str,
    ) -> None:
        self._suppress('set_group_name', group_id=str(group_id), name=name)

    async def mute_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
        duration: int = 0,
    ) -> None:
        self._suppress(
            'mute_member',
            group_id=str(group_id),
            user_id=str(user_id),
            duration=duration,
        )

    async def unmute_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> None:
        self._suppress('unmute_member', group_id=str(group_id), user_id=str(user_id))

    async def kick_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> None:
        self._suppress('kick_member', group_id=str(group_id), user_id=str(user_id))

    async def leave_group(
        self,
        group_id: typing.Union[int, str],
    ) -> None:
        self._suppress('leave_group', group_id=str(group_id))

    async def approve_friend_request(
        self,
        request_id: typing.Union[int, str],
        approve: bool = True,
        remark: str | None = None,
    ) -> None:
        self._suppress(
            'approve_friend_request',
            request_id=str(request_id),
            approve=approve,
            remark=remark,
        )

    async def approve_group_invite(
        self,
        request_id: typing.Union[int, str],
        approve: bool = True,
    ) -> None:
        self._suppress(
            'approve_group_invite',
            request_id=str(request_id),
            approve=approve,
        )

    async def upload_file(self, file_data: bytes, filename: str) -> str:
        self._suppress('upload_file', filename=filename, size=len(file_data))
        return f'suppressed:{filename}'

    async def call_platform_api(self, action: str, params: dict | None = None) -> dict:
        self._suppress('call_platform_api', action=action, params=params or {})
        return {'suppressed': True}


class RuntimeBot:
    """运行时机器人"""

    ap: app.Application

    bot_entity: persistence_bot.Bot

    enable: bool

    adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter

    task_wrapper: taskmgr.TaskWrapper | None

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
        self.task_wrapper = None
        self.task_context = taskmgr.TaskContext()
        self.logger = logger

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
    def _augment_event_data(
        cls,
        event_data: dict[str, typing.Any],
    ) -> dict[str, typing.Any]:
        """Inject virtual computed fields to simplify common filter patterns."""
        message_chain = event_data.get('message_chain')
        if isinstance(message_chain, list):
            text_parts = [
                comp.get('text', '') for comp in message_chain if isinstance(comp, dict) and comp.get('type') == 'Plain'
            ]
            event_data['message_text'] = ''.join(text_parts)
            event_data['message_element_types'] = [
                comp.get('type', '') for comp in message_chain if isinstance(comp, dict)
            ]
        if 'group' in event_data:
            event_data['chat_type'] = 'group' if event_data.get('group') is not None else 'person'
        return event_data

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

        event_data = cls._augment_event_data(cls._safe_model_dump(event))
        return all(
            cls._match_event_filter(event_data, event_filter)
            for event_filter in filters
            if isinstance(event_filter, dict)
        )

    @staticmethod
    def _get_event_bindings_from_value(raw_bindings: typing.Any) -> list[dict[str, typing.Any]]:
        raw_bindings = raw_bindings or []
        if isinstance(raw_bindings, str):
            try:
                raw_bindings = json.loads(raw_bindings)
            except json.JSONDecodeError:
                raw_bindings = []
        if not isinstance(raw_bindings, list):
            return []
        return [binding for binding in raw_bindings if isinstance(binding, dict)]

    def _get_event_bindings(self) -> list[dict[str, typing.Any]]:
        return self._get_event_bindings_from_value(self.bot_entity.event_bindings)

    @classmethod
    def _evaluate_eba_event_bindings(
        cls,
        bindings: list[dict[str, typing.Any]],
        event: platform_events.EBAEvent,
        event_type: str,
    ) -> tuple[dict[str, typing.Any] | None, list[dict[str, typing.Any]]]:
        """Evaluate Bot event bindings with the same precedence used at runtime."""
        matched: list[tuple[int, int, dict[str, typing.Any], dict[str, typing.Any]]] = []
        diagnostic_steps: list[dict[str, typing.Any]] = []

        for index, binding in enumerate(bindings):
            event_pattern = str(binding.get('event_pattern') or '')
            priority = int(binding.get('priority') or 0)
            order = int(binding.get('order', index))
            step = {
                'step': 'evaluate_binding',
                'binding_id': binding.get('id'),
                'event_pattern': event_pattern,
                'target_type': binding.get('target_type'),
                'target_uuid': binding.get('target_uuid') or '',
                'enabled': binding.get('enabled', True),
                'priority': priority,
                'order': order,
                'matched': False,
                'failure_code': None,
                'reason': '',
            }

            if not binding.get('enabled', True):
                step['failure_code'] = 'binding_disabled'
                step['reason'] = 'Binding is disabled'
                diagnostic_steps.append(step)
                continue

            if not cls._match_event_pattern(event_type, event_pattern):
                step['failure_code'] = 'event_pattern_mismatch'
                step['reason'] = 'Event type does not match binding event_pattern'
                diagnostic_steps.append(step)
                continue
            if not cls._match_event_filters(event, binding.get('filters')):
                step['failure_code'] = 'filters_mismatch'
                step['reason'] = 'Event data does not satisfy binding filters'
                diagnostic_steps.append(step)
                continue

            step['matched'] = True
            step['reason'] = 'Binding matched event pattern and filters'
            diagnostic_steps.append(step)
            matched.append((priority, -order, binding, step))

        if not matched:
            return None, diagnostic_steps

        matched.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected_binding = matched[0][2]
        selected_step = matched[0][3]
        selected_step['selected'] = True
        selected_step['reason'] = 'Selected by priority and order'
        for _, _, _, step in matched[1:]:
            step['selected'] = False
            step['failure_code'] = 'lower_priority'
            step['reason'] = 'Another matching binding has higher priority or earlier order'
        return selected_binding, diagnostic_steps

    def _resolve_eba_event_binding(
        self,
        event: platform_events.EBAEvent,
        event_type: str,
    ) -> dict[str, typing.Any] | None:
        """Resolve the highest priority Bot event binding for a platform event."""
        selected, _ = self._evaluate_eba_event_bindings(self._get_event_bindings(), event, event_type)
        return selected

    def diagnose_eba_event_binding(
        self,
        event: platform_events.EBAEvent,
        event_type: str,
    ) -> tuple[dict[str, typing.Any] | None, list[dict[str, typing.Any]]]:
        """Return the selected event binding plus per-binding diagnostic steps."""
        return self._evaluate_eba_event_bindings(self._get_event_bindings(), event, event_type)

    @staticmethod
    def _build_test_platform_event(
        event_type: str,
        payload: dict[str, typing.Any] | None = None,
    ) -> platform_events.EBAEvent:
        """Build a synthetic platform event for route validation."""
        payload = payload or {}
        now = time.time()
        common = {
            'type': event_type,
            'timestamp': payload.get('timestamp') or now,
            'adapter_name': payload.get('adapter_name') or 'test-event',
            'source_platform_object': {'synthetic': True, 'payload': payload},
        }

        user_id = str(payload.get('user_id') or payload.get('sender_id') or 'test-user')
        user_name = str(payload.get('user_name') or payload.get('sender_name') or 'Test User')
        group_id = str(payload.get('group_id') or payload.get('chat_id') or 'test-group')
        group_name = str(payload.get('group_name') or 'Test Group')

        if event_type == 'message.received':
            chat_type_value = str(payload.get('chat_type') or 'private')
            chat_type = (
                platform_entities.ChatType.GROUP
                if chat_type_value == platform_entities.ChatType.GROUP.value
                else platform_entities.ChatType.PRIVATE
            )
            chat_id = str(
                payload.get('chat_id') or (group_id if chat_type == platform_entities.ChatType.GROUP else user_id)
            )
            message_text = str(payload.get('message_text') or payload.get('text') or '')
            message_chain_data = payload.get('message_chain')
            if message_chain_data is None:
                message_chain = platform_message.MessageChain([platform_message.Plain(text=message_text)])
            else:
                message_chain = platform_message.MessageChain.model_validate(message_chain_data)
            group = (
                platform_entities.UserGroup(id=chat_id, name=group_name)
                if chat_type == platform_entities.ChatType.GROUP
                else None
            )
            return platform_events.MessageReceivedEvent(
                **common,
                message_id=str(payload.get('message_id') or f'test-message:{uuid.uuid4()}'),
                message_chain=message_chain,
                sender=platform_entities.User(id=user_id, nickname=user_name),
                chat_type=chat_type,
                chat_id=chat_id,
                group=group,
            )

        if event_type == 'group.member_joined':
            return platform_events.MemberJoinedEvent(
                **common,
                group=platform_entities.UserGroup(id=group_id, name=group_name),
                member=platform_entities.User(id=user_id, nickname=user_name),
                inviter=platform_entities.User(
                    id=str(payload.get('inviter_id')),
                    nickname=str(payload.get('inviter_name') or ''),
                )
                if payload.get('inviter_id')
                else None,
                join_type=payload.get('join_type'),
            )

        if event_type == 'group.member_left':
            return platform_events.MemberLeftEvent(
                **common,
                group=platform_entities.UserGroup(id=group_id, name=group_name),
                member=platform_entities.User(id=user_id, nickname=user_name),
                is_kicked=bool(payload.get('is_kicked', False)),
                operator=platform_entities.User(
                    id=str(payload.get('operator_id')),
                    nickname=str(payload.get('operator_name') or ''),
                )
                if payload.get('operator_id')
                else None,
            )

        if event_type == 'platform.specific':
            return platform_events.PlatformSpecificEvent(
                **common,
                action=str(payload.get('action') or 'test'),
                data=payload.get('data') if isinstance(payload.get('data'), dict) else payload,
            )

        return platform_events.EBAEvent(**common)

    async def dispatch_test_event(
        self,
        event_type: str,
        payload: dict[str, typing.Any] | None = None,
    ) -> dict[str, typing.Any]:
        """Dispatch a synthetic event through the real runtime route path."""
        event_type = str(event_type or '').strip()
        if not event_type:
            raise ValueError('event_type is required')

        event = self._build_test_platform_event(event_type, payload)
        await self._record_event_route_trace(
            event_type=event_type,
            status='test_started',
            reason='Synthetic test event dispatched from control plane',
            text=f'Test event {event_type} dispatched from control plane',
        )
        test_adapter = SyntheticRouteTestAdapter(self.adapter)
        outcome = await self._dispatch_eba_event_to_processor(
            event,
            typing.cast(abstract_platform_adapter.AbstractMessagePlatformAdapter, test_adapter),
        )
        return {
            'event_type': event_type,
            'dispatched': outcome['status'] in {'delivered', 'discarded'},
            'status': outcome['status'],
            'binding_id': outcome.get('binding_id'),
            'failure_code': outcome.get('failure_code'),
            'reason': outcome.get('reason'),
            'suppressed_outputs': test_adapter.suppressed_outputs,
        }

    async def _record_event_route_trace(
        self,
        *,
        event_type: str,
        status: str,
        text: str,
        level: str = 'info',
        binding: dict[str, typing.Any] | None = None,
        target_type: str | None = None,
        target_uuid: str | None = None,
        failure_code: str | None = None,
        reason: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, typing.Any]:
        """Record structured event routing state while preserving the human log."""
        binding = binding or {}
        metadata = {
            'kind': 'event_route_trace',
            'event_type': event_type,
            'status': status,
            'binding_id': binding.get('id'),
            'event_pattern': binding.get('event_pattern'),
            'target_type': target_type or binding.get('target_type'),
            'target_uuid': target_uuid or binding.get('target_uuid') or '',
            'failure_code': failure_code,
            'reason': reason or text,
            'run_id': run_id,
        }
        log_method = getattr(self.logger, level, self.logger.info)
        await log_method(text, metadata=metadata)
        return metadata

    def get_pipeline_target_for_event_type(self, event_type: str = 'message.received') -> str | None:
        """Return the first Pipeline target configured for an event type."""
        matched: list[tuple[int, int, str]] = []
        for index, binding in enumerate(self._get_event_bindings()):
            if not binding.get('enabled', True):
                continue
            if binding.get('target_type') != 'pipeline':
                continue
            target_uuid = str(binding.get('target_uuid') or '')
            if not target_uuid:
                continue
            if not self._match_event_pattern(event_type, str(binding.get('event_pattern') or '')):
                continue
            priority = int(binding.get('priority') or 0)
            order = int(binding.get('order', index))
            matched.append((priority, -order, target_uuid))

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

    @staticmethod
    def _extract_message_id(message_chain: platform_message.MessageChain) -> str:
        for component in message_chain:
            if isinstance(component, platform_message.Source):
                value = getattr(component, 'id', '')
                return str(value) if value is not None else ''
        return ''

    def _legacy_message_to_eba_event(
        self,
        event: platform_events.FriendMessage | platform_events.GroupMessage,
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
    ) -> platform_events.MessageReceivedEvent:
        if isinstance(event, platform_events.GroupMessage):
            group = platform_entities.UserGroup(
                id=event.group.id,
                name=event.group.name,
            )
            return platform_events.MessageReceivedEvent(
                message_id=self._extract_message_id(event.message_chain),
                message_chain=event.message_chain,
                sender=platform_entities.User(
                    id=event.sender.id,
                    nickname=event.sender.member_name,
                ),
                chat_type=platform_entities.ChatType.GROUP,
                chat_id=event.group.id,
                group=group,
                timestamp=event.time or time.time(),
                bot_uuid=self.bot_entity.uuid,
                adapter_name=adapter.__class__.__name__,
                source_platform_object=event.source_platform_object,
            )

        return platform_events.MessageReceivedEvent(
            message_id=self._extract_message_id(event.message_chain),
            message_chain=event.message_chain,
            sender=platform_entities.User(
                id=event.sender.id,
                nickname=event.sender.nickname,
                remark=event.sender.remark,
            ),
            chat_type=platform_entities.ChatType.PRIVATE,
            chat_id=event.sender.id,
            timestamp=event.time or time.time(),
            bot_uuid=self.bot_entity.uuid,
            adapter_name=adapter.__class__.__name__,
            source_platform_object=event.source_platform_object,
        )

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
        supported_apis = self._get_adapter_supported_apis(adapter)

        conversation_id = None
        if target_type and target_id:
            conversation_id = f'{target_type}_{target_id}'
        elif getattr(event, 'session_id', None):
            conversation_id = str(getattr(event, 'session_id'))

        delivery_data: dict[str, typing.Any] = {
            'surface': 'platform',
            'reply_target': {
                'target_type': target_type,
                'target_id': target_id,
                'message_id': getattr(event, 'message_id', None),
                **target_metadata,
            },
            'supports_streaming': False,
            'supports_edit': 'edit_message' in supported_apis,
            'supports_reaction': bool({'add_reaction', 'remove_reaction'} & set(supported_apis)),
            'platform_capabilities': {
                'adapter': adapter.__class__.__name__,
                'event_type': event_type,
                'supported_apis': supported_apis,
            },
        }
        interaction_capabilities = self._get_adapter_interaction_capabilities(adapter, supported_apis)
        if interaction_capabilities is not None:
            delivery_data['interactions'] = interaction_capabilities

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
            delivery=DeliveryContext.model_validate(delivery_data),
            raw_ref=RawEventRef(ref_id=str(event_id), storage_key=None),
            data=self._compact_event_data(event),
        )

    @staticmethod
    def _get_adapter_supported_apis(
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
    ) -> list[str]:
        get_supported_apis = getattr(adapter, 'get_supported_apis', None)
        if not callable(get_supported_apis):
            return []
        try:
            declared_apis = get_supported_apis()
        except Exception:
            return []
        if not isinstance(declared_apis, (list, tuple, set)):
            return []
        return list(dict.fromkeys(api_name for api_name in declared_apis if isinstance(api_name, str) and api_name))

    @staticmethod
    def _get_adapter_interaction_capabilities(
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        supported_apis: list[str],
    ) -> dict[str, typing.Any] | None:
        if 'interactions' not in DeliveryContext.model_fields or 'interaction.request' not in supported_apis:
            return None
        get_capabilities = getattr(adapter, 'get_interaction_capabilities', None)
        if not callable(get_capabilities):
            return None
        try:
            capabilities = get_capabilities()
        except Exception:
            return None
        return capabilities if isinstance(capabilities, dict) else None

    @staticmethod
    def _agent_product_to_binding(
        agent: dict[str, typing.Any],
        event_binding: dict[str, typing.Any],
        event_type: str,
        bot_uuid: str,
    ) -> AgentBinding | None:
        config = agent.get('config') if isinstance(agent, dict) else None
        if config is None:
            return None

        _, runner_id, runner_config = RunnerConfigResolver.resolve_agent_runner_config(config)
        if not runner_id:
            return None

        return AgentBinding(
            binding_id=f'bot:{bot_uuid}:{event_binding.get("id") or uuid.uuid4()}',
            scope=BindingScope(scope_type='bot', scope_id=bot_uuid),
            event_types=[event_type],
            runner_id=runner_id,
            runner_config=runner_config,
            resource_policy=ResourcePolicyProjector.from_runner_config(runner_config),
            state_policy=StatePolicy(state_scopes=['conversation', 'actor', 'subject', 'runner']),
            delivery_policy=DeliveryPolicy(
                enable_streaming=False,
                enable_reply=True,
                enable_interactions=True,
            ),
            enabled=True,
            agent_id=agent.get('uuid'),
            processor_type='agent',
            processor_id=agent.get('uuid'),
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
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter | SyntheticRouteTestAdapter | None = None,
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

        delivery_adapter = adapter or self.adapter
        await delivery_adapter.send_message(
            str(target_type),
            str(target_id),
            platform_message.MessageChain([platform_message.Plain(text=final_text)]),
        )

    async def _handle_platform_event(
        self,
        event: platform_events.EBAEvent,
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
    ) -> None:
        if isinstance(event, platform_events.PlatformSpecificEvent) and event.action == 'interaction.submitted':
            await self._handle_interaction_submission(event, adapter)
            return

        event.bot_uuid = self.bot_entity.uuid
        plugin_event = self._eba_event_to_plugin_event(event)

        if plugin_event is not None:
            try:
                await self.ap.plugin_connector.emit_event(plugin_event)
            except Exception:
                await self.logger.error(f'Failed to dispatch platform event to plugins: {traceback.format_exc()}')

        await self._dispatch_eba_event_to_processor(event, adapter)

    async def _dispatch_eba_event_to_processor(
        self,
        event: platform_events.EBAEvent,
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
    ) -> dict[str, typing.Any]:
        event_type = getattr(event, 'type', None) or event.__class__.__name__

        event_binding = self._resolve_eba_event_binding(event, event_type)
        if event_binding is None:
            return await self._record_event_route_trace(
                event_type=event_type,
                status='not_matched',
                failure_code='route_not_found',
                reason='No event route matched',
                text=f'Platform event {event_type} ignored: no event route matched',
            )

        target_type = event_binding.get('target_type')
        await self._record_event_route_trace(
            event_type=event_type,
            status='matched',
            binding=event_binding,
            target_type=target_type,
            target_uuid=event_binding.get('target_uuid'),
            text=f'EBA event {event_type} matched route {event_binding.get("id") or ""}'.strip(),
        )
        if target_type == 'discard':
            if isinstance(event, platform_events.MessageReceivedEvent):
                await self._dispatch_eba_message_to_pipeline(
                    event,
                    adapter,
                    pipeline_uuid=self.PIPELINE_DISCARD,
                    routed_by_event_binding=True,
                )
                return await self._record_event_route_trace(
                    event_type=event_type,
                    status='discarded',
                    binding=event_binding,
                    target_type=target_type,
                    text=f'EBA event {event_type} discarded by event binding',
                )
            return await self._record_event_route_trace(
                event_type=event_type,
                status='discarded',
                binding=event_binding,
                target_type=target_type,
                text=f'EBA event {event_type} discarded by event binding',
            )
        if target_type == 'pipeline':
            if not self._is_message_event_type(event_type):
                return await self._record_event_route_trace(
                    event_type=event_type,
                    status='failed',
                    level='warning',
                    binding=event_binding,
                    target_type=target_type,
                    target_uuid=event_binding.get('target_uuid'),
                    failure_code='processor_incompatible',
                    reason='Pipeline targets only support message events',
                    text=f'EBA event {event_type} ignored Pipeline target for non-message event',
                )
            await self._dispatch_eba_message_to_pipeline(
                event,
                adapter,
                pipeline_uuid=event_binding.get('target_uuid'),
                routed_by_event_binding=True,
            )
            return await self._record_event_route_trace(
                event_type=event_type,
                status='delivered',
                binding=event_binding,
                target_type=target_type,
                target_uuid=event_binding.get('target_uuid'),
                text=f'EBA event {event_type} delivered to Pipeline {event_binding.get("target_uuid") or ""}'.strip(),
            )
        if target_type != 'agent':
            return await self._record_event_route_trace(
                event_type=event_type,
                status='failed',
                level='warning',
                binding=event_binding,
                target_type=target_type,
                target_uuid=event_binding.get('target_uuid'),
                failure_code='processor_incompatible',
                reason=f'Unsupported event binding target type: {target_type}',
                text=f'EBA event {event_type} ignored unsupported target type {target_type}',
            )

        target_uuid = event_binding.get('target_uuid')
        agent = await self.ap.agent_service.get_agent(target_uuid)
        if not agent or agent.get('kind') != 'agent':
            return await self._record_event_route_trace(
                event_type=event_type,
                status='failed',
                level='warning',
                binding=event_binding,
                target_type=target_type,
                target_uuid=target_uuid,
                failure_code='processor_not_found',
                reason='Agent target not found',
                text=f'EBA event {event_type} target agent not found: {target_uuid}',
            )
        if not agent.get('enabled', True):
            return await self._record_event_route_trace(
                event_type=event_type,
                status='failed',
                binding=event_binding,
                target_type=target_type,
                target_uuid=target_uuid,
                failure_code='processor_disabled',
                reason='Agent target is disabled',
                text=f'EBA event {event_type} target agent disabled: {target_uuid}',
            )
        if not self._agent_supports_event_type(agent.get('supported_event_patterns'), event_type):
            return await self._record_event_route_trace(
                event_type=event_type,
                status='failed',
                binding=event_binding,
                target_type=target_type,
                target_uuid=target_uuid,
                failure_code='processor_incompatible',
                reason='Agent target does not support this event type',
                text=f'EBA event {event_type} target agent does not support this event: {target_uuid}',
            )

        try:
            binding = self._agent_product_to_binding(agent, event_binding, event_type, self.bot_entity.uuid)
        except Exception:
            return await self._record_event_route_trace(
                event_type=event_type,
                status='failed',
                level='error',
                binding=event_binding,
                target_type=target_type,
                target_uuid=target_uuid,
                failure_code='runner_failed',
                reason='Agent configuration is invalid',
                text=f'Failed to build Agent binding for EBA event {event_type}: {traceback.format_exc()}',
            )
        if binding is None:
            return await self._record_event_route_trace(
                event_type=event_type,
                status='failed',
                level='warning',
                binding=event_binding,
                target_type=target_type,
                target_uuid=target_uuid,
                failure_code='processor_not_found',
                reason='Agent target has no runner',
                text=f'EBA event {event_type} target agent has no runner: {target_uuid}',
            )

        envelope = self._eba_event_to_agent_envelope(event, adapter)
        outputs: list[provider_message.Message | provider_message.MessageChunk] = []
        try:
            async for output in self.ap.agent_run_orchestrator.run(
                envelope,
                binding,
                adapter_context={'_delivery_adapter': adapter},
            ):
                outputs.append(output)
        except Exception:
            return await self._record_event_route_trace(
                event_type=event_type,
                status='failed',
                level='error',
                binding=event_binding,
                target_type=target_type,
                target_uuid=target_uuid,
                failure_code='runner_failed',
                reason='Agent runner failed',
                text=f'Failed to run Agent for EBA event {event_type}: {traceback.format_exc()}',
            )

        try:
            await self._deliver_agent_outputs(envelope, outputs, adapter=adapter)
        except Exception:
            return await self._record_event_route_trace(
                event_type=event_type,
                status='failed',
                level='error',
                binding=event_binding,
                target_type=target_type,
                target_uuid=target_uuid,
                failure_code='delivery_failed',
                reason='Agent output delivery failed',
                text=f'Failed to deliver Agent output for EBA event {event_type}: {traceback.format_exc()}',
            )
        return await self._record_event_route_trace(
            event_type=event_type,
            status='delivered',
            binding=event_binding,
            target_type=target_type,
            target_uuid=target_uuid,
            text=f'EBA event {event_type} delivered to Agent {target_uuid}',
        )

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
        variables: dict[str, typing.Any] | None = None,
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
            pipeline_uuid = None
            routed_by_rule = False
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
            variables=variables,
        )

    async def _handle_interaction_submission(
        self,
        event: platform_events.PlatformSpecificEvent,
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
    ) -> None:
        """Consume a platform interaction callback and resume its original processor."""
        data = event.data if isinstance(event.data, dict) else {}
        callback_token = str(data.get('callback_token') or '')
        actor_id = str(data.get('actor_id') or data.get('user_id') or '') or None
        target_type = str(data.get('target_type') or '') or None
        target_id = str(data.get('target_id') or data.get('chat_id') or '') or None
        conversation_id = f'{target_type}_{target_id}' if target_type and target_id else None
        submission = {
            'interaction_id': data.get('interaction_id'),
            'action_id': data.get('action_id'),
            'values': data.get('values') if isinstance(data.get('values'), dict) else {},
            'submitted_at': int(event.timestamp) if event.timestamp else None,
        }
        for ref_name in ('action_ref', 'field_ref', 'option_ref'):
            if data.get(ref_name) is not None:
                submission[ref_name] = data[ref_name]

        record = await self.ap.agent_run_orchestrator.interaction_manager.consume_callback(
            callback_token=callback_token,
            submission=submission,
            bot_id=self.bot_entity.uuid,
            conversation_id=conversation_id,
            actor_id=actor_id,
        )
        await self.ap.agent_run_orchestrator.interaction_manager.acknowledge_submission(record, adapter)

        if record['processor_type'] == 'agent':
            await self._resume_agent_interaction(record, event, adapter, actor_id)
            return
        if record['processor_type'] != 'pipeline':
            raise ValueError(f'Unsupported interaction processor type: {record["processor_type"]}')

        pipeline = await self.ap.pipeline_service.get_pipeline(record['processor_id'])
        if not pipeline:
            raise ValueError(f'Interaction target Pipeline is unavailable: {record["processor_id"]}')
        current_runner_id = RunnerConfigResolver.resolve_runner_id(pipeline.get('config') or {})
        if current_runner_id != record['runner_id']:
            raise ValueError('Interaction target Pipeline runner changed after the request was created')

        message_components: list[platform_message.MessageComponent] = []
        callback_message_id = data.get('message_id')
        if callback_message_id:
            message_components.append(
                platform_message.Source(
                    id=str(callback_message_id),
                    time=int(event.timestamp) if event.timestamp else int(time.time()),
                )
            )
        message_components.append(
            platform_message.Plain(text=str(data.get('display_text') or data.get('action_id') or 'submitted'))
        )
        message_chain = platform_message.MessageChain(message_components)
        delivery_target = record.get('delivery_target') or {}
        original_target_type = delivery_target.get('target_type')
        original_target_id = delivery_target.get('target_id')
        if original_target_type == 'group':
            group = platform_entities.Group(
                id=original_target_id,
                name='',
                permission=platform_entities.Permission.Member,
            )
            message_event: platform_events.MessageEvent = platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=actor_id or '',
                    member_name='',
                    permission=platform_entities.Permission.Member,
                    group=group,
                ),
                message_chain=message_chain,
                time=event.timestamp,
                source_platform_object=event.source_platform_object,
            )
        else:
            message_event = platform_events.FriendMessage(
                sender=platform_entities.Friend(id=actor_id or '', nickname='', remark=''),
                message_chain=message_chain,
                time=event.timestamp,
                source_platform_object=event.source_platform_object,
            )

        launcher_type = (
            provider_session.LauncherTypes.GROUP
            if original_target_type == 'group'
            else provider_session.LauncherTypes.PERSON
        )
        await self.ap.msg_aggregator.add_message(
            bot_uuid=self.bot_entity.uuid,
            launcher_type=launcher_type,
            launcher_id=original_target_id or target_id or actor_id or '',
            sender_id=actor_id or '',
            message_event=message_event,
            message_chain=message_chain,
            adapter=adapter,
            pipeline_uuid=record['processor_id'],
            routed_by_rule=True,
            variables={'_interaction_submission': record['submission']},
        )

    async def _resume_agent_interaction(
        self,
        record: dict[str, typing.Any],
        event: platform_events.PlatformSpecificEvent,
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        actor_id: str | None,
    ) -> None:
        """Resume the exact independent Agent that produced an interaction."""
        agent = await self.ap.agent_service.get_agent(record['processor_id'])
        if not agent or agent.get('kind') != 'agent' or not agent.get('enabled', True):
            raise ValueError(f'Interaction target Agent is unavailable: {record["processor_id"]}')

        binding = self._agent_product_to_binding(
            agent,
            {'id': record['binding_id']},
            'interaction.submitted',
            self.bot_entity.uuid,
        )
        if binding is None or binding.runner_id != record['runner_id']:
            raise ValueError('Interaction target Agent runner changed after the request was created')
        binding.binding_id = record['binding_id']

        submission = record['submission']
        display_text = str(
            (submission or {}).get('action_id')
            or (event.data if isinstance(event.data, dict) else {}).get('display_text')
            or 'submitted'
        )
        input_data: dict[str, typing.Any] = {
            'text': display_text,
            'contents': [{'type': 'text', 'text': display_text}],
            'attachments': [],
        }
        if 'interaction' in AgentInput.model_fields:
            input_data['interaction'] = submission

        delivery_target = record.get('delivery_target') or {}
        supported_apis = self._get_adapter_supported_apis(adapter)
        delivery_data: dict[str, typing.Any] = {
            'surface': 'platform',
            'reply_target': delivery_target,
            'supports_streaming': False,
            'supports_edit': 'edit_message' in supported_apis,
            'supports_reaction': bool({'add_reaction', 'remove_reaction'} & set(supported_apis)),
            'platform_capabilities': {
                'adapter': adapter.__class__.__name__,
                'event_type': 'interaction.submitted',
                'supported_apis': supported_apis,
            },
        }
        interaction_capabilities = self._get_adapter_interaction_capabilities(adapter, supported_apis)
        if interaction_capabilities is not None:
            delivery_data['interactions'] = interaction_capabilities

        envelope = AgentEventEnvelope(
            event_id=f'interaction:{record["id"]}:{uuid.uuid4()}',
            event_type='interaction.submitted',
            event_time=int(event.timestamp) if event.timestamp else int(time.time()),
            source='platform',
            source_event_type='interaction.submitted',
            bot_id=self.bot_entity.uuid,
            workspace_id=record.get('workspace_id'),
            conversation_id=record.get('conversation_id'),
            thread_id=record.get('thread_id'),
            actor=ActorContext(actor_type='user', actor_id=actor_id),
            subject=SubjectContext(
                subject_type='interaction',
                subject_id=record['interaction_id'],
                data={'action_id': (submission or {}).get('action_id')},
            ),
            input=AgentInput.model_validate(input_data),
            delivery=DeliveryContext.model_validate(delivery_data),
            raw_ref=RawEventRef(ref_id=f'interaction:{record["id"]}', storage_key=None),
            data={'interaction': submission},
        )

        outputs: list[provider_message.Message | provider_message.MessageChunk] = []
        async for output in self.ap.agent_run_orchestrator.run(
            envelope,
            binding,
            adapter_context={'_delivery_adapter': adapter},
        ):
            outputs.append(output)
        await self._deliver_agent_outputs(envelope, outputs, adapter=adapter)

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
        def websocket_pipeline_uuid(event, adapter):
            if adapter.__class__.__name__ != 'WebSocketAdapter':
                return None
            value = getattr(event, '_langbot_pipeline_uuid', None)
            return value if isinstance(value, str) and value else None

        async def on_friend_message(
            event: platform_events.FriendMessage,
            adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        ):
            pipeline_uuid = websocket_pipeline_uuid(event, adapter)
            if pipeline_uuid:
                await self._handle_legacy_message_event(event, adapter, pipeline_uuid_override=pipeline_uuid)
                return
            await self._handle_platform_event(self._legacy_message_to_eba_event(event, adapter), adapter)

        async def on_group_message(
            event: platform_events.GroupMessage,
            adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        ):
            pipeline_uuid = websocket_pipeline_uuid(event, adapter)
            if pipeline_uuid:
                await self._handle_legacy_message_event(event, adapter, pipeline_uuid_override=pipeline_uuid)
                return
            await self._handle_platform_event(self._legacy_message_to_eba_event(event, adapter), adapter)

        get_supported_events = getattr(self.adapter, 'get_supported_events', None)
        supported_events: list[str] = []
        if callable(get_supported_events):
            try:
                supported_events = list(get_supported_events() or [])
            except Exception:
                supported_events = []

        # EBA adapters emit MessageReceivedEvent directly. Registering both
        # entry paths would process each native message twice because these
        # adapters also expose legacy conversion for compatibility consumers.
        if 'message.received' not in supported_events:
            self.adapter.register_listener(platform_events.FriendMessage, on_friend_message)
            self.adapter.register_listener(platform_events.GroupMessage, on_group_message)

        # Register feedback listener (only effective on adapters that support it)
        async def on_feedback(
            event: platform_events.FeedbackEvent,
            adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        ):
            try:
                pipeline_id = self.get_pipeline_target_for_event_type('message.received') or ''
                pipeline_name = ''
                if pipeline_id:
                    pipeline = await self.ap.pipeline_service.get_pipeline(pipeline_id)
                    pipeline_name = pipeline.get('name', '') if pipeline else ''

                await self.ap.monitoring_service.record_feedback(
                    feedback_id=event.feedback_id,
                    feedback_type=event.feedback_type,
                    feedback_content=event.feedback_content,
                    inaccurate_reasons=event.inaccurate_reasons,
                    bot_id=self.bot_entity.uuid,
                    bot_name=self.bot_entity.name,
                    pipeline_id=pipeline_id,
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
            await self._handle_platform_event(event, adapter)

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

        if self.task_wrapper is not None:
            self.ap.task_mgr.cancel_task(self.task_wrapper.id)
            self.task_wrapper = None


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
        if hasattr(adapter_inst, 'ap'):
            adapter_inst.ap = self.ap

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
