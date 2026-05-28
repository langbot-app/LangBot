from __future__ import annotations

import asyncio
import traceback
import typing

import pydantic

from langbot.libs.official_account_api.api import OAClient, OAClientForLongerResponse
from langbot.libs.official_account_api.oaevent import OAEvent
from langbot.pkg.platform.adapters.officialaccount.api_impl import OfficialAccountAPIMixin
from langbot.pkg.platform.adapters.officialaccount.event_converter import OfficialAccountEventConverter
from langbot.pkg.platform.adapters.officialaccount.errors import NotSupportedError
from langbot.pkg.platform.adapters.officialaccount.message_converter import OfficialAccountMessageConverter
from langbot.pkg.platform.adapters.officialaccount.platform_api import PLATFORM_API_MAP
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class OfficialAccountAdapter(OfficialAccountAPIMixin, abstract_platform_adapter.AbstractPlatformAdapter):
    bot: typing.Any = pydantic.Field(exclude=True)

    message_converter: OfficialAccountMessageConverter = OfficialAccountMessageConverter()
    event_converter: OfficialAccountEventConverter = OfficialAccountEventConverter()

    config: dict
    bot_uuid: str | None = None
    listeners: dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}
    _message_cache: dict[str, platform_events.MessageReceivedEvent] = {}
    _user_cache: dict[str, platform_entities.User] = {}

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        required_keys = ['token', 'EncodingAESKey', 'AppSecret', 'AppID', 'Mode']
        missing_keys = [key for key in required_keys if not config.get(key)]
        if missing_keys:
            raise Exception(f'OfficialAccount EBA adapter missing config: {missing_keys}')

        mode = config['Mode']
        common_kwargs = {
            'token': config['token'],
            'EncodingAESKey': config['EncodingAESKey'],
            'Appsecret': config['AppSecret'],
            'AppID': config['AppID'],
            'logger': logger,
            'unified_mode': True,
            'api_base_url': config.get('api_base_url', 'https://api.weixin.qq.com'),
        }
        if mode == 'drop':
            bot = OAClient(**common_kwargs)
        elif mode == 'passive':
            bot = OAClientForLongerResponse(
                **common_kwargs,
                LoadingMessage=config.get('LoadingMessage', ''),
            )
        else:
            raise KeyError('OfficialAccount Mode must be "drop" or "passive"')

        super().__init__(
            config=config,
            logger=logger,
            bot=bot,
            bot_account_id=config.get('AppID', ''),
            bot_uuid=None,
            listeners={},
            _message_cache={},
            _user_cache={},
        )
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
            'reply_message',
            'get_message',
            'get_user_info',
            'get_friend_list',
            'call_platform_api',
        ]

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ) -> platform_events.MessageResult:
        raise NotSupportedError('send_message:official_account_requires_inbound_webhook_reply')

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ) -> platform_events.MessageResult:
        source = await OfficialAccountEventConverter.yiri2target(message_source)
        if not isinstance(source, OAEvent):
            raise ValueError('OfficialAccount reply_message requires an OAEvent source object')
        content = await OfficialAccountMessageConverter.yiri2target(message)
        if self.config.get('Mode') == 'passive':
            await self.bot.set_message(source.user_id, source.message_id, content)
        else:
            await self.bot.set_message(source.message_id, content)
        return platform_events.MessageResult(message_id=source.message_id, raw={'queued': True})

    async def call_platform_api(self, action: str, params: dict = {}) -> dict:
        handler = PLATFORM_API_MAP.get(action)
        if handler is None:
            raise NotSupportedError(f'call_platform_api:{action}')
        params = dict(params or {})
        params.setdefault('mode', self.config.get('Mode'))
        return await handler(self.bot, params)

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
        async def keep_alive():
            while True:
                await asyncio.sleep(1)

        await self.logger.info('OfficialAccount EBA adapter running in unified webhook mode')
        await keep_alive()

    async def kill(self) -> bool:
        return True

    async def is_muted(self, group_id: int | None = None) -> bool:
        return False

    def _register_native_handlers(self):
        for msg_type in ('text', 'image', 'voice', 'event'):
            self.bot.on_message(msg_type)(self._handle_native_event)

    async def _handle_native_event(self, event: OAEvent):
        self.bot_account_id = event.receiver_id or self.bot_account_id
        try:
            if platform_events.FriendMessage in self.listeners:
                legacy_event = await self.event_converter.target2legacy(event)
                if legacy_event and platform_events.FriendMessage in self.listeners:
                    await self.listeners[platform_events.FriendMessage](legacy_event, self)

            eba_event = await self.event_converter.target2yiri(event)
            if eba_event:
                self._cache_event(eba_event)
                await self._dispatch_eba_event(eba_event)
        except Exception:
            await self.logger.error(f'Error in officialaccount native event: {traceback.format_exc()}')

    async def _dispatch_eba_event(self, event: platform_events.EBAEvent):
        for event_type in (type(event), platform_events.EBAEvent, platform_events.Event):
            callback = self.listeners.get(event_type)
            if callback:
                await callback(event, self)
                return

    def _cache_event(self, event: platform_events.Event):
        if isinstance(event, platform_events.MessageReceivedEvent):
            self._message_cache[str(event.message_id)] = event
            self._user_cache[str(event.sender.id)] = event.sender
