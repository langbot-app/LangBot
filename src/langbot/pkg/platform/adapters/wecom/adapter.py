from __future__ import annotations

import asyncio
import traceback
import typing

import pydantic

from langbot.libs.wecom_api.api import WecomClient
from langbot.libs.wecom_api.wecomevent import WecomEvent
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
from langbot.pkg.platform.adapters.wecom.api_impl import WecomAPIMixin
from langbot.pkg.platform.adapters.wecom.event_converter import WecomEventConverter
from langbot.pkg.platform.adapters.wecom.message_converter import WecomMessageConverter
from langbot.pkg.platform.adapters.wecom.platform_api import PLATFORM_API_MAP
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError


class WecomAdapter(WecomAPIMixin, abstract_platform_adapter.AbstractPlatformAdapter):
    bot: WecomClient = pydantic.Field(exclude=True)

    message_converter: WecomMessageConverter = WecomMessageConverter()
    event_converter: WecomEventConverter = WecomEventConverter()

    config: dict
    bot_uuid: str | None = None
    listeners: dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}
    _message_cache: dict[str, platform_events.MessageReceivedEvent] = {}
    _user_cache: dict[str, typing.Any] = {}

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        required_keys = [
            'corpid',
            'secret',
            'token',
            'EncodingAESKey',
        ]
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            raise Exception(f'WeCom missing required config fields: {missing_keys}')

        bot = WecomClient(
            corpid=config['corpid'],
            secret=config['secret'],
            token=config['token'],
            EncodingAESKey=config['EncodingAESKey'],
            contacts_secret=config.get('contacts_secret', ''),
            logger=logger,
            unified_mode=True,
            api_base_url=config.get('api_base_url', 'https://qyapi.weixin.qq.com/cgi-bin'),
        )

        super().__init__(
            config=config,
            logger=logger,
            bot=bot,
            bot_account_id='',
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
            'send_message',
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
        if target_type not in ('person', 'private'):
            raise NotSupportedError(f'send_message:{target_type}')

        user_id, agent_id = self._parse_target_id(target_id)
        content_list = await WecomMessageConverter.yiri2target(message, self.bot)
        raw_results = []
        for content in content_list:
            raw_results.append(await self._send_content(user_id, agent_id, content))
        return platform_events.MessageResult(raw={'results': raw_results})

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ) -> platform_events.MessageResult:
        wecom_event = await WecomEventConverter.yiri2target(message_source)
        if not isinstance(wecom_event, WecomEvent):
            raise ValueError('WeCom reply_message requires a WecomEvent source object')
        content_list = await WecomMessageConverter.yiri2target(message, self.bot)
        raw_results = []
        for content in content_list:
            raw_results.append(await self._send_content(wecom_event.user_id, int(wecom_event.agent_id), content))
        return platform_events.MessageResult(message_id=wecom_event.message_id, raw={'results': raw_results})

    async def call_platform_api(self, action: str, params: dict = {}) -> dict:
        handler = PLATFORM_API_MAP.get(action)
        if handler is None:
            raise NotSupportedError(f'call_platform_api:{action}')
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

        await self.logger.info('WeCom EBA adapter running in unified webhook mode')
        await keep_alive()

    async def kill(self) -> bool:
        return True

    async def is_muted(self, group_id: int | None = None) -> bool:
        return False

    def _register_native_handlers(self):
        async def on_message(event: WecomEvent):
            await self._handle_native_event(event)

        self.bot.on_message('text')(on_message)
        self.bot.on_message('image')(on_message)

    async def _handle_native_event(self, event: WecomEvent):
        self.bot_account_id = event.receiver_id or self.bot_account_id
        try:
            if platform_events.FriendMessage in self.listeners:
                legacy_event = await self.event_converter.target2legacy(event, self.bot)
                if legacy_event:
                    callback = self.listeners.get(type(legacy_event))
                    if callback:
                        await callback(legacy_event, self)

            eba_event = await self.event_converter.target2yiri(event, self.bot)
            if eba_event:
                self._cache_event(eba_event)
                await self._dispatch_eba_event(eba_event)
        except Exception:
            await self.logger.error(f'Error in wecom native event: {traceback.format_exc()}')

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

    async def _send_content(self, user_id: str, agent_id: int, content: dict):
        content_type = content.get('type')
        if content_type == 'text':
            return await self.bot.send_private_msg(user_id, agent_id, content.get('content', ''))
        if content_type == 'image':
            return await self.bot.send_image(user_id, agent_id, content['media_id'])
        if content_type == 'voice':
            return await self.bot.send_voice(user_id, agent_id, content['media_id'])
        if content_type == 'file':
            return await self.bot.send_file(user_id, agent_id, content['media_id'])
        raise NotSupportedError(f'send_content:{content_type}')

    @staticmethod
    def _parse_target_id(target_id: str) -> tuple[str, int]:
        user_id, sep, agent_id = str(target_id).partition('|')
        if not user_id or not sep or not agent_id:
            raise ValueError('WeCom target_id must be formatted as "user_id|agent_id"')
        return user_id, int(agent_id)
