
import traceback
import typing
from libs.dingtalk_api.dingtalkevent import DingTalkEvent
from pkg.platform.types import message as platform_message
from pkg.platform.adapter import MessagePlatformAdapter
from pkg.platform.types import events as platform_events, message as platform_message
from pkg.core import app
from .. import adapter
from ...pipeline.longtext.strategies import forward
from ...core import app
from ..types import message as platform_message
from ..types import events as platform_events
from ..types import entities as platform_entities
from ...command.errors import ParamNotEnoughError
from libs.dingtalk_api.api import DingTalkClient
import datetime


class DingTalkMessageConverter(adapter.MessageConverter):

    @staticmethod
    async def yiri2target(
        message_chain:platform_message.MessageChain
    ):
        for msg in message_chain:
            if type(msg) is platform_message.Plain:
                return msg.text

    @staticmethod
    async def target2yiri(event:DingTalkEvent, bot_name:str):
        yiri_msg_list = []
        yiri_msg_list.append(
            platform_message.Source(id = event.incoming_message.message_id,time=datetime.datetime.now())
        )

        for atUser in event.incoming_message.at_users:
            if atUser.dingtalk_id == event.incoming_message.chatbot_user_id:
                yiri_msg_list.append(platform_message.At(target=bot_name))

        if event.content:
            text_content = event.content.replace("@"+bot_name, '')
            yiri_msg_list.append(platform_message.Plain(text=text_content))
        if event.picture:
            yiri_msg_list.append(platform_message.Image(base64=event.picture))
        if event.audio:
            yiri_msg_list.append(platform_message.Voice(base64=event.audio))

        chain = platform_message.MessageChain(yiri_msg_list)
        
        return chain


class DingTalkEventConverter(adapter.EventConverter):

    @staticmethod
    async def yiri2target(
        event:platform_events.MessageEvent
    ):
        return event.source_platform_object

    @staticmethod
    async def target2yiri(
        event:DingTalkEvent,
        bot_name:str
    ):
        
        message_chain = await DingTalkMessageConverter.target2yiri(event, bot_name)


        if event.conversation == 'FriendMessage':

            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event.incoming_message.sender_id,
                    nickname = event.incoming_message.sender_nick,
                    remark=""
                ),
                message_chain = message_chain,
                time = event.incoming_message.create_at,
                source_platform_object=event,
            )
        elif event.conversation == 'GroupMessage':
            sender = platform_entities.GroupMember(
                id = event.incoming_message.sender_id,
                member_name=event.incoming_message.sender_nick,
                permission= 'MEMBER',
                group = platform_entities.Group(
                    id = event.incoming_message.conversation_id,
                    name = event.incoming_message.conversation_title,
                    permission=platform_entities.Permission.Member
                ),
                special_title='',
                join_timestamp=0,
                last_speak_timestamp=0,
                mute_time_remaining=0
            )
            time = event.incoming_message.create_at
            return platform_events.GroupMessage(
                sender =sender,
                message_chain = message_chain,
                time = time,
                source_platform_object=event
            )


class DingTalkAdapter(adapter.MessagePlatformAdapter):
    bot: DingTalkClient
    ap: app.Application
    bot_account_id: str
    message_converter: DingTalkMessageConverter = DingTalkMessageConverter()
    event_converter: DingTalkEventConverter = DingTalkEventConverter()
    config: dict

    def __init__(self,config:dict,ap:app.Application):
        self.config = config
        self.ap = ap
        required_keys = [
            "client_id",
            "client_secret",
            "robot_name",
            "robot_code",
        ]
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            raise ParamNotEnoughError("钉钉缺少相关配置项，请查看文档或联系管理员")

        self.bot_account_id = self.config["robot_name"]
        
        self.bot = DingTalkClient(
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            robot_name = config["robot_name"],
            robot_code=config["robot_code"]
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

        content = await DingTalkMessageConverter.yiri2target(message)
        await self.bot.send_message(content,incoming_message)


    async def send_message(
        self, target_type: str, target_id: str, message: platform_message.MessageChain
    ):
        pass

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, adapter.MessagePlatformAdapter], None
        ],
    ):
        async def on_message(event: DingTalkEvent):
            try:
                return await callback(
                    await self.event_converter.target2yiri(event, self.config["robot_name"]), self
                )
            except:
                traceback.print_exc()

        if event_type == platform_events.FriendMessage:
            self.bot.on_message("FriendMessage")(on_message)
        elif event_type == platform_events.GroupMessage:
            self.bot.on_message("GroupMessage")(on_message)

    async def run_async(self):
        await self.bot.start()

    async def kill(self) -> bool:
        return False

    async def unregister_listener(
        self,
        event_type: type,
        callback: typing.Callable[[platform_events.Event, MessagePlatformAdapter], None],
    ):
        return super().unregister_listener(event_type, callback)

