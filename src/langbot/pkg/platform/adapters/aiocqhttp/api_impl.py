from __future__ import annotations

import typing

import aiocqhttp

from langbot.pkg.platform.adapters.aiocqhttp.event_converter import AiocqhttpEventConverter
from langbot.pkg.platform.adapters.aiocqhttp.message_converter import AiocqhttpMessageConverter
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError


class AiocqhttpAPIMixin:
    bot: aiocqhttp.CQHttp

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ) -> platform_events.MessageResult:
        forward = message.get_first(platform_message.Forward)
        if forward and target_type == 'group':
            raw = await self._send_forward_message(int(target_id), typing.cast(platform_message.Forward, forward))
            return platform_events.MessageResult(message_id=raw.get('message_id'), raw=raw)

        aiocq_msg, _, _ = await AiocqhttpMessageConverter.yiri2target(message)
        if target_type == 'group':
            raw = await self.bot.send_group_msg(group_id=int(target_id), message=aiocq_msg)
        elif target_type in ('person', 'private'):
            raw = await self.bot.send_private_msg(user_id=int(target_id), message=aiocq_msg)
        else:
            raise ValueError(f'Unsupported aiocqhttp target_type: {target_type}')
        return platform_events.MessageResult(message_id=(raw or {}).get('message_id'), raw=raw or {})

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ) -> platform_events.MessageResult:
        assert isinstance(message_source.source_platform_object, aiocqhttp.Event)
        aiocq_msg, _, _ = await AiocqhttpMessageConverter.yiri2target(message)
        if quote_origin:
            source_id = getattr(message_source, 'message_id', None) or message_source.message_chain.message_id
            aiocq_msg = aiocqhttp.MessageSegment.reply(source_id) + aiocq_msg
        raw = await self.bot.send(message_source.source_platform_object, aiocq_msg)
        return platform_events.MessageResult(message_id=(raw or {}).get('message_id'), raw=raw or {})

    async def delete_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
    ) -> None:
        await self.bot.delete_msg(message_id=int(message_id))

    async def forward_message(
        self,
        from_chat_type: str,
        from_chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
        to_chat_type: str,
        to_chat_id: typing.Union[int, str],
    ) -> platform_events.MessageResult:
        raw_message = await self.bot.get_msg(message_id=int(message_id))
        target_message = aiocqhttp.Message(raw_message.get('message', []))
        if to_chat_type == 'group':
            raw = await self.bot.send_group_msg(group_id=int(to_chat_id), message=target_message)
        elif to_chat_type in ('person', 'private'):
            raw = await self.bot.send_private_msg(user_id=int(to_chat_id), message=target_message)
        else:
            raise ValueError(f'Unsupported aiocqhttp to_chat_type: {to_chat_type}')
        return platform_events.MessageResult(message_id=(raw or {}).get('message_id'), raw=raw or {})

    async def get_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
    ) -> platform_events.MessageReceivedEvent:
        raw = await self.bot.get_msg(message_id=int(message_id))
        message_type = raw.get('message_type') or chat_type
        event = aiocqhttp.Event.from_payload(
            {
                'post_type': 'message',
                'message_type': 'group' if message_type == 'group' else 'private',
                'sub_type': raw.get('sub_type', 'normal'),
                'time': raw.get('time', 0),
                'self_id': self.bot_account_id or 0,
                'message_id': raw.get('message_id', message_id),
                'user_id': raw.get('sender', {}).get('user_id') or raw.get('user_id') or chat_id,
                'group_id': raw.get('group_id') or (chat_id if message_type == 'group' else None),
                'message': raw.get('message', []),
                'raw_message': raw.get('raw_message', ''),
                'sender': raw.get('sender', {}),
            }
        )
        return await AiocqhttpEventConverter.message_to_eba(event, self.bot)

    async def get_group_info(self, group_id: typing.Union[int, str]) -> platform_entities.UserGroup:
        raw = await self.bot.get_group_info(group_id=int(group_id))
        return platform_entities.UserGroup(
            id=raw.get('group_id', group_id),
            name=raw.get('group_name', ''),
            member_count=raw.get('member_count'),
        )

    async def get_group_list(self) -> list[platform_entities.UserGroup]:
        raw_list = await self.bot.get_group_list()
        return [
            platform_entities.UserGroup(
                id=item.get('group_id', ''),
                name=item.get('group_name', ''),
                member_count=item.get('member_count'),
            )
            for item in raw_list
        ]

    async def get_group_member_list(
        self,
        group_id: typing.Union[int, str],
    ) -> list[platform_entities.UserGroupMember]:
        raw_list = await self.bot.get_group_member_list(group_id=int(group_id))
        return [self._member_to_entity(item, group_id) for item in raw_list]

    async def get_group_member_info(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> platform_entities.UserGroupMember:
        raw = await self.bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id), no_cache=True)
        return self._member_to_entity(raw, group_id)

    async def set_group_name(self, group_id: typing.Union[int, str], name: str) -> None:
        await self.bot.set_group_name(group_id=int(group_id), group_name=name)

    async def mute_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
        duration: int = 0,
    ) -> None:
        await self.bot.set_group_ban(group_id=int(group_id), user_id=int(user_id), duration=int(duration))

    async def unmute_member(self, group_id: typing.Union[int, str], user_id: typing.Union[int, str]) -> None:
        await self.bot.set_group_ban(group_id=int(group_id), user_id=int(user_id), duration=0)

    async def kick_member(self, group_id: typing.Union[int, str], user_id: typing.Union[int, str]) -> None:
        await self.bot.set_group_kick(group_id=int(group_id), user_id=int(user_id), reject_add_request=False)

    async def leave_group(self, group_id: typing.Union[int, str]) -> None:
        await self.bot.set_group_leave(group_id=int(group_id), is_dismiss=False)

    async def get_user_info(self, user_id: typing.Union[int, str]) -> platform_entities.User:
        raw = await self.bot.get_stranger_info(user_id=int(user_id), no_cache=True)
        return platform_entities.User(
            id=raw.get('user_id', user_id),
            nickname=raw.get('nickname', ''),
            avatar_url=raw.get('avatar_url'),
        )

    async def get_friend_list(self) -> list[platform_entities.User]:
        raw_list = await self.bot.get_friend_list()
        return [
            platform_entities.User(
                id=item.get('user_id', ''),
                nickname=item.get('nickname', ''),
                remark=item.get('remark'),
            )
            for item in raw_list
        ]

    async def approve_friend_request(
        self,
        request_id: typing.Union[int, str],
        approve: bool = True,
        remark: typing.Optional[str] = None,
    ) -> None:
        await self.bot.set_friend_add_request(flag=str(request_id), approve=approve, remark=remark or '')

    async def approve_group_invite(self, request_id: typing.Union[int, str], approve: bool = True) -> None:
        await self.bot.set_group_add_request(flag=str(request_id), sub_type='invite', approve=approve, reason='')

    async def upload_file(self, file_data: bytes, filename: str) -> str:
        raise NotSupportedError('upload_file')

    async def get_file_url(self, file_id: str) -> str:
        raise NotSupportedError('get_file_url')

    @staticmethod
    def _member_to_entity(raw: dict, group_id: typing.Union[int, str]) -> platform_entities.UserGroupMember:
        role = platform_entities.MemberRole.MEMBER
        if raw.get('role') == 'owner':
            role = platform_entities.MemberRole.OWNER
        elif raw.get('role') == 'admin':
            role = platform_entities.MemberRole.ADMIN
        return platform_entities.UserGroupMember(
            user=platform_entities.User(
                id=raw.get('user_id', ''),
                nickname=raw.get('nickname', ''),
                remark=raw.get('card') or raw.get('remark'),
            ),
            group_id=group_id,
            role=role,
            display_name=raw.get('card') or raw.get('nickname'),
            joined_at=float(raw['join_time']) if raw.get('join_time') else None,
            title=raw.get('title'),
        )

    async def _send_forward_message(self, group_id: int, forward: platform_message.Forward) -> dict:
        messages = []
        for node in forward.node_list:
            if not node.message_chain:
                continue
            content, _, _ = await AiocqhttpMessageConverter.yiri2target(node.message_chain)
            if not content:
                continue
            messages.append(
                {
                    'type': 'node',
                    'data': {
                        'user_id': str(node.sender_id or self.bot_account_id or '10000'),
                        'nickname': node.sender_name or 'LangBot',
                        'content': list(content),
                    },
                }
            )
        if not messages:
            return {}
        try:
            return await self.bot.call_action(
                'send_forward_msg', group_id=group_id, user_id=str(self.bot_account_id), messages=messages
            )
        except Exception:
            return await self.bot.call_action('send_group_forward_msg', group_id=group_id, messages=messages)
