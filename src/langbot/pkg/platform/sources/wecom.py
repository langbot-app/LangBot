from __future__ import annotations
import typing
import asyncio
import traceback

import datetime

from langbot.libs.wecom_api.api import WecomClient
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot.libs.wecom_api.wecomevent import WecomEvent
from langbot.pkg.utils import image
from langbot.pkg.platform.logger import EventLogger
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities


class WecomMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain, bot: WecomClient):
        content_list = []

        for msg in message_chain:
            if type(msg) is platform_message.Plain:
                content_list.append(
                    {
                        'type': 'text',
                        'content': msg.text,
                    }
                )
            elif type(msg) is platform_message.Image:
                content_list.append(
                    {
                        'type': 'image',
                        'media_id': await bot.get_media_id(msg),
                    }
                )
            elif type(msg) is platform_message.Forward:
                for node in msg.node_list:
                    content_list.extend((await WecomMessageConverter.yiri2target(node.message_chain, bot)))
            else:
                content_list.append(
                    {
                        'type': 'text',
                        'content': str(msg),
                    }
                )

        return content_list

    @staticmethod
    async def target2yiri(message: str, message_id: int = -1):
        yiri_msg_list = []
        yiri_msg_list.append(platform_message.Source(id=message_id, time=datetime.datetime.now()))

        yiri_msg_list.append(platform_message.Plain(text=message))
        chain = platform_message.MessageChain(yiri_msg_list)

        return chain

    @staticmethod
    async def target2yiri_image(picurl: str, message_id: int = -1):
        yiri_msg_list = []
        yiri_msg_list.append(platform_message.Source(id=message_id, time=datetime.datetime.now()))
        image_base64, image_format = await image.get_wecom_image_base64(pic_url=picurl)
        yiri_msg_list.append(platform_message.Image(base64=f'data:image/{image_format};base64,{image_base64}'))
        chain = platform_message.MessageChain(yiri_msg_list)

        return chain


class WecomEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.Event, bot_account_id: int, bot: WecomClient) -> WecomEvent:
        # only for extracting user information

        if type(event) is platform_events.GroupMessage:
            pass

        if type(event) is platform_events.FriendMessage:
            payload = {
                'MsgType': 'text',
                'Content': '',
                'FromUserName': event.sender.id,
                'ToUserName': bot_account_id,
                'CreateTime': int(datetime.datetime.now().timestamp()),
                'AgentID': event.sender.nickname,
            }
            wecom_event = WecomEvent.from_payload(payload=payload)
            if not wecom_event:
                raise ValueError('无法从 message_data 构造 WecomEvent 对象')

            return wecom_event

    @staticmethod
    async def target2yiri(event: WecomEvent):
        """
        将 WecomEvent 转换为平台的 FriendMessage 对象。

        Args:
            event (WecomEvent): 企业微信事件。

        Returns:
            platform_events.FriendMessage: 转换后的 FriendMessage 对象。
        """
        # 转换消息链
        if event.type == 'text':
            yiri_chain = await WecomMessageConverter.target2yiri(event.message, event.message_id)
            friend = platform_entities.Friend(
                id=f'u{event.user_id}',
                nickname=str(event.agent_id),
                remark='',
            )

            return platform_events.FriendMessage(sender=friend, message_chain=yiri_chain, time=event.timestamp)
        elif event.type == 'image':
            friend = platform_entities.Friend(
                id=f'u{event.user_id}',
                nickname=str(event.agent_id),
                remark='',
            )

            yiri_chain = await WecomMessageConverter.target2yiri_image(picurl=event.picurl, message_id=event.message_id)

            return platform_events.FriendMessage(sender=friend, message_chain=yiri_chain, time=event.timestamp)


class WecomAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    bot: WecomClient
    bot_account_id: str
    message_converter: WecomMessageConverter = WecomMessageConverter()
    event_converter: WecomEventConverter = WecomEventConverter()
    config: dict

    def __init__(self, config: dict, logger: EventLogger):
        # 校验必填项
        required_keys = [
            'corpid',
            'secret',
            'token',
            'EncodingAESKey',
            'contacts_secret',
        ]
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            raise Exception(f'Wecom 缺少配置项: {missing_keys}')

        # 创建运行时 bot 对象
        bot = WecomClient(
            corpid=config['corpid'],
            secret=config['secret'],
            token=config['token'],
            EncodingAESKey=config['EncodingAESKey'],
            contacts_secret=config['contacts_secret'],
            logger=logger,
        )

        super().__init__(
            config=config,
            logger=logger,
            bot=bot,
            bot_account_id='',
        )

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        Wecom_event = await WecomEventConverter.yiri2target(message_source, self.bot_account_id, self.bot)
        content_list = await WecomMessageConverter.yiri2target(message, self.bot)
        fixed_user_id = Wecom_event.user_id
        # 删掉开头的u
        fixed_user_id = fixed_user_id[1:]
        for content in content_list:
            if content['type'] == 'text':
                await self.bot.send_private_msg(fixed_user_id, Wecom_event.agent_id, content['content'])
            elif content['type'] == 'image':
                await self.bot.send_image(fixed_user_id, Wecom_event.agent_id, content['media_id'])

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        """企业微信目前只有发送给个人的方法，
        构造target_id的方式为前半部分为账户id，后半部分为agent_id,中间使用“|”符号隔开。
        """
        content_list = await WecomMessageConverter.yiri2target(message, self.bot)
        parts = target_id.split('|')
        user_id = parts[0]
        agent_id = int(parts[1])
        if target_type == 'person':
            for content in content_list:
                if content['type'] == 'text':
                    await self.bot.send_private_msg(user_id, agent_id, content['content'])
                if content['type'] == 'image':
                    await self.bot.send_image(user_id, agent_id, content['media'])

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        async def on_message(event: WecomEvent):
            self.bot_account_id = event.receiver_id
            try:
                return await callback(await self.event_converter.target2yiri(event), self)
            except Exception:
                await self.logger.error(f'Error in wecom callback: {traceback.format_exc()}')

        if event_type == platform_events.FriendMessage:
            self.bot.on_message('text')(on_message)
            self.bot.on_message('image')(on_message)
        elif event_type == platform_events.GroupMessage:
            pass

    async def run_async(self):
        async def shutdown_trigger_placeholder():
            while True:
                await asyncio.sleep(1)

        await self.bot.run_task(
            host=self.config['host'],
            port=self.config['port'],
            shutdown_trigger=shutdown_trigger_placeholder,
        )

    async def kill(self) -> bool:
        return False

    async def unregister_listener(
        self,
        event_type: type,
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        return super().unregister_listener(event_type, callback)

    async def is_muted(self, group_id: int) -> bool:
        pass
