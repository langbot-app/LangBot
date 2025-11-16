from __future__ import annotations
import typing
import asyncio
import traceback
import datetime

import aiocqhttp
import pydantic

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
from ...utils import image
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger


class AiocqhttpMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(
        message_chain: platform_message.MessageChain,
    ) -> typing.Tuple[list, int, datetime.datetime]:
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
                    msg_list.append(aiocqhttp.MessageSegment.image(f'base64://{arg}'))
                elif msg.url:
                    arg = msg.url
                    msg_list.append(aiocqhttp.MessageSegment.image(arg))
                elif msg.path:
                    arg = msg.path
                    msg_list.append(aiocqhttp.MessageSegment.image(arg))
            elif type(msg) is platform_message.At:
                msg_list.append(aiocqhttp.MessageSegment.at(msg.target))
            elif type(msg) is platform_message.AtAll:
                msg_list.append(aiocqhttp.MessageSegment.at('all'))
            elif type(msg) is platform_message.Voice:
                arg = ''
                if msg.base64:
                    arg = msg.base64
                    msg_list.append(aiocqhttp.MessageSegment.record(f'base64://{arg}'))
                elif msg.url:
                    arg = msg.url
                    msg_list.append(aiocqhttp.MessageSegment.record(arg))
                elif msg.path:
                    arg = msg.path
                    msg_list.append(aiocqhttp.MessageSegment.record(msg.path))
            elif type(msg) is platform_message.Forward:
                for node in msg.node_list:
                    msg_list.extend((await AiocqhttpMessageConverter.yiri2target(node.message_chain))[0])
            elif isinstance(msg, platform_message.File):
                msg_list.append({'type': 'file', 'data': {'file': msg.url, 'name': msg.name}})
            elif isinstance(msg, platform_message.Face):
                if msg.face_type == 'face':
                    msg_list.append(aiocqhttp.MessageSegment.face(msg.face_id))
                elif msg.face_type == 'rps':
                    msg_list.append(aiocqhttp.MessageSegment.rps())
                elif msg.face_type == 'dice':
                    msg_list.append(aiocqhttp.MessageSegment.dice())

            else:
                msg_list.append(aiocqhttp.MessageSegment.text(str(msg)))

        return msg_list, msg_id, msg_time

    @staticmethod
    async def target2yiri(message: str, message_id: int = -1, bot: aiocqhttp.CQHttp = None):
        message = aiocqhttp.Message(message)

        def get_face_name(face_id):
            face_code_dict = {
                '2': '好色',
                '4': '得意',
                '5': '流泪',
                '8': '睡',
                '9': '大哭',
                '10': '尴尬',
                '12': '调皮',
                '14': '微笑',
                '16': '酷',
                '21': '可爱',
                '23': '傲慢',
                '24': '饥饿',
                '25': '困',
                '26': '惊恐',
                '27': '流汗',
                '28': '憨笑',
                '29': '悠闲',
                '30': '奋斗',
                '32': '疑问',
                '33': '嘘',
                '34': '晕',
                '38': '敲打',
                '39': '再见',
                '41': '发抖',
                '42': '爱情',
                '43': '跳跳',
                '49': '拥抱',
                '53': '蛋糕',
                '60': '咖啡',
                '63': '玫瑰',
                '66': '爱心',
                '74': '太阳',
                '75': '月亮',
                '76': '赞',
                '78': '握手',
                '79': '胜利',
                '85': '飞吻',
                '89': '西瓜',
                '96': '冷汗',
                '97': '擦汗',
                '98': '抠鼻',
                '99': '鼓掌',
                '100': '糗大了',
                '101': '坏笑',
                '102': '左哼哼',
                '103': '右哼哼',
                '104': '哈欠',
                '106': '委屈',
                '109': '左亲亲',
                '111': '可怜',
                '116': '示爱',
                '118': '抱拳',
                '120': '拳头',
                '122': '爱你',
                '123': 'NO',
                '124': 'OK',
                '125': '转圈',
                '129': '挥手',
                '144': '喝彩',
                '147': '棒棒糖',
                '171': '茶',
                '173': '泪奔',
                '174': '无奈',
                '175': '卖萌',
                '176': '小纠结',
                '179': 'doge',
                '180': '惊喜',
                '181': '骚扰',
                '182': '笑哭',
                '183': '我最美',
                '201': '点赞',
                '203': '托脸',
                '212': '托腮',
                '214': '啵啵',
                '219': '蹭一蹭',
                '222': '抱抱',
                '227': '拍手',
                '232': '佛系',
                '240': '喷脸',
                '243': '甩头',
                '246': '加油抱抱',
                '262': '脑阔疼',
                '264': '捂脸',
                '265': '辣眼睛',
                '266': '哦哟',
                '267': '头秃',
                '268': '问号脸',
                '269': '暗中观察',
                '270': 'emm',
                '271': '吃瓜',
                '272': '呵呵哒',
                '273': '我酸了',
                '277': '汪汪',
                '278': '汗',
                '281': '无眼笑',
                '282': '敬礼',
                '284': '面无表情',
                '285': '摸鱼',
                '287': '哦',
                '289': '睁眼',
                '290': '敲开心',
                '293': '摸锦鲤',
                '294': '期待',
                '297': '拜谢',
                '298': '元宝',
                '299': '牛啊',
                '305': '右亲亲',
                '306': '牛气冲天',
                '307': '喵喵',
                '314': '仔细分析',
                '315': '加油',
                '318': '崇拜',
                '319': '比心',
                '320': '庆祝',
                '322': '拒绝',
                '324': '吃糖',
                '326': '生气',
            }
            return face_code_dict.get(face_id, '')

        async def process_message_data(msg_data, reply_list):
            if msg_data['type'] == 'image':
                image_base64, image_format = await image.qq_image_url_to_base64(msg_data['data']['url'])
                reply_list.append(platform_message.Image(base64=f'data:image/{image_format};base64,{image_base64}'))

            elif msg_data['type'] == 'text':
                reply_list.append(platform_message.Plain(text=msg_data['data']['text']))

            elif msg_data['type'] == 'forward':  # 这里来应该传入转发消息组，暂时传入qoute
                for forward_msg_datas in msg_data['data']['content']:
                    for forward_msg_data in forward_msg_datas['message']:
                        await process_message_data(forward_msg_data, reply_list)

            elif msg_data['type'] == 'at':
                if msg_data['data']['qq'] == 'all':
                    reply_list.append(platform_message.AtAll())
                else:
                    reply_list.append(
                        platform_message.At(
                            target=msg_data['data']['qq'],
                        )
                    )

        yiri_msg_list = []

        yiri_msg_list.append(platform_message.Source(id=message_id, time=datetime.datetime.now()))

        for msg in message:
            reply_list = []
            if msg.type == 'at':
                if msg.data['qq'] == 'all':
                    yiri_msg_list.append(platform_message.AtAll())
                else:
                    yiri_msg_list.append(
                        platform_message.At(
                            target=msg.data['qq'],
                        )
                    )
            elif msg.type == 'text':
                yiri_msg_list.append(platform_message.Plain(text=msg.data['text']))
            elif msg.type == 'image':
                emoji_id = msg.data.get('emoji_package_id', None)
                if emoji_id:
                    face_id = emoji_id
                    face_name = msg.data.get('summary', '')
                    image_msg = platform_message.Face(face_id=face_id, face_name=face_name)
                else:
                    image_base64, image_format = await image.qq_image_url_to_base64(msg.data['url'])
                    image_msg = platform_message.Image(base64=f'data:image/{image_format};base64,{image_base64}')
                yiri_msg_list.append(image_msg)
            elif msg.type == 'forward':
                # 暂时不太合理
                # msg_datas = await bot.get_msg(message_id=message_id)
                # print(msg_datas)
                # for msg_data in msg_datas["message"]:
                #     await process_message_data(msg_data, yiri_msg_list)
                pass

            elif msg.type == 'reply':  # 此处处理引用消息传入Qoute
                msg_datas = await bot.get_msg(message_id=msg.data['id'])

                for msg_data in msg_datas['message']:
                    await process_message_data(msg_data, reply_list)

                reply_msg = platform_message.Quote(
                    message_id=msg.data['id'], sender_id=msg_datas['user_id'], origin=reply_list
                )
                yiri_msg_list.append(reply_msg)

            elif msg.type == 'file':
                pass
                # file_name = msg.data['file']
                # file_id = msg.data['file_id']
                # file_data = await bot.get_file(file_id=file_id)
                # file_name = file_data.get('file_name')
                # file_path = file_data.get('file')
                # _ = file_path
                # file_url = file_data.get('file_url')
                # file_size = file_data.get('file_size')
                # yiri_msg_list.append(platform_message.File(id=file_id, name=file_name,url=file_url,size=file_size))
            elif msg.type == 'face':
                face_id = msg.data['id']
                face_name = msg.data['raw']['faceText']
                if not face_name:
                    face_name = get_face_name(face_id)
                yiri_msg_list.append(platform_message.Face(face_id=int(face_id), face_name=face_name.replace('/', '')))
            elif msg.type == 'rps':
                face_id = msg.data['result']
                yiri_msg_list.append(platform_message.Face(face_type='rps', face_id=int(face_id), face_name='猜拳'))
            elif msg.type == 'dice':
                face_id = msg.data['result']
                yiri_msg_list.append(platform_message.Face(face_type='dice', face_id=int(face_id), face_name='骰子'))

        chain = platform_message.MessageChain(yiri_msg_list)

        return chain


class AiocqhttpEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent, bot_account_id: int):
        return event.source_platform_object

    @staticmethod
    async def target2yiri(event: aiocqhttp.Event, bot=None):
        yiri_chain = await AiocqhttpMessageConverter.target2yiri(event.message, event.message_id, bot)

        if event.message_type == 'group':
            permission = 'MEMBER'

            if 'role' in event.sender:
                if event.sender['role'] == 'admin':
                    permission = 'ADMINISTRATOR'
                elif event.sender['role'] == 'owner':
                    permission = 'OWNER'
            converted_event = platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=event.sender['user_id'],  # message_seq 放哪？
                    member_name=event.sender['nickname'],
                    permission=permission,
                    group=platform_entities.Group(
                        id=event.group_id,
                        name=event.sender['nickname'],
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title=event.sender['title'] if 'title' in event.sender else '',
                    join_timestamp=0,
                    last_speak_timestamp=0,
                    mute_time_remaining=0,
                ),
                message_chain=yiri_chain,
                time=event.time,
                source_platform_object=event,
            )
            return converted_event
        elif event.message_type == 'private':
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event.sender['user_id'],
                    nickname=event.sender['nickname'],
                    remark='',
                ),
                message_chain=yiri_chain,
                time=event.time,
                source_platform_object=event,
            )


class AiocqhttpAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    bot: aiocqhttp.CQHttp = pydantic.Field(exclude=True, default_factory=aiocqhttp.CQHttp)

    message_converter: AiocqhttpMessageConverter = AiocqhttpMessageConverter()
    event_converter: AiocqhttpEventConverter = AiocqhttpEventConverter()

    on_websocket_connection_event_cache: typing.List[typing.Callable[[aiocqhttp.Event], None]] = []

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        super().__init__(
            config=config,
            logger=logger,
        )

        async def shutdown_trigger_placeholder():
            while True:
                await asyncio.sleep(1)

        self.config['shutdown_trigger'] = shutdown_trigger_placeholder

        self.on_websocket_connection_event_cache = []

        if 'access-token' in config:
            self.bot = aiocqhttp.CQHttp(access_token=config['access-token'])
            del self.config['access-token']
        else:
            self.bot = aiocqhttp.CQHttp()

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        aiocq_msg = (await AiocqhttpMessageConverter.yiri2target(message))[0]

        if target_type == 'group':
            await self.bot.send_group_msg(group_id=int(target_id), message=aiocq_msg)
        elif target_type == 'person':
            await self.bot.send_private_msg(user_id=int(target_id), message=aiocq_msg)

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        aiocq_event = await AiocqhttpEventConverter.yiri2target(message_source, self.bot_account_id)
        aiocq_msg = (await AiocqhttpMessageConverter.yiri2target(message))[0]
        if quote_origin:
            aiocq_msg = aiocqhttp.MessageSegment.reply(aiocq_event.message_id) + aiocq_msg

        return await self.bot.send(aiocq_event, aiocq_msg)

    async def is_muted(self, group_id: int) -> bool:
        return False

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        async def on_message(event: aiocqhttp.Event):
            self.bot_account_id = event.self_id
            try:
                return await callback(await self.event_converter.target2yiri(event, self.bot), self)
            except Exception:
                await self.logger.error(f'Error in on_message: {traceback.format_exc()}')
                traceback.print_exc()

        if event_type == platform_events.GroupMessage:
            self.bot.on_message('group')(on_message)
            # self.bot.on_notice()(on_message)
        elif event_type == platform_events.FriendMessage:
            self.bot.on_message('private')(on_message)
            # self.bot.on_notice()(on_message)
        # print(event_type)

        async def on_websocket_connection(event: aiocqhttp.Event):
            for event in self.on_websocket_connection_event_cache:
                if event.self_id == event.self_id and event.time == event.time:
                    return

            self.on_websocket_connection_event_cache.append(event)
            await self.logger.info(f'WebSocket connection established, bot id: {event.self_id}')

        self.bot.on_websocket_connection(on_websocket_connection)

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        return super().unregister_listener(event_type, callback)

    async def run_async(self):
        await self.bot._server_app.run_task(**self.config)

    async def kill(self) -> bool:
        # Current issue: existing connection will not be closed
        # self.should_shutdown = True
        return False
