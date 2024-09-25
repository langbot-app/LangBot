from __future__ import annotations
import typing
import asyncio
import traceback
import time
import datetime

# import mirai
# import mirai.models.message as yiri_message
import aiocqhttp

from .. import adapter
from ...pipeline.longtext.strategies import forward
from ...core import app
from ..types import message as platform_message
from ..types import events as platform_events
from ..types import entities as platform_entities


class AiocqhttpMessageConverter(adapter.MessageConverter):

    @staticmethod
    def yiri2target(message_chain: platform_message.MessageChain) -> typing.Tuple[list, int, datetime.datetime]:
        msg_list = aiocqhttp.Message()

        msg_id = 0
        msg_time = None

        for msg in message_chain:
            if type(msg) is platform_message.Plain:
                msg_list.append(aiocqhttp.MessageSegment.text(msg.text))
            elif type(msg) is platform_message.Source:
                msg_id = msg.id
                msg_time = msg.time
            elif type(msg) is platform_message.Image:
                arg = ''
                if msg.base64:
                    arg = msg.base64
                    msg_list.append(aiocqhttp.MessageSegment.image(f"base64://{arg}"))
                elif msg.url:
                    arg = msg.url
                    msg_list.append(aiocqhttp.MessageSegment.image(arg))
                elif msg.path:
                    arg = msg.path
                    msg_list.append(aiocqhttp.MessageSegment.image(arg))
            elif type(msg) is platform_message.At:
                msg_list.append(aiocqhttp.MessageSegment.at(msg.target))
            elif type(msg) is platform_message.AtAll:
                msg_list.append(aiocqhttp.MessageSegment.at("all"))
            elif type(msg) is platform_message.Voice:
                arg = ''
                if msg.base64:
                    arg = msg.base64
                    msg_list.append(aiocqhttp.MessageSegment.record(f"base64://{arg}"))
                elif msg.url:
                    arg = msg.url
                    msg_list.append(aiocqhttp.MessageSegment.record(arg))
                elif msg.path:
                    arg = msg.path
                    msg_list.append(aiocqhttp.MessageSegment.record(msg.path))
            elif type(msg) is forward.Forward:

                for node in msg.node_list:
                    msg_list.extend(AiocqhttpMessageConverter.yiri2target(node.message_chain)[0])
                
            else:
                msg_list.append(aiocqhttp.MessageSegment.text(str(msg)))

        return msg_list, msg_id, msg_time

    @staticmethod
    def target2yiri(message: str, message_id: int = -1):
        message = aiocqhttp.Message(message)

        yiri_msg_list = []

        yiri_msg_list.append(
            platform_message.Source(id=message_id, time=datetime.datetime.now())
        )

        for msg in message:
            if msg.type == "at":
                if msg.data["qq"] == "all":
                    yiri_msg_list.append(platform_message.AtAll())
                else:
                    yiri_msg_list.append(
                        platform_message.At(
                            target=msg.data["qq"],
                        )
                    )
            elif msg.type == "text":
                yiri_msg_list.append(platform_message.Plain(text=msg.data["text"]))
            elif msg.type == "image":
                yiri_msg_list.append(platform_message.Image(url=msg.data["url"]))

        chain = platform_message.MessageChain(yiri_msg_list)

        return chain


class AiocqhttpEventConverter(adapter.EventConverter):

    @staticmethod
    def yiri2target(event: platform_events.Event, bot_account_id: int):

        msg, msg_id, msg_time = AiocqhttpMessageConverter.yiri2target(event.message_chain)

        if type(event) is platform_events.GroupMessage:
            role = "member"

            if event.sender.permission == "ADMINISTRATOR":
                role = "admin"
            elif event.sender.permission == "OWNER":
                role = "owner"

            payload = {
                "post_type": "message",
                "message_type": "group",
                "time": int(msg_time.timestamp()),
                "self_id": bot_account_id,
                "sub_type": "normal",
                "anonymous": None,
                "font": 0,
                "message": str(msg),
                "raw_message": str(msg),
                "sender": {
                    "age": 0,
                    "area": "",
                    "card": "",
                    "level": "",
                    "nickname": event.sender.member_name,
                    "role": role,
                    "sex": "unknown",
                    "title": "",
                    "user_id": event.sender.id,
                },
                "user_id": event.sender.id,
                "message_id": msg_id,
                "group_id": event.group.id,
                "message_seq": 0,
            }

            return aiocqhttp.Event.from_payload(payload)
        elif type(event) is platform_events.FriendMessage:

            payload = {
                "post_type": "message",
                "message_type": "private",
                "time": int(msg_time.timestamp()),
                "self_id": bot_account_id,
                "sub_type": "friend",
                "target_id": bot_account_id,
                "message": str(msg),
                "raw_message": str(msg),
                "font": 0,
                "sender": {
                    "age": 0,
                    "nickname": event.sender.nickname,
                    "sex": "unknown",
                    "user_id": event.sender.id,
                },
                "message_id": msg_id,
                "user_id": event.sender.id,
            }
            
            return aiocqhttp.Event.from_payload(payload)

    @staticmethod
    def target2yiri(event: aiocqhttp.Event):
        yiri_chain = AiocqhttpMessageConverter.target2yiri(
            event.message, event.message_id
        )

        if event.message_type == "group":
            permission = "MEMBER"

            if "role" in event.sender:
                if event.sender["role"] == "admin":
                    permission = "ADMINISTRATOR"
                elif event.sender["role"] == "owner":
                    permission = "OWNER"
            converted_event = platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=event.sender["user_id"],  # message_seq 放哪？
                    member_name=event.sender["nickname"],
                    permission=permission,
                    group=platform_entities.Group(
                        id=event.group_id,
                        name=event.sender["nickname"],
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title=event.sender["title"] if "title" in event.sender else "",
                    join_timestamp=0,
                    last_speak_timestamp=0,
                    mute_time_remaining=0,
                ),
                message_chain=yiri_chain,
                time=event.time,
            )
            return converted_event
        elif event.message_type == "private":
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event.sender["user_id"],
                    nickname=event.sender["nickname"],
                    remark="",
                ),
                message_chain=yiri_chain,
                time=event.time,
            )


@adapter.adapter_class("aiocqhttp")
class AiocqhttpAdapter(adapter.MessageSourceAdapter):

    bot: aiocqhttp.CQHttp

    bot_account_id: int

    message_converter: AiocqhttpMessageConverter = AiocqhttpMessageConverter()
    event_converter: AiocqhttpEventConverter = AiocqhttpEventConverter()

    config: dict

    ap: app.Application

    def __init__(self, config: dict, ap: app.Application):
        self.config = config

        async def shutdown_trigger_placeholder():
            while True:
                await asyncio.sleep(1)
        
        self.config['shutdown_trigger'] = shutdown_trigger_placeholder

        self.ap = ap

        if "access-token" in config:
            self.bot = aiocqhttp.CQHttp(access_token=config["access-token"])
            del self.config["access-token"]
        else:
            self.bot = aiocqhttp.CQHttp()

    async def send_message(
        self, target_type: str, target_id: str, message: platform_message.MessageChain
    ):
        aiocq_msg = AiocqhttpMessageConverter.yiri2target(message)[0]

        if target_type == "group":
            await self.bot.send_group_msg(group_id=int(target_id), message=aiocq_msg)
        elif target_type == "person":
            await self.bot.send_private_msg(user_id=int(target_id), message=aiocq_msg)

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):  
        aiocq_event = AiocqhttpEventConverter.yiri2target(message_source, self.bot_account_id)
        aiocq_msg = AiocqhttpMessageConverter.yiri2target(message)[0]
        if quote_origin:
            aiocq_msg = aiocqhttp.MessageSegment.reply(aiocq_event.message_id) + aiocq_msg

        return await self.bot.send(
            aiocq_event,
            aiocq_msg
        )

    async def is_muted(self, group_id: int) -> bool:
        return False

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[[platform_events.Event, adapter.MessageSourceAdapter], None],
    ):
        async def on_message(event: aiocqhttp.Event):
            self.bot_account_id = event.self_id
            try:
                return await callback(self.event_converter.target2yiri(event), self)
            except:
                traceback.print_exc()

        if event_type == platform_events.GroupMessage:
            self.bot.on_message("group")(on_message)
        elif event_type == platform_events.FriendMessage:
            self.bot.on_message("private")(on_message)

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[[platform_events.Event, adapter.MessageSourceAdapter], None],
    ):
        return super().unregister_listener(event_type, callback)

    async def run_async(self):
        await self.bot._server_app.run_task(**self.config)

    async def kill(self) -> bool:
        return False
