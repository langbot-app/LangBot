from __future__ import annotations

import traceback
import typing

import dingtalk_stream
import pydantic

from langbot.libs.dingtalk_api.api import DingTalkClient
from langbot.libs.dingtalk_api.dingtalkevent import DingTalkEvent
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
from langbot.pkg.platform.adapters.dingtalk.api_impl import DingTalkAPIMixin
from langbot.pkg.platform.adapters.dingtalk.event_converter import DingTalkEventConverter
from langbot.pkg.platform.adapters.dingtalk.message_converter import DingTalkMessageConverter
from langbot.pkg.platform.adapters.dingtalk.platform_api import PLATFORM_API_MAP
from langbot.pkg.platform.adapters.dingtalk.interaction import (
    interaction_delivery_capabilities,
    interaction_event_from_native,
    send_interaction,
)
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError


class DingTalkCardCallbackHandler(dingtalk_stream.CallbackHandler):
    def __init__(self, adapter: 'DingTalkAdapter'):
        super().__init__()
        self.adapter = adapter

    async def process(self, message: dingtalk_stream.CallbackMessage):
        callback = dingtalk_stream.CardCallbackMessage.from_dict(message.data or {})
        content = dict(callback.content) if isinstance(callback.content, dict) else {}
        if isinstance(message.data, dict):
            content['_raw_callback'] = message.data
        event = DingTalkEvent.from_payload(
            {
                'conversation_type': 'CardCallback',
                'Type': 'card_callback',
                'CardCallback': {
                    'extension': callback.extension,
                    'corp_id': callback.corp_id,
                    'user_id': callback.user_id,
                    'content': content,
                    'space_id': callback.space_id,
                    'card_instance_id': callback.card_instance_id,
                },
            }
        )
        if event is not None:
            await self.adapter._handle_native_event(event)
        return dingtalk_stream.AckMessage.STATUS_OK, 'OK'


class DingTalkAdapter(DingTalkAPIMixin, abstract_platform_adapter.AbstractPlatformAdapter):
    bot: DingTalkClient = pydantic.Field(exclude=True)

    message_converter: DingTalkMessageConverter = DingTalkMessageConverter()
    event_converter: DingTalkEventConverter = DingTalkEventConverter()

    config: dict
    listeners: dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}
    card_instance_id_dict: dict = {}
    _message_cache: dict[str, platform_events.MessageReceivedEvent] = {}
    _user_cache: dict[str, platform_entities.User] = {}
    _group_cache: dict[str, platform_entities.UserGroup] = {}
    interaction_callback_contexts: dict[str, dict[str, typing.Any]] = {}

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        required_keys = ['client_id', 'client_secret', 'robot_name', 'robot_code']
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            raise Exception('钉钉缺少相关配置项，请查看文档或联系管理员')

        bot = DingTalkClient(
            client_id=config['client_id'],
            client_secret=config['client_secret'],
            robot_name=config['robot_name'],
            robot_code=config['robot_code'],
            markdown_card=config.get('markdown_card', True),
            logger=logger,
        )
        super().__init__(
            config=config,
            logger=logger,
            card_instance_id_dict={},
            bot_account_id=config['robot_name'],
            bot=bot,
            listeners={},
            _message_cache={},
            _user_cache={},
            _group_cache={},
            interaction_callback_contexts={},
        )
        self._register_native_handlers()

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
            'get_group_info',
            'get_group_list',
            'get_group_member_info',
            'get_user_info',
            'get_friend_list',
            'get_file_url',
            'call_platform_api',
        ]
        if self.config.get('human_input_card_template_id') and hasattr(self.bot, 'create_and_deliver_card'):
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
        markdown_enabled = self.config.get('markdown_card', False)
        content, _ = await DingTalkMessageConverter.yiri2target(message, markdown_enabled)
        if target_type in ('person', 'private'):
            raw = await self.bot.send_proactive_message_to_one(target_id, content)
        elif target_type == 'group':
            raw = await self.bot.send_proactive_message_to_group(target_id, content)
        else:
            raise ValueError(f'Unsupported dingtalk target_type: {target_type}')
        return platform_events.MessageResult(raw=raw if isinstance(raw, dict) else {'result': raw})

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ) -> platform_events.MessageResult:
        assert isinstance(message_source.source_platform_object, DingTalkEvent)
        incoming_message = message_source.source_platform_object.incoming_message
        markdown_enabled = self.config.get('markdown_card', False)
        content, at = await DingTalkMessageConverter.yiri2target(message, markdown_enabled)
        raw = await self.bot.send_message(content, incoming_message, at)
        return platform_events.MessageResult(
            message_id=getattr(incoming_message, 'message_id', None),
            raw=raw if isinstance(raw, dict) else {'result': raw},
        )

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        message_id = bot_message.resp_message_id
        msg_seq = bot_message.msg_sequence
        if (msg_seq - 1) % 8 != 0 and not is_final:
            return

        markdown_enabled = self.config.get('markdown_card', False)
        content, _ = await DingTalkMessageConverter.yiri2target(message, markdown_enabled)
        card_instance, card_instance_id = self.card_instance_id_dict[message_id]
        if not content and bot_message.content:
            content = bot_message.content
        if content:
            await self.bot.send_card_message(card_instance, card_instance_id, content, is_final)
        if is_final and bot_message.tool_calls is None:
            self.card_instance_id_dict.pop(message_id)

    async def create_message_card(self, message_id, event):
        card_template_id = self.config['card_template_id']
        incoming_message = event.source_platform_object.incoming_message
        card_auto_layout = self.config.get('card_auto_layout', False)
        card_instance, card_instance_id = await self.bot.create_and_card(
            card_template_id,
            incoming_message,
            card_auto_layout=card_auto_layout,
        )
        self.card_instance_id_dict[message_id] = (card_instance, card_instance_id)
        return True

    async def is_stream_output_supported(self) -> bool:
        return bool(self.config.get('enable-stream-reply', False))

    async def call_platform_api(self, action: str, params: dict = {}) -> dict:
        if action == 'interaction.request' and action in self.get_supported_apis():
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

    async def run_async(self):
        await self.logger.info('DingTalk EBA adapter starting')
        await self.bot.start()

    async def kill(self) -> bool:
        await self.bot.stop()
        return True

    async def is_muted(self, group_id: int | None = None) -> bool:
        return False

    def _register_native_handlers(self):
        async def on_message(event: DingTalkEvent):
            await self._handle_native_event(event)

        self.bot.on_message('FriendMessage')(on_message)
        self.bot.on_message('GroupMessage')(on_message)
        self.bot.client.register_callback_handler(
            dingtalk_stream.CallbackHandler.TOPIC_CARD_CALLBACK,
            DingTalkCardCallbackHandler(self),
        )

    async def _handle_native_event(self, event: DingTalkEvent):
        try:
            interaction_event = interaction_event_from_native(event, self.interaction_callback_contexts)
            if interaction_event is not None:
                await self._dispatch_eba_event(interaction_event)
                return
            await self.logger.debug(
                'DingTalk EBA event received: '
                f'conversation={event.conversation}, message_id={getattr(event.incoming_message, "message_id", None)}'
            )
            if platform_events.FriendMessage in self.listeners or platform_events.GroupMessage in self.listeners:
                legacy_event = await self.event_converter.target2legacy(event, self.config['robot_name'])
                if legacy_event:
                    callback = self.listeners.get(type(legacy_event))
                    if callback:
                        await callback(legacy_event, self)

            eba_event = await self.event_converter.target2yiri(event, self.config['robot_name'])
            if eba_event:
                self._cache_event(eba_event)
                await self._dispatch_eba_event(eba_event)
        except Exception:
            await self.logger.error(f'Error in dingtalk native event: {traceback.format_exc()}')

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
