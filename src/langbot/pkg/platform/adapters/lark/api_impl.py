from __future__ import annotations

import typing

from lark_oapi.api.im.v1 import GetChatRequest, GetMessageRequest
from lark_oapi.core.model import RequestOption

from langbot.pkg.platform.adapters.lark.event_converter import LarkEventConverter
from langbot.pkg.platform.adapters.lark.message_converter import LarkMessageConverter
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError


class LarkAPIMixin:
    _message_cache: dict[str, platform_events.MessageReceivedEvent]
    _user_cache: dict[str, platform_entities.User]
    _group_cache: dict[str, platform_entities.UserGroup]

    async def get_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
    ) -> platform_events.MessageReceivedEvent:
        cached = self._message_cache.get(str(message_id))
        if cached:
            return cached
        request = GetMessageRequest.builder().message_id(str(message_id)).build()
        response = await self.api_client.im.v1.message.aget(request, self.request_option(None))
        if not response.success():
            raise NotSupportedError(f'get_message:{message_id}')
        items = getattr(response.data, 'items', None) or []
        if not items:
            raise NotSupportedError(f'get_message:{message_id}')
        event_message = LarkEventConverter._build_event_message_from_message_item(items[0])
        if event_message is None:
            raise NotSupportedError(f'get_message:{message_id}')
        message_chain = await LarkMessageConverter.target2yiri(event_message, self.api_client)
        event = platform_events.MessageReceivedEvent(
            type='message.received',
            adapter_name='lark-eba',
            message_id=str(message_id),
            message_chain=message_chain,
            sender=platform_entities.User(id=''),
            chat_type=platform_entities.ChatType.GROUP if chat_type == 'group' else platform_entities.ChatType.PRIVATE,
            chat_id=chat_id,
            group=platform_entities.UserGroup(id=chat_id, name='') if chat_type == 'group' else None,
            timestamp=0,
            source_platform_object=items[0],
        )
        self._message_cache[str(message_id)] = event
        return event

    async def get_group_info(self, group_id: typing.Union[int, str]) -> platform_entities.UserGroup:
        cached = self._group_cache.get(str(group_id))
        if cached:
            return cached
        request = GetChatRequest.builder().chat_id(str(group_id)).build()
        response = await self.api_client.im.v1.chat.aget(request, self.request_option(None))
        if not response.success():
            raise NotSupportedError(f'get_group_info:{group_id}')
        data = response.data
        group = platform_entities.UserGroup(
            id=getattr(data, 'chat_id', group_id),
            name=getattr(data, 'name', '') or '',
            description=getattr(data, 'description', None),
            avatar_url=getattr(data, 'avatar', None),
            owner_id=getattr(data, 'owner_id', None),
        )
        self._group_cache[str(group.id)] = group
        return group

    async def get_group_member_info(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> platform_entities.UserGroupMember:
        user = self._user_cache.get(str(user_id)) or platform_entities.User(id=user_id)
        return platform_entities.UserGroupMember(user=user, group_id=group_id, role=platform_entities.MemberRole.MEMBER)

    async def get_user_info(self, user_id: typing.Union[int, str]) -> platform_entities.User:
        cached = self._user_cache.get(str(user_id))
        if cached:
            return cached
        return platform_entities.User(id=user_id)

    async def get_file_url(self, file_id: str) -> str:
        if str(file_id).startswith('file://'):
            return str(file_id)
        raise NotSupportedError('get_file_url requires a file:// path or platform-specific resource download params')

    def request_option(self, tenant_key: str | None) -> RequestOption:
        app_access_token = self.get_app_access_token()
        tenant_access_token = self.get_tenant_access_token(tenant_key)
        return (
            RequestOption.builder()
            .app_ticket(self.app_ticket)
            .tenant_key(tenant_key)
            .app_access_token(app_access_token)
            .tenant_access_token(tenant_access_token)
            .build()
        )
