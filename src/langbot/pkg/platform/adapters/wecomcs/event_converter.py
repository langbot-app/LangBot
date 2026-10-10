from __future__ import annotations

import typing

from langbot.libs.wecom_customer_service_api.api import WecomCSClient
from langbot.libs.wecom_customer_service_api.wecomcsevent import WecomCSEvent
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot.pkg.platform.adapters.wecomcs.message_converter import WecomCSMessageConverter
from langbot.pkg.platform.adapters.wecomcs.types import ADAPTER_NAME, make_private_chat_id
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events


class WecomCSEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.Event) -> WecomCSEvent | None:
        return getattr(event, 'source_platform_object', None)

    @staticmethod
    async def target2legacy(
        event: WecomCSEvent, bot: WecomCSClient | None = None
    ) -> platform_events.FriendMessage | None:
        eba_event = await WecomCSEventConverter.target2yiri(event, bot)
        if hasattr(eba_event, 'to_legacy_event'):
            return eba_event.to_legacy_event()
        return None

    @staticmethod
    async def target2yiri(event: WecomCSEvent, bot: WecomCSClient | None = None) -> platform_events.Event | None:
        if event.type in {'text', 'image', 'file', 'voice'}:
            return await WecomCSEventConverter.message_to_eba(event, bot)
        if event.type == 'event':
            data = event.get('event') or {}
            event_type = data.get('event_type', 'unknown')
            customer_id = data.get('external_userid') or ''
            common = {
                'adapter_name': ADAPTER_NAME,
                'timestamp': float(event.timestamp or 0),
                'source_platform_object': event,
                'chat_id': make_private_chat_id(customer_id, data.get('open_kfid')) if customer_id else '',
            }
            if event_type in {'user_recall_msg', 'servicer_recall_msg'}:
                operator_id = data.get('servicer_userid') if event_type == 'servicer_recall_msg' else customer_id
                return platform_events.MessageDeletedEvent(
                    message_id=data.get('recall_msgid') or '',
                    operator=platform_entities.User(id=operator_id) if operator_id else None,
                    **common,
                )
            event_classes = {
                'enter_session': platform_events.WecomCSEnterSessionEvent,
                'msg_send_fail': platform_events.WecomCSMessageSendFailedEvent,
                'servicer_status_change': platform_events.WecomCSServicerStatusChangedEvent,
                'session_status_change': platform_events.WecomCSSessionStatusChangedEvent,
                'reject_customer_msg_switch_change': platform_events.WecomCSRejectCustomerMessageChangedEvent,
            }
            event_class = event_classes.get(event_type)
            if event_class:
                fields = {
                    key: value for key, value in data.items() if key in event_class.model_fields and value is not None
                }
                fields.update(common)
                fields['data'] = dict(data)
                actor_id = data.get('servicer_userid') or customer_id
                fields['user'] = platform_entities.User(id=actor_id) if actor_id else None
                return event_class(**fields)
            return WecomCSEventConverter.platform_specific(event, f'wecomcs.{event_type}')
        return WecomCSEventConverter.platform_specific(event, f'wecomcs.{event.type or "unknown"}')

    @staticmethod
    async def message_to_eba(
        event: WecomCSEvent, bot: WecomCSClient | None = None
    ) -> platform_events.MessageReceivedEvent:
        message_chain = await WecomCSMessageConverter.target2yiri(event)
        sender = await WecomCSEventConverter.user_from_event(event, bot)
        return platform_events.MessageReceivedEvent(
            type='message.received',
            adapter_name=ADAPTER_NAME,
            message_id=event.message_id or '',
            message_chain=message_chain,
            sender=sender,
            chat_type=platform_entities.ChatType.PRIVATE,
            chat_id=make_private_chat_id(event.user_id, event.receiver_id),
            group=None,
            timestamp=float(event.timestamp or 0),
            source_platform_object=event,
        )

    @staticmethod
    async def user_from_event(event: WecomCSEvent, bot: WecomCSClient | None = None) -> platform_entities.User:
        nickname = str(event.user_id or '')
        avatar_url = None
        raw: dict[str, typing.Any] = {}
        if bot and event.user_id:
            try:
                raw = await bot.get_customer_info(event.user_id) or {}
                nickname = raw.get('nickname') or nickname
                avatar_url = raw.get('avatar')
            except Exception:
                raw = {}

        return platform_entities.User(
            id=event.user_id or '',
            nickname=nickname,
            avatar_url=avatar_url,
            username=raw.get('external_userid') or None,
        )

    @staticmethod
    def platform_specific(event: WecomCSEvent, action: str) -> platform_events.PlatformSpecificEvent:
        return platform_events.PlatformSpecificEvent(
            type='platform.specific',
            adapter_name=ADAPTER_NAME,
            action=action,
            data=dict(event),
            timestamp=float(event.timestamp or 0),
            source_platform_object=event,
        )
