import typing
import quart
import asyncio
import traceback
import json
import datetime
import base64
import re

import traceback
import typing
import asyncio
import re
import base64
import uuid
import json
import datetime
import hashlib
from Crypto.Cipher import AES

import quart
from lark_oapi.api.im.v1 import *
from lark_oapi.api.cardkit.v1 import *

from .. import adapter
from ...core import app
from ..types import message as platform_message
from ..types import events as platform_events
from ..types import entities as platform_entities
from ..logger import EventLogger

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    ImageMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
    VideoMessageContent,
    AudioMessageContent,
    FileMessageContent,
    LocationMessageContent,
    StickerMessageContent
)

from . import adapter



class LINEMessageConverter(adapter.MessageConverter):
    @staticmethod
    async def yiri2target(
        message_chain: platform_message.MessageChain, api_client: ApiClient
    ) -> typing.Tuple[list]:
        content_list = []
        for component in message_chain:
            if isinstance(component, platform_message.At):
                content_list.append({'type': 'at', 'target': component.target})
            elif isinstance(component, platform_message.Plain):
                content_list.append({'type': 'text', 'content': component.text})
            elif isinstance(component, platform_message.Image):
                if not component.url:
                    pass
                content_list.append({'type': 'image', 'image': component.url})

            elif isinstance(component, platform_message.Voice):
                content_list.append({'type': 'voice', 'url': component.url, 'length': component.length})
            

        return content_list

    @staticmethod
    async def target2yiri(
        message: MessageEvent,
        api_client: ApiClient,
    ) -> platform_message.MessageChain:
        lb_msg_list = []

        msg_create_time = datetime.datetime.fromtimestamp(int(message.timestamp) / 1000)

        lb_msg_list.append(platform_message.Source(id=message.webhook_event_id, time=msg_create_time))

        if isinstance(message.message, TextMessageContent):
            lb_msg_list.append(platform_message.Plain(text=message.message['text']))
        elif isinstance(message.message, AudioMessageContent):
            pass
        elif isinstance(message.message, VideoMessageContent):
            pass
        elif isinstance(message.message, ImageMessageContent):
            pass
        return platform_message.MessageChain(lb_msg_list)


class LINEEventConverter(adapter.EventConverter):
    @staticmethod
    async def yiri2target(
        event: platform_events.MessageEvent,
    ) -> MessageEvent:
        pass

    @staticmethod
    async def target2yiri(
        event: MessageEvent, api_client: ApiClient
    ) -> platform_events.Event:
        message_chain = await LINEMessageConverter.target2yiri(event.event.message, api_client)

        if event.source.type== 'user':
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event.message.id,
                    nickname=event.source.user_id,
                    remark='',
                ),
                message_chain=message_chain,
                time=event.timestamp,
                source_platform_object=event,
            )
        else:
            return platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=event.event.sender.sender_id.open_id,
                    member_name=event.event.sender.sender_id.union_id,
                    permission=platform_entities.Permission.Member,
                    group=platform_entities.Group(
                        id=event.message.id,
                        name='',
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                    join_timestamp=0,
                    last_speak_timestamp=0,
                    mute_time_remaining=0,
                ),
                message_chain=message_chain,
                time=event.timestamp,
                source_platform_object=event,
            )

class LINEAdapter(adapter.MessagePlatformAdapter):
    bot: WebhookHandler
    api_client: ApiClient

    bot_account_id: str  # 用于在流水线中识别at是否是本bot，直接以bot_name作为标识
    message_converter: LINEMessageConverter = LINEMessageConverter()
    event_converter: LINEEventConverter = LINEEventConverter()

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, adapter.MessagePlatformAdapter], None],
    ]

    config: dict
    quart_app: quart.Quart
    ap: app.Application


    card_id_dict: dict[str, str]  # 消息id到卡片id的映射，便于创建卡片后的发送消息到指定卡片

    seq: int  # 用于在发送卡片消息中识别消息顺序，直接以seq作为标识

    def __init__(self, config: dict, ap: app.Application, logger: EventLogger):
        self.config = config
        self.ap = ap
        self.logger = logger
        self.quart_app = quart.Quart(__name__)
        self.listeners = {}
        self.card_id_dict = {}
        self.seq = 1

        self.configuration = Configuration(access_token=config['channel_access_token'])
        self.webhook = WebhookHandler(config['channel_secret'])
        self.api_client = ApiClient(self.configuration)
        self.bot = MessagingApi(self.api_client)

        @self.quart_app.route('/line/callback', methods=['POST'])
        async def line_callback():
            try:
                signature = quart.request.headers.get('X-Line-Signature')
                body = await quart.request.get_data(as_text=True)
                self.logger.info("Request body: " + body)

                try:
                    self.webhook.handle(body, signature)
                except InvalidSignatureError:
                    self.logger.info("Invalid signature. Please check your channel access token/channel secret.")
                    return quart.Response('Invalid signature', status=400)


                return {'code': 200, 'message': 'ok'}
            except Exception:
                await self.logger.error(f'Error in LINE callback: {traceback.format_exc()}')
                return {'code': 500, 'message': 'error'}

        @self.webhook.add(MessageEvent)
        async def handle_message(event):
            # 不限定类型，所有event都进on_message
            asyncio.create_task(self.on_message(event))

        async def on_message(self, event: MessageEvent):
            try:
                print(event)
                lb_event = await self.event_converter.target2yiri(event, self.api_client)
                if type(lb_event) in self.listeners:
                    await self.listeners[type(lb_event)](lb_event, self)
            except Exception:
                await self.logger.error(f'Error in LINE message: {traceback.format_exc()}')
    

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        
        pass

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        content_list = await self.message_converter.yiri2target(message, self.api_client)

        for content in content_list:
            if content['type'] == 'text':
                self.bot.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=message_source.source_platform_object.reply_token,
                        messages=[TextMessage(text=content['content'])]
                    )
                )
            elif content['type'] == 'image':
                 self.bot.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=message_source.source_platform_object.reply_token,
                        messages=[ImageMessage(text=content['content'])]
                    )
                )

    async def is_muted(self, group_id: int) -> bool:
        return False

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[[platform_events.Event, adapter.MessagePlatformAdapter], None],
    ):
        self.listeners[event_type] = callback

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[[platform_events.Event, adapter.MessagePlatformAdapter], None],
    ):
        self.listeners.pop(event_type)

    async def run_async(self):
        port = self.config['port']

        async def shutdown_trigger_placeholder():
            while True:
                await asyncio.sleep(1)
        await self.quart_app.run_task(
            host='0.0.0.0',
            port=port,
            shutdown_trigger=shutdown_trigger_placeholder,
        )

    async def kill(self) -> bool:
        pass
