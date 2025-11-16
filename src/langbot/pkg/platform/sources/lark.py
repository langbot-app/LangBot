from __future__ import annotations

import lark_oapi
from lark_oapi.api.im.v1 import CreateImageRequest, CreateImageRequestBody
import traceback
import typing
import asyncio
import re
import base64
import uuid
import json
import datetime
import hashlib
from Crypto.Cipher import AES

import aiohttp
import lark_oapi.ws.exception
import quart
from lark_oapi.api.im.v1 import *
import pydantic
from lark_oapi.api.cardkit.v1 import *

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger


class AESCipher(object):
    def __init__(self, key):
        self.bs = AES.block_size
        self.key = hashlib.sha256(AESCipher.str_to_bytes(key)).digest()

    @staticmethod
    def str_to_bytes(data):
        u_type = type(b''.decode('utf8'))
        if isinstance(data, u_type):
            return data.encode('utf8')
        return data

    @staticmethod
    def _unpad(s):
        return s[: -ord(s[len(s) - 1 :])]

    def decrypt(self, enc):
        iv = enc[: AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return self._unpad(cipher.decrypt(enc[AES.block_size :]))

    def decrypt_string(self, enc):
        enc = base64.b64decode(enc)
        return self.decrypt(enc).decode('utf8')


class LarkMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(
        message_chain: platform_message.MessageChain, api_client: lark_oapi.Client
    ) -> typing.Tuple[list]:
        message_elements = []
        pending_paragraph = []
        for msg in message_chain:
            if isinstance(msg, platform_message.Plain):
                # Ensure text is valid UTF-8
                try:
                    text = msg.text.encode('utf-8').decode('utf-8')
                    pending_paragraph.append({'tag': 'md', 'text': text})
                except UnicodeError:
                    # If text is not valid UTF-8, try to decode with other encodings
                    try:
                        text = msg.text.encode('latin1').decode('utf-8')
                        pending_paragraph.append({'tag': 'md', 'text': text})
                    except UnicodeError:
                        # If still fails, replace invalid characters
                        text = msg.text.encode('utf-8', errors='replace').decode('utf-8')
                        pending_paragraph.append({'tag': 'md', 'text': text})
            elif isinstance(msg, platform_message.At):
                pending_paragraph.append({'tag': 'at', 'user_id': msg.target, 'style': []})
            elif isinstance(msg, platform_message.AtAll):
                pending_paragraph.append({'tag': 'at', 'user_id': 'all', 'style': []})
            elif isinstance(msg, platform_message.Image):
                image_bytes = None

                if msg.base64:
                    try:
                        # Remove data URL prefix if present
                        if msg.base64.startswith('data:'):
                            msg.base64 = msg.base64.split(',', 1)[1]
                        image_bytes = base64.b64decode(msg.base64)
                    except Exception:
                        traceback.print_exc()
                        continue
                elif msg.url:
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(msg.url) as response:
                                if response.status == 200:
                                    image_bytes = await response.read()
                                else:
                                    traceback.print_exc()
                                    continue
                    except Exception:
                        traceback.print_exc()
                        continue
                elif msg.path:
                    try:
                        with open(msg.path, 'rb') as f:
                            image_bytes = f.read()
                    except Exception:
                        traceback.print_exc()
                        continue

                if image_bytes is None:
                    continue

                try:
                    # Create a temporary file to store the image bytes
                    import tempfile

                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        temp_file.write(image_bytes)
                        temp_file.flush()

                        # Create image request using the temporary file
                        request = (
                            CreateImageRequest.builder()
                            .request_body(
                                CreateImageRequestBody.builder()
                                .image_type('message')
                                .image(open(temp_file.name, 'rb'))
                                .build()
                            )
                            .build()
                        )

                        response = await api_client.im.v1.image.acreate(request)

                        if not response.success():
                            raise Exception(
                                f'client.im.v1.image.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
                            )

                        image_key = response.data.image_key

                        message_elements.append(pending_paragraph)
                        message_elements.append(
                            [
                                {
                                    'tag': 'img',
                                    'image_key': image_key,
                                }
                            ]
                        )
                        pending_paragraph = []
                except Exception:
                    traceback.print_exc()
                    continue
                finally:
                    # Clean up the temporary file
                    import os

                    if 'temp_file' in locals():
                        os.unlink(temp_file.name)
            elif isinstance(msg, platform_message.Forward):
                for node in msg.node_list:
                    message_elements.extend(await LarkMessageConverter.yiri2target(node.message_chain, api_client))

        if pending_paragraph:
            message_elements.append(pending_paragraph)

        return message_elements

    @staticmethod
    async def target2yiri(
        message: lark_oapi.api.im.v1.model.event_message.EventMessage,
        api_client: lark_oapi.Client,
    ) -> platform_message.MessageChain:
        message_content = json.loads(message.content)

        lb_msg_list = []

        msg_create_time = datetime.datetime.fromtimestamp(int(message.create_time) / 1000)

        lb_msg_list.append(platform_message.Source(id=message.message_id, time=msg_create_time))

        if message.message_type == 'text':
            element_list = []

            def text_element_recur(text_ele: dict) -> list[dict]:
                if text_ele['text'] == '':
                    return []

                at_pattern = re.compile(r'@_user_[\d]+')
                at_matches = at_pattern.findall(text_ele['text'])

                name_mapping = {}
                for mathc in at_matches:
                    for mention in message.mentions:
                        if mention.key == mathc:
                            name_mapping[mathc] = mention.name
                            break

                if len(name_mapping.keys()) == 0:
                    return [text_ele]

                # 只处理第一个，剩下的递归处理
                text_split = text_ele['text'].split(list(name_mapping.keys())[0])

                new_list = []

                left_text = text_split[0]
                right_text = text_split[1]

                new_list.extend(text_element_recur({'tag': 'text', 'text': left_text, 'style': []}))

                new_list.append(
                    {
                        'tag': 'at',
                        'user_id': list(name_mapping.keys())[0],
                        'user_name': name_mapping[list(name_mapping.keys())[0]],
                        'style': [],
                    }
                )

                new_list.extend(text_element_recur({'tag': 'text', 'text': right_text, 'style': []}))

                return new_list

            element_list = text_element_recur({'tag': 'text', 'text': message_content['text'], 'style': []})

            message_content = {'title': '', 'content': element_list}

        elif message.message_type == 'post':
            new_list = []

            for ele in message_content['content']:
                if type(ele) is dict:
                    new_list.append(ele)
                elif type(ele) is list:
                    new_list.extend(ele)

            message_content['content'] = new_list
        elif message.message_type == 'image':
            message_content['content'] = [{'tag': 'img', 'image_key': message_content['image_key'], 'style': []}]

        for ele in message_content['content']:
            if ele['tag'] == 'text':
                lb_msg_list.append(platform_message.Plain(text=ele['text']))
            elif ele['tag'] == 'at':
                lb_msg_list.append(platform_message.At(target=ele['user_name']))
            elif ele['tag'] == 'img':
                image_key = ele['image_key']

                request: GetMessageResourceRequest = (
                    GetMessageResourceRequest.builder()
                    .message_id(message.message_id)
                    .file_key(image_key)
                    .type('image')
                    .build()
                )

                response: GetMessageResourceResponse = await api_client.im.v1.message_resource.aget(request)

                if not response.success():
                    raise Exception(
                        f'client.im.v1.message_resource.get failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
                    )

                image_bytes = response.file.read()
                image_base64 = base64.b64encode(image_bytes).decode()

                image_format = response.raw.headers['content-type']

                lb_msg_list.append(platform_message.Image(base64=f'data:{image_format};base64,{image_base64}'))

        return platform_message.MessageChain(lb_msg_list)


class LarkEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(
        event: platform_events.MessageEvent,
    ) -> lark_oapi.im.v1.P2ImMessageReceiveV1:
        pass

    @staticmethod
    async def target2yiri(
        event: lark_oapi.im.v1.P2ImMessageReceiveV1, api_client: lark_oapi.Client
    ) -> platform_events.Event:
        message_chain = await LarkMessageConverter.target2yiri(event.event.message, api_client)

        if event.event.message.chat_type == 'p2p':
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event.event.sender.sender_id.open_id,
                    nickname=event.event.sender.sender_id.union_id,
                    remark='',
                ),
                message_chain=message_chain,
                time=event.event.message.create_time,
            )
        elif event.event.message.chat_type == 'group':
            return platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=event.event.sender.sender_id.open_id,
                    member_name=event.event.sender.sender_id.union_id,
                    permission=platform_entities.Permission.Member,
                    group=platform_entities.Group(
                        id=event.event.message.chat_id,
                        name='',
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                    join_timestamp=0,
                    last_speak_timestamp=0,
                    mute_time_remaining=0,
                ),
                message_chain=message_chain,
                time=event.event.message.create_time,
            )


CARD_ID_CACHE_SIZE = 500
CARD_ID_CACHE_MAX_LIFETIME = 20 * 60  # 20分钟


class LarkAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    bot: lark_oapi.ws.Client = pydantic.Field(exclude=True)
    api_client: lark_oapi.Client = pydantic.Field(exclude=True)

    bot_account_id: str  # 用于在流水线中识别at是否是本bot，直接以bot_name作为标识
    lark_tenant_key: str = pydantic.Field(exclude=True, default='')  # 飞书企业key

    message_converter: LarkMessageConverter = LarkMessageConverter()
    event_converter: LarkEventConverter = LarkEventConverter()

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ]

    quart_app: quart.Quart = pydantic.Field(exclude=True)

    card_id_dict: dict[str, str]  # 消息id到卡片id的映射，便于创建卡片后的发送消息到指定卡片

    seq: int  # 用于在发送卡片消息中识别消息顺序，直接以seq作为标识

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger, **kwargs):
        quart_app = quart.Quart(__name__)

        @quart_app.route('/lark/callback', methods=['POST'])
        async def lark_callback():
            try:
                data = await quart.request.json

                if 'encrypt' in data:
                    cipher = AESCipher(config['encrypt-key'])
                    data = cipher.decrypt_string(data['encrypt'])
                    data = json.loads(data)

                type = data.get('type')
                if type is None:
                    context = EventContext(data)
                    type = context.header.event_type

                if 'url_verification' == type:
                    # todo 验证verification token
                    return {'challenge': data.get('challenge')}
                context = EventContext(data)
                type = context.header.event_type
                p2v1 = P2ImMessageReceiveV1()
                p2v1.header = context.header
                event = P2ImMessageReceiveV1Data()
                event.message = EventMessage(context.event['message'])
                event.sender = EventSender(context.event['sender'])
                p2v1.event = event
                p2v1.schema = context.schema
                if 'im.message.receive_v1' == type:
                    try:
                        event = await self.event_converter.target2yiri(p2v1, self.api_client)
                    except Exception:
                        await self.logger.error(f'Error in lark callback: {traceback.format_exc()}')

                    if event.__class__ in self.listeners:
                        await self.listeners[event.__class__](event, self)

                return {'code': 200, 'message': 'ok'}
            except Exception:
                await self.logger.error(f'Error in lark callback: {traceback.format_exc()}')
                return {'code': 500, 'message': 'error'}

        async def on_message(event: lark_oapi.im.v1.P2ImMessageReceiveV1):
            lb_event = await self.event_converter.target2yiri(event, self.api_client)

            await self.listeners[type(lb_event)](lb_event, self)

        def sync_on_message(event: lark_oapi.im.v1.P2ImMessageReceiveV1):
            asyncio.create_task(on_message(event))

        event_handler = (
            lark_oapi.EventDispatcherHandler.builder('', '').register_p2_im_message_receive_v1(sync_on_message).build()
        )

        bot_account_id = config['bot_name']

        bot = lark_oapi.ws.Client(config['app_id'], config['app_secret'], event_handler=event_handler)
        api_client = lark_oapi.Client.builder().app_id(config['app_id']).app_secret(config['app_secret']).build()

        super().__init__(
            config=config,
            logger=logger,
            lark_tenant_key=config.get('lark_tenant_key', ''),
            card_id_dict={},
            seq=1,
            listeners={},
            quart_app=quart_app,
            bot=bot,
            api_client=api_client,
            bot_account_id=bot_account_id,
            **kwargs,
        )

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        pass

    async def is_stream_output_supported(self) -> bool:
        is_stream = False
        if self.config.get('enable-stream-reply', None):
            is_stream = True
        return is_stream

    async def create_card_id(self, message_id):
        try:
            # self.logger.debug('飞书支持stream输出,创建卡片......')

            card_data = {
                'schema': '2.0',
                'config': {
                    'update_multi': True,
                    'streaming_mode': True,
                    'streaming_config': {
                        'print_step': {'default': 1},
                        'print_frequency_ms': {'default': 70},
                        'print_strategy': 'fast',
                    },
                },
                'body': {
                    'direction': 'vertical',
                    'padding': '12px 12px 12px 12px',
                    'elements': [
                        {
                            'tag': 'div',
                            'text': {
                                'tag': 'plain_text',
                                'content': 'LangBot',
                                'text_size': 'normal',
                                'text_align': 'left',
                                'text_color': 'default',
                            },
                            'icon': {
                                'tag': 'custom_icon',
                                'img_key': 'img_v3_02p3_05c65d5d-9bad-440a-a2fb-c89571bfd5bg',
                            },
                        },
                        {
                            'tag': 'markdown',
                            'content': '',
                            'text_align': 'left',
                            'text_size': 'normal',
                            'margin': '0px 0px 0px 0px',
                            'element_id': 'streaming_txt',
                        },
                        {
                            'tag': 'markdown',
                            'content': '',
                            'text_align': 'left',
                            'text_size': 'normal',
                            'margin': '0px 0px 0px 0px',
                        },
                        {
                            'tag': 'column_set',
                            'horizontal_spacing': '8px',
                            'horizontal_align': 'left',
                            'columns': [
                                {
                                    'tag': 'column',
                                    'width': 'weighted',
                                    'elements': [
                                        {
                                            'tag': 'markdown',
                                            'content': '',
                                            'text_align': 'left',
                                            'text_size': 'normal',
                                            'margin': '0px 0px 0px 0px',
                                        },
                                        {
                                            'tag': 'markdown',
                                            'content': '',
                                            'text_align': 'left',
                                            'text_size': 'normal',
                                            'margin': '0px 0px 0px 0px',
                                        },
                                        {
                                            'tag': 'markdown',
                                            'content': '',
                                            'text_align': 'left',
                                            'text_size': 'normal',
                                            'margin': '0px 0px 0px 0px',
                                        },
                                    ],
                                    'padding': '0px 0px 0px 0px',
                                    'direction': 'vertical',
                                    'horizontal_spacing': '8px',
                                    'vertical_spacing': '2px',
                                    'horizontal_align': 'left',
                                    'vertical_align': 'top',
                                    'margin': '0px 0px 0px 0px',
                                    'weight': 1,
                                }
                            ],
                            'margin': '0px 0px 0px 0px',
                        },
                        {'tag': 'hr', 'margin': '0px 0px 0px 0px'},
                        {
                            'tag': 'column_set',
                            'horizontal_spacing': '12px',
                            'horizontal_align': 'right',
                            'columns': [
                                {
                                    'tag': 'column',
                                    'width': 'weighted',
                                    'elements': [
                                        {
                                            'tag': 'markdown',
                                            'content': '<font color="grey-600">以上内容由 AI 生成，仅供参考。更多详细、准确信息可点击引用链接查看</font>',
                                            'text_align': 'left',
                                            'text_size': 'notation',
                                            'margin': '4px 0px 0px 0px',
                                            'icon': {
                                                'tag': 'standard_icon',
                                                'token': 'robot_outlined',
                                                'color': 'grey',
                                            },
                                        }
                                    ],
                                    'padding': '0px 0px 0px 0px',
                                    'direction': 'vertical',
                                    'horizontal_spacing': '8px',
                                    'vertical_spacing': '8px',
                                    'horizontal_align': 'left',
                                    'vertical_align': 'top',
                                    'margin': '0px 0px 0px 0px',
                                    'weight': 1,
                                },
                                {
                                    'tag': 'column',
                                    'width': '20px',
                                    'elements': [
                                        {
                                            'tag': 'button',
                                            'text': {'tag': 'plain_text', 'content': ''},
                                            'type': 'text',
                                            'width': 'fill',
                                            'size': 'medium',
                                            'icon': {'tag': 'standard_icon', 'token': 'thumbsup_outlined'},
                                            'hover_tips': {'tag': 'plain_text', 'content': '有帮助'},
                                            'margin': '0px 0px 0px 0px',
                                        }
                                    ],
                                    'padding': '0px 0px 0px 0px',
                                    'direction': 'vertical',
                                    'horizontal_spacing': '8px',
                                    'vertical_spacing': '8px',
                                    'horizontal_align': 'left',
                                    'vertical_align': 'top',
                                    'margin': '0px 0px 0px 0px',
                                },
                                {
                                    'tag': 'column',
                                    'width': '30px',
                                    'elements': [
                                        {
                                            'tag': 'button',
                                            'text': {'tag': 'plain_text', 'content': ''},
                                            'type': 'text',
                                            'width': 'default',
                                            'size': 'medium',
                                            'icon': {'tag': 'standard_icon', 'token': 'thumbdown_outlined'},
                                            'hover_tips': {'tag': 'plain_text', 'content': '无帮助'},
                                            'margin': '0px 0px 0px 0px',
                                        }
                                    ],
                                    'padding': '0px 0px 0px 0px',
                                    'vertical_spacing': '8px',
                                    'horizontal_align': 'left',
                                    'vertical_align': 'top',
                                    'margin': '0px 0px 0px 0px',
                                },
                            ],
                            'margin': '0px 0px 4px 0px',
                        },
                    ],
                },
            }
            # delay / fast 创建卡片模板，delay 延迟打印，fast 实时打印，可以自定义更好看的消息模板

            request: CreateCardRequest = (
                CreateCardRequest.builder()
                .request_body(CreateCardRequestBody.builder().type('card_json').data(json.dumps(card_data)).build())
                .build()
            )

            # 发起请求
            response: CreateCardResponse = self.api_client.cardkit.v1.card.create(request)

            # 处理失败返回
            if not response.success():
                raise Exception(
                    f'client.cardkit.v1.card.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
                )

            self.card_id_dict[message_id] = response.data.card_id

            card_id = response.data.card_id
            return card_id

        except Exception as e:
            raise e

    async def create_message_card(self, message_id, event) -> str:
        """
        创建卡片消息。
        使用卡片消息是因为普通消息更新次数有限制，而大模型流式返回结果可能很多而超过限制，而飞书卡片没有这个限制（api免费次数有限）
        """
        # message_id = event.message_chain.message_id

        card_id = await self.create_card_id(message_id)
        content = {
            'type': 'card',
            'data': {'card_id': card_id, 'template_variable': {'content': 'Thinking...'}},
        }  # 当收到消息时发送消息模板，可添加模板变量，详情查看飞书中接口文档
        request: ReplyMessageRequest = (
            ReplyMessageRequest.builder()
            .message_id(event.message_chain.message_id)
            .request_body(
                ReplyMessageRequestBody.builder().content(json.dumps(content)).msg_type('interactive').build()
            )
            .build()
        )

        # 发起请求
        response: ReplyMessageResponse = await self.api_client.im.v1.message.areply(request)

        # 处理失败返回
        if not response.success():
            raise Exception(
                f'client.im.v1.message.reply failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
            )
        return True

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        # 不再需要了，因为message_id已经被包含到message_chain中
        # lark_event = await self.event_converter.yiri2target(message_source)
        lark_message = await self.message_converter.yiri2target(message, self.api_client)

        final_content = {
            'zh_Hans': {
                'title': '',
                'content': lark_message,
            },
        }

        request: ReplyMessageRequest = (
            ReplyMessageRequest.builder()
            .message_id(message_source.message_chain.message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .content(json.dumps(final_content))
                .msg_type('post')
                .reply_in_thread(False)
                .uuid(str(uuid.uuid4()))
                .build()
            )
            .build()
        )

        response: ReplyMessageResponse = await self.api_client.im.v1.message.areply(request)

        if not response.success():
            raise Exception(
                f'client.im.v1.message.reply failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
            )

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        """
        回复消息变成更新卡片消息
        """
        # self.seq += 1
        message_id = bot_message.resp_message_id
        msg_seq = bot_message.msg_sequence
        if msg_seq % 8 == 0 or is_final:
            lark_message = await self.message_converter.yiri2target(message, self.api_client)

            text_message = ''
            for ele in lark_message[0]:
                if ele['tag'] == 'text':
                    text_message += ele['text']
                elif ele['tag'] == 'md':
                    text_message += ele['text']

            # content = {
            #     'type': 'card_json',
            #     'data': {'card_id': self.card_id_dict[message_id], 'elements': {'content': text_message}},
            # }

            request: ContentCardElementRequest = (
                ContentCardElementRequest.builder()
                .card_id(self.card_id_dict[message_id])
                .element_id('streaming_txt')
                .request_body(
                    ContentCardElementRequestBody.builder()
                    # .uuid("a0d69e20-1dd1-458b-k525-dfeca4015204")
                    .content(text_message)
                    .sequence(msg_seq)
                    .build()
                )
                .build()
            )

            if is_final and bot_message.tool_calls is None:
                # self.seq = 1  # 消息回复结束之后重置seq
                self.card_id_dict.pop(message_id)  # 清理已经使用过的卡片
            # 发起请求
            response: ContentCardElementResponse = self.api_client.cardkit.v1.card_element.content(request)

            # 处理失败返回
            if not response.success():
                raise Exception(
                    f'client.im.v1.message.patch failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
                )
                return

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
        enable_webhook = self.config['enable-webhook']

        if not enable_webhook:
            try:
                await self.bot._connect()
            except lark_oapi.ws.exception.ClientException as e:
                raise e
            except Exception as e:
                await self.bot._disconnect()
                if self.bot._auto_reconnect:
                    await self.bot._reconnect()
                else:
                    raise e
        else:

            async def shutdown_trigger_placeholder():
                while True:
                    await asyncio.sleep(1)

            await self.quart_app.run_task(
                host='0.0.0.0',
                port=port,
                shutdown_trigger=shutdown_trigger_placeholder,
            )

    async def kill(self) -> bool:
        # 需要断开连接，不然旧的连接会继续运行，导致飞书消息来时会随机选择一个连接
        # 断开时lark.ws.Client的_receive_message_loop会打印error日志: receive message loop exit。然后进行重连，
        # 所以要设置_auto_reconnect=False,让其不重连。
        self.bot._auto_reconnect = False
        await self.bot._disconnect()
        return False
