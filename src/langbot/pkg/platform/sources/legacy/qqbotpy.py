from __future__ import annotations

import logging
import typing
import datetime
import re
import traceback

import botpy
import botpy.message as botpy_message
import botpy.types.message as botpy_message_type

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from ....pipeline.longtext.strategies import forward
from ....core import app
from ....config import manager as cfg_mgr
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
from ...logger import EventLogger


class OfficialGroupMessage(platform_events.GroupMessage):
    pass


class OfficialFriendMessage(platform_events.FriendMessage):
    pass


event_handler_mapping = {
    platform_events.GroupMessage: [
        'on_at_message_create',
        'on_group_at_message_create',
    ],
    platform_events.FriendMessage: [
        'on_direct_message_create',
        'on_c2c_message_create',
    ],
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


K = typing.TypeVar('K')
V = typing.TypeVar('V')


class OpenIDMapping(typing.Generic[K, V]):
    map: dict[K, V]

    dump_func: typing.Callable

    digest_func: typing.Callable[[K], V]

    def __init__(
        self,
        map: dict[K, V],
        dump_func: typing.Callable,
        digest_func: typing.Callable[[K], V] = digest,
    ):
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


class OfficialMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    """QQ 官方消息转换器"""

    @staticmethod
    def yiri2target(message_chain: platform_message.MessageChain):
        """将 YiriMirai 的消息链转换为 QQ 官方消息"""

        msg_list = []
        if type(message_chain) is platform_message.MessageChain:
            msg_list = message_chain.__root__
        elif type(message_chain) is list:
            msg_list = message_chain
        elif type(message_chain) is str:
            msg_list = [platform_message.Plain(text=message_chain)]
        else:
            raise Exception('Unknown message type: ' + str(message_chain) + str(type(message_chain)))

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
            if type(component) is platform_message.Plain:
                offcial_messages.append({'type': 'text', 'content': component.text})
            elif type(component) is platform_message.Image:
                if component.url is not None:
                    offcial_messages.append({'type': 'image', 'content': component.url})
                elif component.path is not None:
                    offcial_messages.append({'type': 'file_image', 'content': component.path})
            elif type(component) is platform_message.At:
                offcial_messages.append({'type': 'at', 'content': ''})
            elif type(component) is platform_message.AtAll:
                print('上层组件要求发送 AtAll 消息，但 QQ 官方 API 不支持此消息类型，忽略此消息。')
            elif type(component) is platform_message.Voice:
                print('上层组件要求发送 Voice 消息，但 QQ 官方 API 不支持此消息类型，忽略此消息。')
            elif type(component) is forward.Forward:
                # 转发消息
                yiri_forward_node_list = component.node_list

                # 遍历并转换
                for yiri_forward_node in yiri_forward_node_list:
                    try:
                        message_chain = yiri_forward_node.message_chain

                        # 平铺
                        offcial_messages.extend(OfficialMessageConverter.yiri2target(message_chain))
                    except Exception:
                        import traceback

                        traceback.print_exc()

        return offcial_messages

    @staticmethod
    def extract_message_chain_from_obj(
        message: typing.Union[
            botpy_message.Message,
            botpy_message.DirectMessage,
            botpy_message.GroupMessage,
            botpy_message.C2CMessage,
        ],
        message_id: str = None,
        bot_account_id: int = 0,
    ) -> platform_message.MessageChain:
        yiri_msg_list = []
        # 存id

        yiri_msg_list.append(platform_message.Source(id=save_msg_id(message_id), time=datetime.datetime.now()))

        if type(message) not in [botpy_message.DirectMessage, botpy_message.C2CMessage]:
            yiri_msg_list.append(platform_message.At(target=bot_account_id))

        if hasattr(message, 'mentions'):
            for mention in message.mentions:
                if mention.bot:
                    continue

                yiri_msg_list.append(platform_message.At(target=mention.id))

        for attachment in message.attachments:
            if attachment.content_type.startswith('image'):
                yiri_msg_list.append(platform_message.Image(url=attachment.url))
            else:
                logging.warning('不支持的附件类型：' + attachment.content_type + '，忽略此附件。')

        content = re.sub(r'<@!\d+>', '', str(message.content))
        if content.strip() != '':
            yiri_msg_list.append(platform_message.Plain(text=content))

        chain = platform_message.MessageChain(yiri_msg_list)

        return chain


class OfficialEventConverter(abstract_platform_adapter.AbstractEventConverter):
    """事件转换器"""

    def __init__(self):
        pass

    def yiri2target(self, event: typing.Type[platform_events.Event]):
        if event == platform_events.GroupMessage:
            return botpy_message.Message
        elif event == platform_events.FriendMessage:
            return botpy_message.DirectMessage
        else:
            raise Exception('未支持转换的事件类型(YiriMirai -> Official): ' + str(event))

    def target2yiri(
        self,
        event: typing.Union[
            botpy_message.Message,
            botpy_message.DirectMessage,
            botpy_message.GroupMessage,
            botpy_message.C2CMessage,
        ],
    ) -> platform_events.Event:
        if isinstance(event, botpy_message.Message):  # 频道内，转群聊事件
            permission = 'MEMBER'

            if '2' in event.member.roles:
                permission = 'ADMINISTRATOR'
            elif '4' in event.member.roles:
                permission = 'OWNER'

            return platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=event.author.id,
                    member_name=event.author.username,
                    permission=permission,
                    group=platform_entities.Group(
                        id=event.channel_id,
                        name=event.author.username,
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                    join_timestamp=int(
                        datetime.datetime.strptime(event.member.joined_at, '%Y-%m-%dT%H:%M:%S%z').timestamp()
                    ),
                    last_speak_timestamp=datetime.datetime.now().timestamp(),
                    mute_time_remaining=0,
                ),
                message_chain=OfficialMessageConverter.extract_message_chain_from_obj(event, event.id),
                time=int(datetime.datetime.strptime(event.timestamp, '%Y-%m-%dT%H:%M:%S%z').timestamp()),
            )
        elif isinstance(event, botpy_message.DirectMessage):  # 频道私聊，转私聊事件
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event.guild_id,
                    nickname=event.author.username,
                    remark=event.author.username,
                ),
                message_chain=OfficialMessageConverter.extract_message_chain_from_obj(event, event.id),
                time=int(datetime.datetime.strptime(event.timestamp, '%Y-%m-%dT%H:%M:%S%z').timestamp()),
            )
        elif isinstance(event, botpy_message.GroupMessage):  # 群聊，转群聊事件
            author_member_id = event.author.member_openid

            return OfficialGroupMessage(
                sender=platform_entities.GroupMember(
                    id=author_member_id,
                    member_name=author_member_id,
                    permission='MEMBER',
                    group=platform_entities.Group(
                        id=event.group_openid,
                        name=author_member_id,
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                    join_timestamp=int(0),
                    last_speak_timestamp=datetime.datetime.now().timestamp(),
                    mute_time_remaining=0,
                ),
                message_chain=OfficialMessageConverter.extract_message_chain_from_obj(event, event.id),
                time=int(datetime.datetime.strptime(event.timestamp, '%Y-%m-%dT%H:%M:%S%z').timestamp()),
            )
        elif isinstance(event, botpy_message.C2CMessage):  # 私聊，转私聊事件
            user_id_alter = event.author.user_openid

            return OfficialFriendMessage(
                sender=platform_entities.Friend(
                    id=user_id_alter,
                    nickname=user_id_alter,
                    remark=user_id_alter,
                ),
                message_chain=OfficialMessageConverter.extract_message_chain_from_obj(event, event.id),
                time=int(datetime.datetime.strptime(event.timestamp, '%Y-%m-%dT%H:%M:%S%z').timestamp()),
            )


class OfficialAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
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

    group_msg_seq = None
    c2c_msg_seq = None

    def __init__(self, cfg: dict, ap: app.Application, logger: EventLogger):
        """初始化适配器"""
        self.cfg = cfg
        self.ap = ap
        self.logger = logger

        self.group_msg_seq = 1
        self.c2c_msg_seq = 1

        switchs = {}

        for intent in cfg['intents']:
            switchs[intent] = True

        del cfg['intents']

        intents = botpy.Intents(**switchs)

        self.bot = botpy.Client(intents=intents)

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        message_list = self.message_converter.yiri2target(message)

        for msg in message_list:
            args = {}

            if msg['type'] == 'text':
                args['content'] = msg['content']
            elif msg['type'] == 'image':
                args['image'] = msg['content']
            elif msg['type'] == 'file_image':
                args['file_image'] = msg['content']
            else:
                continue

            if target_type == 'group':
                args['channel_id'] = str(target_id)

                await self.bot.api.post_message(**args)
            elif target_type == 'person':
                args['guild_id'] = str(target_id)

                await self.bot.api.post_dms(**args)

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        message_list = self.message_converter.yiri2target(message)

        for msg in message_list:
            args = {}

            if msg['type'] == 'text':
                args['content'] = msg['content']
            elif msg['type'] == 'image':
                args['image'] = msg['content']
            elif msg['type'] == 'file_image':
                args['file_image'] = msg['content']
            else:
                continue

            if quote_origin:
                args['message_reference'] = botpy_message_type.Reference(
                    message_id=cached_message_ids[str(message_source.message_chain.message_id)]
                )

            if isinstance(message_source, platform_events.GroupMessage):
                args['channel_id'] = str(message_source.sender.group.id)
                args['msg_id'] = cached_message_ids[str(message_source.message_chain.message_id)]
                await self.bot.api.post_message(**args)
            elif isinstance(message_source, platform_events.FriendMessage):
                args['guild_id'] = str(message_source.sender.id)
                args['msg_id'] = cached_message_ids[str(message_source.message_chain.message_id)]
                await self.bot.api.post_dms(**args)
            elif isinstance(message_source, OfficialGroupMessage):
                if 'file_image' in args:  # 暂不支持发送文件图片
                    continue

                args['group_openid'] = message_source.sender.group.id

                if 'image' in args:
                    uploadMedia = await self.bot.api.post_group_file(
                        group_openid=args['group_openid'],
                        file_type=1,
                        url=str(args['image']),
                    )

                    del args['image']
                    args['media'] = uploadMedia
                    args['msg_type'] = 7

                args['msg_id'] = cached_message_ids[str(message_source.message_chain.message_id)]
                args['msg_seq'] = self.group_msg_seq
                self.group_msg_seq += 1

                await self.bot.api.post_group_message(**args)
            elif isinstance(message_source, OfficialFriendMessage):
                if 'file_image' in args:
                    continue
                args['openid'] = message_source.sender.id

                if 'image' in args:
                    uploadMedia = await self.bot.api.post_c2c_file(
                        openid=args['openid'], file_type=1, url=str(args['image'])
                    )

                    del args['image']
                    args['media'] = uploadMedia
                    args['msg_type'] = 7

                args['msg_id'] = cached_message_ids[str(message_source.message_chain.message_id)]

                args['msg_seq'] = self.c2c_msg_seq
                self.c2c_msg_seq += 1

                await self.bot.api.post_c2c_message(**args)

    async def is_muted(self, group_id: int) -> bool:
        return False

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        try:

            async def wrapper(
                message: typing.Union[
                    botpy_message.Message,
                    botpy_message.DirectMessage,
                    botpy_message.GroupMessage,
                ],
            ):
                self.cached_official_messages[str(message.id)] = message
                await callback(self.event_converter.target2yiri(message), self)

            for event_handler in event_handler_mapping[event_type]:
                setattr(self.bot, event_handler, wrapper)
        except Exception as e:
            self.logger.error(f'Error in qqbotpy callback: {traceback.format_exc()}')
            raise e

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        delattr(self.bot, event_handler_mapping[event_type])

    async def run_async(self):
        self.metadata = self.ap.adapter_qq_botpy_meta

        self.message_converter = OfficialMessageConverter()
        self.event_converter = OfficialEventConverter()

        self.cfg['ret_coro'] = True

        await self.logger.info('运行 QQ 官方适配器')
        await (await self.bot.start(**self.cfg))

    async def kill(self) -> bool:
        if not self.bot.is_closed():
            await self.bot.close()
            return True
