import traceback
import typing
from langbot.libs.dingtalk_api.dingtalkevent import DingTalkEvent
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
from langbot.libs.dingtalk_api.api import DingTalkClient
import datetime
from langbot.pkg.platform.logger import EventLogger


class DingTalkMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain):
        content = ''
        at = False
        for msg in message_chain:
            if type(msg) is platform_message.At:
                at = True
            if type(msg) is platform_message.Plain:
                content += msg.text
            if type(msg) is platform_message.Forward:
                for node in msg.node_list:
                    content += (await DingTalkMessageConverter.yiri2target(node.message_chain))[0]
        return content, at

    @staticmethod
    async def target2yiri(event: DingTalkEvent, bot_name: str):
        yiri_msg_list = []
        yiri_msg_list.append(
            platform_message.Source(id=event.incoming_message.message_id, time=datetime.datetime.now())
        )

        for atUser in event.incoming_message.at_users:
            if atUser.dingtalk_id == event.incoming_message.chatbot_user_id:
                yiri_msg_list.append(platform_message.At(target=bot_name))

        if event.rich_content:
            elements = event.rich_content.get('Elements')
            for element in elements:
                if element.get('Type') == 'text':
                    text = element.get('Content', '').replace('@' + bot_name, '')
                    if text.strip():
                        yiri_msg_list.append(platform_message.Plain(text=text))
                elif element.get('Type') == 'image' and element.get('Picture'):
                    yiri_msg_list.append(platform_message.Image(base64=element['Picture']))
        else:
            # 回退到原有简单逻辑
            if event.content:
                text_content = event.content.replace('@' + bot_name, '')
                yiri_msg_list.append(platform_message.Plain(text=text_content))
            if event.picture:
                yiri_msg_list.append(platform_message.Image(base64=event.picture))

            # 处理其他类型消息（文件、音频等）
        if event.file:
            yiri_msg_list.append(platform_message.File(url=event.file, name=event.name))
        if event.audio:
            yiri_msg_list.append(platform_message.Voice(base64=event.audio))

        chain = platform_message.MessageChain(yiri_msg_list)

        return chain


class DingTalkEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent):
        return event.source_platform_object

    @staticmethod
    async def target2yiri(event: DingTalkEvent, bot_name: str):
        message_chain = await DingTalkMessageConverter.target2yiri(event, bot_name)

        if event.conversation == 'FriendMessage':
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event.incoming_message.sender_staff_id,
                    nickname=event.incoming_message.sender_nick,
                    remark='',
                ),
                message_chain=message_chain,
                time=event.incoming_message.create_at,
                source_platform_object=event,
            )
        elif event.conversation == 'GroupMessage':
            sender = platform_entities.GroupMember(
                id=event.incoming_message.sender_staff_id,
                member_name=event.incoming_message.sender_nick,
                permission='MEMBER',
                group=platform_entities.Group(
                    id=event.incoming_message.conversation_id,
                    name=event.incoming_message.conversation_title,
                    permission=platform_entities.Permission.Member,
                ),
                special_title='',
                join_timestamp=0,
                last_speak_timestamp=0,
                mute_time_remaining=0,
            )
            time = event.incoming_message.create_at
            return platform_events.GroupMessage(
                sender=sender,
                message_chain=message_chain,
                time=time,
                source_platform_object=event,
            )


class DingTalkAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    bot: DingTalkClient
    bot_account_id: str
    message_converter: DingTalkMessageConverter = DingTalkMessageConverter()
    event_converter: DingTalkEventConverter = DingTalkEventConverter()
    config: dict
    card_instance_id_dict: (
        dict  # 回复卡片消息字典，key为消息id，value为回复卡片实例id，用于在流式消息时判断是否发送到指定卡片
    )

    def __init__(self, config: dict, logger: EventLogger):
        required_keys = [
            'client_id',
            'client_secret',
            'robot_name',
            'robot_code',
        ]
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            raise Exception('钉钉缺少相关配置项，请查看文档或联系管理员')
        bot = DingTalkClient(
            client_id=config['client_id'],
            client_secret=config['client_secret'],
            robot_name=config['robot_name'],
            robot_code=config['robot_code'],
            markdown_card=config['markdown_card'],
            logger=logger,
        )
        bot_account_id = config['robot_name']
        super().__init__(
            config=config,
            logger=logger,
            card_instance_id_dict={},
            bot_account_id=bot_account_id,
            bot=bot,
            listeners={},
        )

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        event = await DingTalkEventConverter.yiri2target(
            message_source,
        )
        incoming_message = event.incoming_message

        content, at = await DingTalkMessageConverter.yiri2target(message)
        await self.bot.send_message(content, incoming_message, at)

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        # event = await DingTalkEventConverter.yiri2target(
        #     message_source,
        # )
        # incoming_message = event.incoming_message

        # msg_id = incoming_message.message_id
        message_id = bot_message.resp_message_id
        msg_seq = bot_message.msg_sequence

        if (msg_seq - 1) % 8 == 0 or is_final:
            content, at = await DingTalkMessageConverter.yiri2target(message)

            card_instance, card_instance_id = self.card_instance_id_dict[message_id]
            if not content and bot_message.content:
                content = bot_message.content  # 兼容直接传入content的情况
            # print(card_instance_id)
            if content:
                await self.bot.send_card_message(card_instance, card_instance_id, content, is_final)
            if is_final and bot_message.tool_calls is None:
                # self.seq = 1  # 消息回复结束之后重置seq
                self.card_instance_id_dict.pop(message_id)  # 消息回复结束之后删除卡片实例id

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        content = await DingTalkMessageConverter.yiri2target(message)
        if target_type == 'person':
            await self.bot.send_proactive_message_to_one(target_id, content)
        if target_type == 'group':
            await self.bot.send_proactive_message_to_group(target_id, content)

    async def is_stream_output_supported(self) -> bool:
        is_stream = False
        if self.config.get('enable-stream-reply', None):
            is_stream = True
        return is_stream

    async def create_message_card(self, message_id, event):
        card_template_id = self.config['card_template_id']
        incoming_message = event.source_platform_object.incoming_message
        # message_id = incoming_message.message_id
        card_instance, card_instance_id = await self.bot.create_and_card(card_template_id, incoming_message)
        self.card_instance_id_dict[message_id] = (card_instance, card_instance_id)
        return True

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        async def on_message(event: DingTalkEvent):
            try:
                return await callback(
                    await self.event_converter.target2yiri(event, self.config['robot_name']),
                    self,
                )
            except Exception:
                await self.logger.error(f'Error in dingtalk callback: {traceback.format_exc()}')

        if event_type == platform_events.FriendMessage:
            self.bot.on_message('FriendMessage')(on_message)
        elif event_type == platform_events.GroupMessage:
            self.bot.on_message('GroupMessage')(on_message)

    async def run_async(self):
        await self.bot.start()

    async def kill(self) -> bool:
        return False

    async def is_muted(self) -> bool:
        return False

    async def unregister_listener(
        self,
        event_type: type,
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        return super().unregister_listener(event_type, callback)
