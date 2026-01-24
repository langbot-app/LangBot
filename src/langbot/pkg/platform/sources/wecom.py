from __future__ import annotations
import typing
import asyncio
import traceback

import datetime

from langbot.libs.wecom_api.api import WecomClient
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot.libs.wecom_api.wecomevent import WecomEvent
from ...utils import image
from ..logger import EventLogger
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities


def split_string_by_bytes(text, limit=2048, encoding='utf-8'):
    """
    Splits a string into a list of strings, where each part is at most 'limit' bytes.

    Args:
        text (str): The original string to split.
        limit (int): The maximum byte size for each split part.
        encoding (str): The encoding to use (default is 'utf-8').

    Returns:
        list: A list of split strings.
    """
    # 1. Encode the entire string into bytes
    bytes_data = text.encode(encoding)
    total_len = len(bytes_data)

    parts = []
    start = 0

    while start < total_len:
        # 2. Determine the end index for the current chunk
        # It shouldn't exceed the total length
        end = min(start + limit, total_len)

        # 3. Slice the byte array
        chunk = bytes_data[start:end]

        # 4. Attempt to decode the chunk
        # Use errors='ignore' to drop any partial bytes at the end of the chunk
        # (e.g., if a 3-byte character was cut after the 2nd byte)
        part_str = chunk.decode(encoding, errors='ignore')

        # 5. Calculate the actual byte length of the successfully decoded string
        # This tells us exactly where the valid character boundary ended
        part_bytes = part_str.encode(encoding)
        part_len = len(part_bytes)

        # Safety check: Prevent infinite loop if limit is too small (e.g., limit=1 for a Chinese char)
        if part_len == 0 and end < total_len:
            # Force advance by 1 byte to consume the un-decodable byte or raise error
            # Here we just treat it as a part to avoid stuck loops, though it might be invalid
            start += 1
            continue

        parts.append(part_str)

        # 6. Move the start pointer by the actual length consumed
        start += part_len

    return parts


class WecomMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain, bot: WecomClient):
        content_list = []

        for msg in message_chain:
            if type(msg) is platform_message.Plain:
                chunks = split_string_by_bytes(msg.text)
                content_list.extend(
                    [
                        {
                            'type': 'text',
                            'content': chunk,
                        }
                        for chunk in chunks
                    ]
                )
            elif type(msg) is platform_message.Image:
                content_list.append(
                    {
                        'type': 'image',
                        'media_id': await bot.get_media_id(msg),
                    }
                )
            elif type(msg) is platform_message.Voice:
                content_list.append(
                    {
                        'type': 'voice',
                        'media_id': await bot.get_media_id(msg),
                    }
                )
            elif type(msg) is platform_message.File:
                content_list.append(
                    {
                        'type': 'file',
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
    bot_uuid: str = None

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

        # 创建运行时 bot 对象，始终使用统一 webhook 模式
        bot = WecomClient(
            corpid=config['corpid'],
            secret=config['secret'],
            token=config['token'],
            EncodingAESKey=config['EncodingAESKey'],
            contacts_secret=config['contacts_secret'],
            logger=logger,
            unified_mode=True,
            api_base_url=config.get('api_base_url', 'https://qyapi.weixin.qq.com/cgi-bin'),
        )

        super().__init__(
            config=config,
            logger=logger,
            bot=bot,
            bot_account_id='',
        )

    def set_bot_uuid(self, bot_uuid: str):
        """设置 bot UUID（用于生成 webhook URL）"""
        self.bot_uuid = bot_uuid

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
            elif content['type'] == 'voice':
                await self.bot.send_voice(fixed_user_id, Wecom_event.agent_id, content['media_id'])
            elif content['type'] == 'file':
                await self.bot.send_file(fixed_user_id, Wecom_event.agent_id, content['media_id'])

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
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
                if content['type'] == 'voice':
                    await self.bot.send_voice(user_id, agent_id, content['media'])
                if content['type'] == 'file':
                    await self.bot.send_file(user_id, agent_id, content['media'])

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

    async def handle_unified_webhook(self, bot_uuid: str, path: str, request):
        """处理统一 webhook 请求。

        Args:
            bot_uuid: Bot 的 UUID
            path: 子路径（如果有的话）
            request: Quart Request 对象

        Returns:
            响应数据
        """
        return await self.bot.handle_unified_webhook(request)

    async def run_async(self):
        async def keep_alive():
            while True:
                await asyncio.sleep(1)

        await keep_alive()

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
