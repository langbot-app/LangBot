import typing
import quart


import traceback
import asyncio
import base64
import datetime


import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
from ..logger import EventLogger


from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, ImageMessage
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
    VideoMessageContent,
    AudioMessageContent,
)

# from linebot import WebhookParser
from linebot.v3.webhook import WebhookParser
from linebot.v3.messaging import MessagingApiBlob


class LINEMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain, api_client: ApiClient) -> typing.Tuple[list]:
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
    async def target2yiri(message, bot_client) -> platform_message.MessageChain:
        lb_msg_list = []
        msg_create_time = datetime.datetime.fromtimestamp(int(message.timestamp) / 1000)

        lb_msg_list.append(platform_message.Source(id=message.webhook_event_id, time=msg_create_time))

        if isinstance(message.message, TextMessageContent):
            lb_msg_list.append(platform_message.Plain(text=message.message.text))
        elif isinstance(message.message, AudioMessageContent):
            pass
        elif isinstance(message.message, VideoMessageContent):
            pass
        elif isinstance(message.message, ImageMessageContent):
            message_content = MessagingApiBlob(bot_client).get_message_content(message.message.id)

            base64_string = base64.b64encode(message_content).decode('utf-8')

            # 如果需要Data URI格式（用于直接嵌入HTML等）
            # 首先需要知道图片类型，LINE图片通常是JPEG
            data_uri = f'data:image/jpeg;base64,{base64_string}'
            lb_msg_list.append(platform_message.Image(base64=data_uri))
        return platform_message.MessageChain(lb_msg_list)


class LINEEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(
        event: platform_events.MessageEvent,
    ) -> MessageEvent:
        pass

    @staticmethod
    async def target2yiri(event, bot_client) -> platform_events.Event:
        message_chain = await LINEMessageConverter.target2yiri(event, bot_client)

        if event.source.type == 'user':
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


class LINEAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    bot: MessagingApi
    api_client: ApiClient

    bot_account_id: str  # 用于在流水线中识别at是否是本bot，直接以bot_name作为标识
    message_converter: LINEMessageConverter
    event_converter: LINEEventConverter

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ]

    config: dict
    quart_app: quart.Quart

    card_id_dict: dict[str, str]  # 消息id到卡片id的映射，便于创建卡片后的发送消息到指定卡片

    seq: int  # 用于在发送卡片消息中识别消息顺序，直接以seq作为标识

    def __init__(self, config: dict, logger: EventLogger):
        configuration = Configuration(access_token=config['channel_access_token'])
        line_webhook = WebhookHandler(config['channel_secret'])
        parser = WebhookParser(config['channel_secret'])
        api_client = ApiClient(configuration)

        bot_account_id = config.get('bot_account_id', 'langbot')

        super().__init__(
            config=config,
            logger=logger,
            quart_app=quart.Quart(__name__),
            listeners={},
            card_id_dict={},
            seq=1,
            event_converter=LINEEventConverter(),
            message_converter=LINEMessageConverter(),
            line_webhook=line_webhook,
            parser=parser,
            configuration=configuration,
            api_client=api_client,
            bot=MessagingApi(api_client),
            bot_account_id=bot_account_id,
        )

        @self.quart_app.route('/line/callback', methods=['POST'])
        async def line_callback():
            try:
                signature = quart.request.headers.get('X-Line-Signature')
                body = await quart.request.get_data(as_text=True)
                events = parser.parse(body, signature)  # 解密解析消息

                try:
                    # print(events)
                    lb_event = await self.event_converter.target2yiri(events[0], self.api_client)
                    if lb_event.__class__ in self.listeners:
                        await self.listeners[lb_event.__class__](lb_event, self)
                except InvalidSignatureError:
                    self.logger.info(
                        f'Invalid signature. Please check your channel access token/channel secret.{traceback.format_exc()}'
                    )
                    return quart.Response('Invalid signature', status=400)

                return {'code': 200, 'message': 'ok'}
            except Exception:
                await self.logger.error(f'Error in LINE callback: {traceback.format_exc()}')
                return {'code': 500, 'message': 'error'}

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
                        messages=[TextMessage(text=content['content'])],
                    )
                )
            elif content['type'] == 'image':
                self.bot.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=message_source.source_platform_object.reply_token,
                        messages=[ImageMessage(text=content['content'])],
                    )
                )

    async def is_muted(self, group_id: int) -> bool:
        return False

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
