from __future__ import annotations

import asyncio
import traceback
import typing

import pydantic

from langbot.libs.slack_api.api import SlackClient
from langbot.libs.slack_api.slackevent import SlackEvent
from langbot.pkg.platform.adapters.slack.api_impl import SlackAPIMixin
from langbot.pkg.platform.adapters.slack.errors import NotSupportedError
from langbot.pkg.platform.adapters.slack.event_converter import SlackEventConverter
from langbot.pkg.platform.adapters.slack.message_converter import SlackMessageConverter
from langbot.pkg.platform.adapters.slack.platform_api import PLATFORM_API_MAP
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class SlackAdapter(SlackAPIMixin, abstract_platform_adapter.AbstractPlatformAdapter):
    bot: typing.Any = pydantic.Field(exclude=True)

    message_converter: SlackMessageConverter = SlackMessageConverter()
    event_converter: SlackEventConverter = SlackEventConverter()

    config: dict
    bot_uuid: str | None = None
    listeners: dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}
    _message_cache: dict[str, platform_events.MessageReceivedEvent] = {}
    _user_cache: dict[str, platform_entities.User] = {}
    _group_cache: dict[str, platform_entities.UserGroup] = {}
    _member_cache: dict[tuple[str, str], platform_entities.UserGroupMember] = {}

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        required_keys = ['bot_token', 'signing_secret']
        missing_keys = [key for key in required_keys if not config.get(key)]
        if missing_keys:
            raise Exception(f'Slack EBA adapter missing config: {missing_keys}')

        bot = SlackClient(
            bot_token=config['bot_token'],
            signing_secret=config['signing_secret'],
            logger=logger,
            unified_mode=True,
        )
        super().__init__(
            config=config,
            logger=logger,
            bot=bot,
            bot_account_id=config.get('bot_user_id', ''),
            bot_uuid=None,
            listeners={},
            _message_cache={},
            _user_cache={},
            _group_cache={},
            _member_cache={},
        )
        self.event_converter = SlackEventConverter(config['bot_token'])
        self._register_native_handlers()

    def set_bot_uuid(self, bot_uuid: str):
        self.bot_uuid = bot_uuid

    def get_supported_events(self) -> list[str]:
        return [
            'message.received',
            'platform.specific',
        ]

    def get_supported_apis(self) -> list[str]:
        return [
            'send_message',
            'reply_message',
            'get_message',
            'get_user_info',
            'get_friend_list',
            'get_group_info',
            'get_group_list',
            'get_group_member_list',
            'get_group_member_info',
            'call_platform_api',
        ]

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ) -> platform_events.MessageResult:
        content = await SlackMessageConverter.yiri2target(message)
        raw = await self._send_text(str(target_type), str(target_id), content)
        return platform_events.MessageResult(raw=raw)

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ) -> platform_events.MessageResult:
        source = await SlackEventConverter.yiri2target(message_source)
        if not isinstance(source, SlackEvent):
            raise ValueError('Slack reply_message requires a SlackEvent source object')
        target_type = 'channel' if source.type == 'channel' else 'person'
        target_id = source.channel_id if source.type == 'channel' else source.user_id
        raw = await self._send_text(target_type, target_id, await SlackMessageConverter.yiri2target(message))
        return platform_events.MessageResult(message_id=source.message_id, raw=raw)

    async def call_platform_api(self, action: str, params: dict = {}) -> dict:
        handler = PLATFORM_API_MAP.get(action)
        if handler is None:
            raise NotSupportedError(f'call_platform_api:{action}')
        return await handler(self, dict(params or {}))

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        self.listeners[event_type] = callback

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        registered = self.listeners.get(event_type)
        if registered is callback:
            self.listeners.pop(event_type, None)

    async def handle_unified_webhook(self, bot_uuid: str, path: str, request):
        return await self.bot.handle_unified_webhook(request)

    async def run_async(self):
        await self.logger.info('Slack EBA adapter running in unified webhook mode')
        while True:
            await asyncio.sleep(1)

    async def kill(self) -> bool:
        return True

    async def is_muted(self, group_id: int | None = None) -> bool:
        return False

    def _register_native_handlers(self):
        for msg_type in ('im', 'channel'):
            self.bot.on_message(msg_type)(self._handle_native_event)

    async def _handle_native_event(self, event: SlackEvent):
        try:
            if platform_events.FriendMessage in self.listeners or platform_events.GroupMessage in self.listeners:
                legacy_event = await self.event_converter.target2legacy(event)
                if legacy_event and type(legacy_event) in self.listeners:
                    await self.listeners[type(legacy_event)](legacy_event, self)

            eba_event = await self.event_converter.target2yiri(event)
            if eba_event:
                self._cache_event(eba_event)
                await self._dispatch_eba_event(eba_event)
        except Exception:
            await self.logger.error(f'Error in slack native event: {traceback.format_exc()}')

    async def _dispatch_eba_event(self, event: platform_events.EBAEvent):
        for event_type in (type(event), platform_events.EBAEvent, platform_events.Event):
            callback = self.listeners.get(event_type)
            if callback:
                await callback(event, self)
                return

    def _cache_event(self, event: platform_events.Event):
        if not isinstance(event, platform_events.MessageReceivedEvent):
            return
        self._message_cache[str(event.message_id)] = event
        self._user_cache[str(event.sender.id)] = event.sender
        if event.group:
            self._group_cache[str(event.group.id)] = event.group
            self._member_cache[(str(event.group.id), str(event.sender.id))] = platform_entities.UserGroupMember(
                user=event.sender,
                group_id=event.group.id,
                role=platform_entities.MemberRole.MEMBER,
                display_name=event.sender.nickname,
            )

    async def _send_text(self, target_type: str, target_id: str, content: str) -> dict:
        target_type = self._normalize_target_type(target_type)
        if target_type == 'person':
            raw = await self.bot.send_message_to_one(content, target_id)
        elif target_type == 'channel':
            raw = await self.bot.send_message_to_channel(content, target_id)
        else:
            raise NotSupportedError(f'send_message:{target_type}')
        return {'target_type': target_type, 'target_id': target_id, 'raw': raw}

    @staticmethod
    def _normalize_target_type(target_type: str) -> str:
        if target_type in {'person', 'private', 'friend', 'im', 'dm'}:
            return 'person'
        if target_type in {'group', 'channel'}:
            return 'channel'
        return target_type
