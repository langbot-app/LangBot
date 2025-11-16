from __future__ import annotations
import typing
import asyncio
import traceback

import datetime
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
from langbot.pkg.platform.logger import EventLogger
from langbot.libs.wecom_ai_bot_api.wecombotevent import WecomBotEvent
from langbot.libs.wecom_ai_bot_api.api import WecomBotClient


class WecomBotMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain):
        content = ''
        for msg in message_chain:
            if type(msg) is platform_message.Plain:
                content += msg.text
        return content

    @staticmethod
    async def target2yiri(event: WecomBotEvent):
        yiri_msg_list = []
        if event.type == 'group':
            yiri_msg_list.append(platform_message.At(target=event.ai_bot_id))
        yiri_msg_list.append(platform_message.Source(id=event.message_id, time=datetime.datetime.now()))
        yiri_msg_list.append(platform_message.Plain(text=event.content))
        if event.picurl != '':
            yiri_msg_list.append(platform_message.Image(base64=event.picurl))
        chain = platform_message.MessageChain(yiri_msg_list)

        return chain


class WecomBotEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent):
        return event.source_platform_object

    @staticmethod
    async def target2yiri(event: WecomBotEvent):
        message_chain = await WecomBotMessageConverter.target2yiri(event)
        if event.type == 'single':
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event.userid,
                    nickname=event.username,
                    remark='',
                ),
                message_chain=message_chain,
                time=datetime.datetime.now().timestamp(),
                source_platform_object=event,
            )
        elif event.type == 'group':
            try:
                sender = platform_entities.GroupMember(
                    id=event.userid,
                    permission='MEMBER',
                    member_name=event.username,
                    group=platform_entities.Group(
                        id=str(event.chatid),
                        name=event.chatname,
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                    join_timestamp=0,
                    last_speak_timestamp=0,
                    mute_time_remaining=0,
                )
                time = datetime.datetime.now().timestamp()
                return platform_events.GroupMessage(
                    sender=sender,
                    message_chain=message_chain,
                    time=time,
                    source_platform_object=event,
                )
            except Exception:
                print(traceback.format_exc())


class WecomBotAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    bot: WecomBotClient
    bot_account_id: str
    message_converter: WecomBotMessageConverter = WecomBotMessageConverter()
    event_converter: WecomBotEventConverter = WecomBotEventConverter()
    config: dict

    def __init__(self, config: dict, logger: EventLogger):
        required_keys = ['Token', 'EncodingAESKey', 'Corpid', 'BotId', 'port']
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            raise Exception(f'WecomBot 缺少配置项: {missing_keys}')

        # 创建运行时 bot 对象
        bot = WecomBotClient(
            Token=config['Token'],
            EnCodingAESKey=config['EncodingAESKey'],
            Corpid=config['Corpid'],
            logger=logger,
        )
        bot_account_id = config['BotId']

        super().__init__(
            config=config,
            logger=logger,
            bot=bot,
            bot_account_id=bot_account_id,
        )

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        content = await self.message_converter.yiri2target(message)
        await self.bot.set_message(message_source.source_platform_object.message_id, content)

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        """将流水线增量输出写入企业微信 stream 会话。

        Args:
            message_source: 流水线提供的原始消息事件。
            bot_message: 当前片段对应的模型元信息（未使用）。
            message: 需要回复的消息链。
            quote_origin: 是否引用原消息（企业微信暂不支持）。
            is_final: 标记当前片段是否为最终回复。

        Returns:
            dict: 包含 `stream` 键，标识写入是否成功。

        Example:
            在流水线 `reply_message_chunk` 调用中自动触发，无需手动调用。
        """
        # 转换为纯文本（智能机器人当前协议仅支持文本流）
        content = await self.message_converter.yiri2target(message)
        msg_id = message_source.source_platform_object.message_id

        # 将片段推送到 WecomBotClient 中的队列，返回值用于判断是否走降级逻辑
        success = await self.bot.push_stream_chunk(msg_id, content, is_final=is_final)
        if not success and is_final:
            # 未命中流式队列时使用旧有 set_message 兜底
            await self.bot.set_message(msg_id, content)
        return {'stream': success}

    async def is_stream_output_supported(self) -> bool:
        """智能机器人侧默认开启流式能力。

        Returns:
            bool: 恒定返回 True。

        Example:
            流水线执行阶段会调用此方法以确认是否启用流式。"""
        return True

    async def send_message(self, target_type, target_id, message):
        pass

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        async def on_message(event: WecomBotEvent):
            try:
                return await callback(await self.event_converter.target2yiri(event), self)
            except Exception:
                await self.logger.error(f'Error in wecombot callback: {traceback.format_exc()}')
                print(traceback.format_exc())

        try:
            if event_type == platform_events.FriendMessage:
                self.bot.on_message('single')(on_message)
            elif event_type == platform_events.GroupMessage:
                self.bot.on_message('group')(on_message)
        except Exception:
            print(traceback.format_exc())

    async def run_async(self):
        async def shutdown_trigger_placeholder():
            while True:
                await asyncio.sleep(1)

        await self.bot.run_task(
            host='0.0.0.0',
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
