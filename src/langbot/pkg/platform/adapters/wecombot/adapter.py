from __future__ import annotations

import asyncio
import time
import traceback
import typing

import pydantic

from langbot.libs.wecom_ai_bot_api.api import WecomBotClient
from langbot.libs.wecom_ai_bot_api.wecombotevent import WecomBotEvent
from langbot.libs.wecom_ai_bot_api.ws_client import WecomBotWsClient
from langbot.pkg.platform.adapters.wecombot.api_impl import WecomBotAPIMixin
from langbot.pkg.platform.adapters.wecombot.event_converter import WecomBotEventConverter
from langbot.pkg.platform.adapters.wecombot.message_converter import WecomBotMessageConverter
from langbot.pkg.platform.adapters.wecombot.platform_api import PLATFORM_API_MAP
from langbot.pkg.platform.adapters.wecombot.interaction import (
    interaction_delivery_capabilities,
    interaction_event_from_native,
    send_interaction,
)
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError


class WecomBotAdapter(WecomBotAPIMixin, abstract_platform_adapter.AbstractPlatformAdapter):
    bot: typing.Any = pydantic.Field(exclude=True)

    message_converter: WecomBotMessageConverter = WecomBotMessageConverter()
    event_converter: WecomBotEventConverter

    config: dict
    bot_uuid: str | None = None
    bot_name: str = ''
    listeners: dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}
    _message_cache: dict[str, platform_events.MessageReceivedEvent] = {}
    _user_cache: dict[str, platform_entities.User] = {}
    _group_cache: dict[str, platform_entities.UserGroup] = {}
    _member_cache: dict[tuple[str, str], platform_entities.UserGroupMember] = {}
    _stream_to_monitoring_msg: dict[str, tuple[str, float]] = {}
    _STREAM_MAPPING_TTL: int = 600

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        enable_webhook = config.get('enable-webhook', False)
        bot_name = config.get('robot_name', '')
        if not enable_webhook:
            required_keys = ['BotId', 'Secret']
            missing_keys = [key for key in required_keys if not config.get(key)]
            if missing_keys:
                raise Exception(f'WeComBot WebSocket mode missing config: {missing_keys}')
            bot = WecomBotWsClient(
                bot_id=config['BotId'],
                secret=config['Secret'],
                logger=logger,
                encoding_aes_key=config.get('EncodingAESKey', ''),
            )
        else:
            required_keys = ['Token', 'EncodingAESKey', 'Corpid']
            missing_keys = [key for key in required_keys if not config.get(key)]
            if missing_keys:
                raise Exception(f'WeComBot webhook mode missing config: {missing_keys}')
            bot = WecomBotClient(
                Token=config['Token'],
                EnCodingAESKey=config['EncodingAESKey'],
                Corpid=config['Corpid'],
                logger=logger,
                unified_mode=True,
            )

        super().__init__(
            config=config,
            logger=logger,
            bot=bot,
            bot_account_id=config.get('BotId', ''),
            bot_uuid=None,
            bot_name=bot_name,
            event_converter=WecomBotEventConverter(bot_name=bot_name),
            listeners={},
            _message_cache={},
            _user_cache={},
            _group_cache={},
            _member_cache={},
            _stream_to_monitoring_msg={},
        )
        self._register_native_handlers()

    def set_bot_uuid(self, bot_uuid: str):
        self.bot_uuid = bot_uuid

    def get_supported_events(self) -> list[str]:
        return [
            'message.received',
            'feedback.received',
            'platform.specific',
        ]

    def get_supported_apis(self) -> list[str]:
        apis = [
            'send_message',
            'reply_message',
            'get_message',
            'get_user_info',
            'get_friend_list',
            'get_group_info',
            'get_group_member_info',
            'get_group_member_list',
            'call_platform_api',
        ]
        if not self.config.get('enable-webhook', False) and hasattr(self.bot, 'send_template_card'):
            apis.append('interaction.request')
        return apis

    def get_interaction_capabilities(self) -> dict[str, typing.Any]:
        return interaction_delivery_capabilities()

    @staticmethod
    def _plain_message(text: str) -> platform_message.MessageChain:
        return platform_message.MessageChain([platform_message.Plain(text=text)])

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ) -> platform_events.MessageResult:
        if self.config.get('enable-webhook', False):
            raise NotSupportedError('send_message:webhook_mode')
        if target_type not in ('person', 'private', 'group'):
            raise NotSupportedError(f'send_message:{target_type}')
        content = await WecomBotMessageConverter.yiri2target(message)
        raw = await self.bot.send_message(str(target_id), content)
        return platform_events.MessageResult(raw={'result': raw})

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ) -> platform_events.MessageResult:
        event = await WecomBotEventConverter.yiri2target(message_source)
        if not isinstance(event, WecomBotEvent):
            raise ValueError('WeComBot reply_message requires a WecomBotEvent source object')
        content = await WecomBotMessageConverter.yiri2target(message)
        if not self.config.get('enable-webhook', False) and event.get('req_id'):
            raw = await self.bot.reply_text(event.get('req_id'), content)
        else:
            raw = await self.bot.set_message(event.message_id, content)
        return platform_events.MessageResult(message_id=event.message_id, raw={'result': raw})

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ) -> dict:
        event = await WecomBotEventConverter.yiri2target(message_source)
        if not isinstance(event, WecomBotEvent):
            raise ValueError('WeComBot reply_message_chunk requires a WecomBotEvent source object')
        content = await WecomBotMessageConverter.yiri2target(message)
        success = await self.bot.push_stream_chunk(event.message_id, content, is_final=is_final)
        if not success and is_final and not self.config.get('enable-webhook', False) and event.get('req_id'):
            await self.bot.reply_text(event.get('req_id'), content)
        return {'stream': success}

    async def is_stream_output_supported(self) -> bool:
        return self.config.get('enable-stream-reply', True)

    async def call_platform_api(self, action: str, params: dict = {}) -> dict:
        if action == 'interaction.request' and 'interaction.request' in self.get_supported_apis():
            return await send_interaction(self, params)
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
        if not self.config.get('enable-webhook', False):
            return None
        return await self.bot.handle_unified_webhook(request)

    async def run_async(self):
        if not self.config.get('enable-webhook', False):
            await self.bot.connect()
            return

        async def keep_alive():
            while True:
                await asyncio.sleep(1)

        await self.logger.info('WeComBot EBA adapter running in unified webhook mode')
        await keep_alive()

    async def kill(self) -> bool:
        if not self.config.get('enable-webhook', False):
            await self.bot.disconnect()
        return True

    async def is_muted(self, group_id: int | None = None) -> bool:
        return False

    async def on_monitoring_message_created(self, query, monitoring_message_id: str):
        try:
            stream_id = query.message_event.source_platform_object.stream_id
            if stream_id:
                self._stream_to_monitoring_msg[stream_id] = (monitoring_message_id, time.time())
                self._cleanup_stream_mapping()
        except Exception as e:
            await self.logger.debug(f'Failed to map stream_id to monitoring message: {e}')

    def _register_native_handlers(self):
        self.bot.on_message('single')(self._handle_native_event)
        self.bot.on_message('group')(self._handle_native_event)
        if hasattr(self.bot, 'on_feedback'):
            self.bot.on_feedback()(self._handle_feedback)
        if hasattr(self.bot, 'on_message'):
            self.bot.on_message('event')(self._handle_native_event)
            self.bot.on_message('template_card_event')(self._handle_interaction_event)

    async def _handle_interaction_event(self, event: WecomBotEvent):
        try:
            interaction_event = interaction_event_from_native(event)
            if interaction_event is not None:
                await self._dispatch_eba_event(interaction_event)
        except Exception:
            await self.logger.error(f'Error in WeComBot interaction callback: {traceback.format_exc()}')

    async def _handle_native_event(self, event: WecomBotEvent):
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
            await self.logger.error(f'Error in wecombot native event: {traceback.format_exc()}')

    async def _handle_feedback(self, **kwargs):
        try:
            event = WecomBotEventConverter.feedback_to_eba(**kwargs)
            if event.stream_id and event.stream_id in self._stream_to_monitoring_msg:
                monitoring_msg_id, _ = self._stream_to_monitoring_msg[event.stream_id]
                event.stream_id = monitoring_msg_id
            await self._dispatch_eba_event(event)
        except Exception:
            await self.logger.error(f'Error in wecombot feedback event: {traceback.format_exc()}')

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

    def _cleanup_stream_mapping(self):
        now = time.time()
        expired = [
            key for key, (_, ts) in self._stream_to_monitoring_msg.items() if now - ts > self._STREAM_MAPPING_TTL
        ]
        for key in expired:
            del self._stream_to_monitoring_msg[key]
