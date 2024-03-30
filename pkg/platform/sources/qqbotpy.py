from __future__ import annotations

import logging
import typing
import datetime
import asyncio
import re
import traceback
import json
import threading

import mirai
import botpy
import botpy.message as botpy_message
import botpy.types.message as botpy_message_type

from .. import adapter as adapter_model
from ...pipeline.longtext.strategies import forward
from ...core import app
from ...config import manager as cfg_mgr


class OfficialGroupMessage(mirai.GroupMessage):
    pass


event_handler_mapping = {
    mirai.GroupMessage: ["on_at_message_create", "on_group_at_message_create"],
    mirai.FriendMessage: ["on_direct_message_create"],
}


cached_message_ids = {}
"""由于QQ官方的消息id是字符串，而YiriMirai的消息id是整数，所以需要一个索引来进行转换"""

id_index = 0


def save_msg_id(message_id: str) -> int:
    """保存消息id"""
    global id_index, cached_message_ids

    crt_index = id_index
    id_index += 1
    cached_message_ids[str(crt_index)] = message_id
    return crt_index


def char_to_value(char):
    """将单个字符转换为相应的数值。"""
    if '0' <= char <= '9':
        return ord(char) - ord('0')
    elif 'A' <= char <= 'Z':
        return ord(char) - ord('A') + 10
    
    return ord(char) - ord('a') + 36

def digest(s: str) -> int:
    """计算字符串的hash值。"""
    # 取末尾的8位
    sub_s = s[-10:]

    number = 0
    base = 36

    for i in range(len(sub_s)):
        number = number * base + char_to_value(sub_s[i])

    return number

K = typing.TypeVar("K")
V = typing.TypeVar("V")


class OpenIDMapping(typing.Generic[K, V]):

    map: dict[K, V]

    dump_func: typing.Callable

    digest_func: typing.Callable[[K], V]

    def __init__(self, map: dict[K, V], dump_func: typing.Callable, digest_func: typing.Callable[[K], V] = digest):
        self.map = map

        self.dump_func = dump_func

        self.digest_func = digest_func

    def __getitem__(self, key: K) -> V:
        return self.map[key]

    def __setitem__(self, key: K, value: V):
        self.map[key] = value
        self.dump_func()

    def __contains__(self, key: K) -> bool:
        return key in self.map

    def __delitem__(self, key: K):
        del self.map[key]
        self.dump_func()

    def getkey(self, value: V) -> K:
        return list(self.map.keys())[list(self.map.values()).index(value)]
    
    def save_openid(self, key: K) -> V:
        
        if key in self.map:
            return self.map[key]
        
        value = self.digest_func(key)

        self.map[key] = value

        self.dump_func()

        return value


class OfficialMessageConverter(adapter_model.MessageConverter):
    """QQ 官方消息转换器"""

    @staticmethod
    def yiri2target(message_chain: mirai.MessageChain):
        """将 YiriMirai 的消息链转换为 QQ 官方消息"""

        msg_list = []
        if type(message_chain) is mirai.MessageChain:
            msg_list = message_chain.__root__
        elif type(message_chain) is list:
            msg_list = message_chain
        elif type(message_chain) is str:
            msg_list = [mirai.Plain(text=message_chain)]
        else:
            raise Exception(
                "Unknown message type: " + str(message_chain) + str(type(message_chain))
            )

        offcial_messages: list[dict] = []
        """
        {
            "type": "text",
            "content": "Hello World!"
        }

        {
            "type": "image",
            "content": "https://example.com/example.jpg"
        }
        """

        # 遍历并转换
        for component in msg_list:
            if type(component) is mirai.Plain:
                offcial_messages.append({"type": "text", "content": component.text})
            elif type(component) is mirai.Image:
                if component.url is not None:
                    offcial_messages.append({"type": "image", "content": component.url})
                elif component.path is not None:
                    offcial_messages.append(
                        {"type": "file_image", "content": component.path}
                    )
            elif type(component) is mirai.At:
                offcial_messages.append({"type": "at", "content": ""})
            elif type(component) is mirai.AtAll:
                print(
                    "上层组件要求发送 AtAll 消息，但 QQ 官方 API 不支持此消息类型，忽略此消息。"
                )
            elif type(component) is mirai.Voice:
                print(
                    "上层组件要求发送 Voice 消息，但 QQ 官方 API 不支持此消息类型，忽略此消息。"
                )
            elif type(component) is forward.Forward:
                # 转发消息
                yiri_forward_node_list = component.node_list

                # 遍历并转换
                for yiri_forward_node in yiri_forward_node_list:
                    try:
                        message_chain = yiri_forward_node.message_chain

                        # 平铺
                        offcial_messages.extend(
                            OfficialMessageConverter.yiri2target(message_chain)
                        )
                    except Exception as e:
                        import traceback

                        traceback.print_exc()

        return offcial_messages

    @staticmethod
    def extract_message_chain_from_obj(
        message: typing.Union[botpy_message.Message, botpy_message.DirectMessage],
        message_id: str = None,
        bot_account_id: int = 0,
    ) -> mirai.MessageChain:
        yiri_msg_list = []

        # 存id

        yiri_msg_list.append(
            mirai.models.message.Source(
                id=save_msg_id(message_id), time=datetime.datetime.now()
            )
        )

        if type(message) is not botpy_message.DirectMessage:
            yiri_msg_list.append(mirai.At(target=bot_account_id))

        if hasattr(message, "mentions"):
            for mention in message.mentions:
                if mention.bot:
                    continue

                yiri_msg_list.append(mirai.At(target=mention.id))

        for attachment in message.attachments:
            if attachment.content_type == "image":
                yiri_msg_list.append(mirai.Image(url=attachment.url))
            else:
                logging.warning(
                    "不支持的附件类型：" + attachment.content_type + "，忽略此附件。"
                )

        content = re.sub(r"<@!\d+>", "", str(message.content))
        if content.strip() != "":
            yiri_msg_list.append(mirai.Plain(text=content))

        chain = mirai.MessageChain(yiri_msg_list)

        return chain


class OfficialEventConverter(adapter_model.EventConverter):
    """事件转换器"""

    member_openid_mapping: OpenIDMapping[str, int]
    group_openid_mapping: OpenIDMapping[str, int]

    def __init__(self, member_openid_mapping: OpenIDMapping[str, int], group_openid_mapping: OpenIDMapping[str, int]):
        self.member_openid_mapping = member_openid_mapping
        self.group_openid_mapping = group_openid_mapping

    def yiri2target(self, event: typing.Type[mirai.Event]):
        if event == mirai.GroupMessage:
            return botpy_message.Message
        elif event == mirai.FriendMessage:
            return botpy_message.DirectMessage
        else:
            raise Exception(
                "未支持转换的事件类型(YiriMirai -> Official): " + str(event)
            )

    def target2yiri(
        self,
        event: typing.Union[botpy_message.Message, botpy_message.DirectMessage]
    ) -> mirai.Event:
        import mirai.models.entities as mirai_entities

        if type(event) == botpy_message.Message:  # 频道内，转群聊事件
            permission = "MEMBER"

            if "2" in event.member.roles:
                permission = "ADMINISTRATOR"
            elif "4" in event.member.roles:
                permission = "OWNER"

            return mirai.GroupMessage(
                sender=mirai_entities.GroupMember(
                    id=event.author.id,
                    member_name=event.author.username,
                    permission=permission,
                    group=mirai_entities.Group(
                        id=event.channel_id,
                        name=event.author.username,
                        permission=mirai_entities.Permission.Member,
                    ),
                    special_title="",
                    join_timestamp=int(
                        datetime.datetime.strptime(
                            event.member.joined_at, "%Y-%m-%dT%H:%M:%S%z"
                        ).timestamp()
                    ),
                    last_speak_timestamp=datetime.datetime.now().timestamp(),
                    mute_time_remaining=0,
                ),
                message_chain=OfficialMessageConverter.extract_message_chain_from_obj(
                    event, event.id
                ),
                time=int(
                    datetime.datetime.strptime(
                        event.timestamp, "%Y-%m-%dT%H:%M:%S%z"
                    ).timestamp()
                ),
            )
        elif type(event) == botpy_message.DirectMessage:  # 私聊，转私聊事件
            return mirai.FriendMessage(
                sender=mirai_entities.Friend(
                    id=event.guild_id,
                    nickname=event.author.username,
                    remark=event.author.username,
                ),
                message_chain=OfficialMessageConverter.extract_message_chain_from_obj(
                    event, event.id
                ),
                time=int(
                    datetime.datetime.strptime(
                        event.timestamp, "%Y-%m-%dT%H:%M:%S%z"
                    ).timestamp()
                ),
            )
        elif type(event) == botpy_message.GroupMessage:

            replacing_member_id = self.member_openid_mapping.save_openid(event.author.member_openid)

            return OfficialGroupMessage(
                sender=mirai_entities.GroupMember(
                    id=replacing_member_id,
                    member_name=replacing_member_id,
                    permission="MEMBER",
                    group=mirai_entities.Group(
                        id=self.group_openid_mapping.save_openid(event.group_openid),
                        name=replacing_member_id,
                        permission=mirai_entities.Permission.Member,
                    ),
                    special_title="",
                    join_timestamp=int(0),
                    last_speak_timestamp=datetime.datetime.now().timestamp(),
                    mute_time_remaining=0,
                ),
                message_chain=OfficialMessageConverter.extract_message_chain_from_obj(
                    event, event.id
                ),
                time=int(
                    datetime.datetime.strptime(
                        event.timestamp, "%Y-%m-%dT%H:%M:%S%z"
                    ).timestamp()
                ),
            )


@adapter_model.adapter_class("qq-botpy")
class OfficialAdapter(adapter_model.MessageSourceAdapter):
    """QQ 官方消息适配器"""

    bot: botpy.Client = None

    bot_account_id: int = 0

    message_converter: OfficialMessageConverter
    event_converter: OfficialEventConverter

    cfg: dict = None

    cached_official_messages: dict = {}
    """缓存的 qq-botpy 框架消息对象
    
    message_id: botpy_message.Message | botpy_message.DirectMessage
    """

    ap: app.Application

    metadata: cfg_mgr.ConfigManager = None

    member_openid_mapping: OpenIDMapping[str, int] = None
    group_openid_mapping: OpenIDMapping[str, int] = None

    group_msg_seq = None

    def __init__(self, cfg: dict, ap: app.Application):
        """初始化适配器"""
        self.cfg = cfg
        self.ap = ap

        self.group_msg_seq = 1

        switchs = {}

        for intent in cfg["intents"]:
            switchs[intent] = True

        del cfg["intents"]

        intents = botpy.Intents(**switchs)

        self.bot = botpy.Client(intents=intents)

    async def send_message(
        self, target_type: str, target_id: str, message: mirai.MessageChain
    ):
        message_list = self.message_converter.yiri2target(message)

        for msg in message_list:
            args = {}

            if msg["type"] == "text":
                args["content"] = msg["content"]
            elif msg["type"] == "image":
                args["image"] = msg["content"]
            elif msg["type"] == "file_image":
                args["file_image"] = msg["content"]
            else:
                continue

            if target_type == "group":
                args["channel_id"] = str(target_id)

                await self.bot.api.post_message(**args)
            elif target_type == "person":
                args["guild_id"] = str(target_id)

                await self.bot.api.post_dms(**args)

    async def reply_message(
        self,
        message_source: mirai.MessageEvent,
        message: mirai.MessageChain,
        quote_origin: bool = False,
    ):
        
        message_list = self.message_converter.yiri2target(message)

        for msg in message_list:
            args = {}

            if msg["type"] == "text":
                args["content"] = msg["content"]
            elif msg["type"] == "image":
                args["image"] = msg["content"]
            elif msg["type"] == "file_image":
                args["file_image"] = msg["content"]
            else:
                continue

            if quote_origin:
                args["message_reference"] = botpy_message_type.Reference(
                    message_id=cached_message_ids[
                        str(message_source.message_chain.message_id)
                    ]
                )

            if type(message_source) == mirai.GroupMessage:
                args["channel_id"] = str(message_source.sender.group.id)
                args["msg_id"] = cached_message_ids[
                    str(message_source.message_chain.message_id)
                ]
                await self.bot.api.post_message(**args)
            elif type(message_source) == mirai.FriendMessage:
                args["guild_id"] = str(message_source.sender.id)
                args["msg_id"] = cached_message_ids[
                    str(message_source.message_chain.message_id)
                ]
                await self.bot.api.post_dms(**args)
            elif type(message_source) == OfficialGroupMessage:
                if "image" in args or "file_image" in args:
                    continue
                args["group_openid"] = self.group_openid_mapping.getkey(
                    message_source.sender.group.id
                )

                args["msg_id"] = cached_message_ids[
                    str(message_source.message_chain.message_id)
                ]
                args["msg_seq"] = self.group_msg_seq
                self.group_msg_seq += 1
                await self.bot.api.post_group_message(**args)

    async def is_muted(self, group_id: int) -> bool:
        return False

    def register_listener(
        self,
        event_type: typing.Type[mirai.Event],
        callback: typing.Callable[
            [mirai.Event, adapter_model.MessageSourceAdapter], None
        ],
    ):

        try:

            async def wrapper(
                message: typing.Union[
                    botpy_message.Message,
                    botpy_message.DirectMessage,
                    botpy_message.GroupMessage,
                ]
            ):
                self.cached_official_messages[str(message.id)] = message
                await callback(self.event_converter.target2yiri(message), self)

            for event_handler in event_handler_mapping[event_type]:
                setattr(self.bot, event_handler, wrapper)
        except Exception as e:
            traceback.print_exc()
            raise e

    def unregister_listener(
        self,
        event_type: typing.Type[mirai.Event],
        callback: typing.Callable[
            [mirai.Event, adapter_model.MessageSourceAdapter], None
        ],
    ):
        delattr(self.bot, event_handler_mapping[event_type])

    async def run_async(self):

        self.metadata = self.ap.adapter_qq_botpy_meta

        self.member_openid_mapping = OpenIDMapping(
            map=self.metadata.data["mapping"]["members"],
            dump_func=self.metadata.dump_config_sync,
        )

        self.group_openid_mapping = OpenIDMapping(
            map=self.metadata.data["mapping"]["groups"],
            dump_func=self.metadata.dump_config_sync,
        )

        self.message_converter = OfficialMessageConverter()
        self.event_converter = OfficialEventConverter(
            self.member_openid_mapping, self.group_openid_mapping
        )

        self.ap.logger.info("运行 QQ 官方适配器")
        await self.bot.start(**self.cfg)

    def kill(self) -> bool:
        return False
