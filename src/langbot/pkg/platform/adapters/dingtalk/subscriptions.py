"""Translate DingTalk Stream EVENT envelopes, keeping unknown payloads intact."""

import asyncio
from collections import OrderedDict

import dingtalk_stream
from langbot_plugin.api.entities.builtin.platform import entities, events

from .types import ADAPTER_NAME


def subscription_events(message):
    data = message.data
    headers = message.headers
    action = headers.event_type or data.get('EventType') or data.get('eventType') or ''
    raw = {'headers': vars(headers).copy(), 'data': data}
    stamp = headers.event_born_time or data.get('TimeStamp') or data.get('EventTime') or data.get('timestamp') or headers.time or 0
    stamp = float(stamp)
    common = dict(
        adapter_name=ADAPTER_NAME,
        timestamp=stamp / 1000 if stamp > 10_000_000_000 else stamp,
        source_platform_object=raw,
    )
    group_id = data.get('OpenConversationId') or data.get('openConversationId') or data.get('chatId') or data.get('ChatId')
    group = entities.UserGroup(id=str(group_id or ''), name=str(data.get('Title') or data.get('title') or ''))
    owner_id = data.get('Owner') or data.get('owner')
    if owner_id:
        group.owner_id = str(owner_id)
    operator_id = data.get('Operator') or data.get('operator')
    operator = entities.User(id=str(operator_id)) if operator_id else None
    members = data.get('UserId') or data.get('userId') or []
    if isinstance(members, str):
        members = [members]
    if group_id and members and action in {'chat_add_member', 'chat_remove_member', 'chat_quit'}:
        for member_id in dict.fromkeys(members):
            member = entities.User(id=str(member_id))
            if action == 'chat_add_member':
                yield events.MemberJoinedEvent(group=group, member=member, inviter=operator, **common)
            else:
                yield events.MemberLeftEvent(
                    group=group, member=member, operator=operator,
                    is_kicked=action == 'chat_remove_member', **common,
                )
    elif group_id and action in {'chat_update_title', 'chat_update_owner'}:
        yield events.GroupInfoUpdatedEvent(
            group=group, operator=operator,
            changed_fields=['name' if action == 'chat_update_title' else 'owner_id'], **common,
        )
    else:
        yield events.PlatformSpecificEvent(action=action or 'unknown', data=raw, **common)


class DingTalkSubscriptionHandler(dingtalk_stream.EventHandler):
    def __init__(self, adapter):
        super().__init__()
        self.adapter = adapter
        self.completed = OrderedDict()
        self.lock = asyncio.Lock()

    async def process(self, message):
        # Serialize retries; mark each fan-out event only after successful dispatch.
        async with self.lock:
            try:
                identity = message.headers.event_id or message.headers.message_id
                for index, event in enumerate(subscription_events(message)):
                    key = (message.headers.event_corp_id, identity, index)
                    if identity and key in self.completed:
                        continue
                    await self.adapter._dispatch_eba_event(event)
                    if identity:
                        self.completed[key] = None
                        while len(self.completed) > 4096:
                            self.completed.popitem(last=False)
                return dingtalk_stream.AckMessage.STATUS_OK, 'OK'
            except Exception:
                self.logger.exception('DingTalk subscription dispatch failed')
                return 500, 'Event dispatch failed'
