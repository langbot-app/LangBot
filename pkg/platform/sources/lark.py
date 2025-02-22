from __future__ import annotations

import lark_oapi

import typing
import asyncio
import traceback
import time
import re
import base64
import uuid
import json
import datetime
import hashlib
import base64
from Crypto.Cipher import AES

import aiohttp
import lark_oapi.ws.exception
import quart
from flask import jsonify
from lark_oapi.api.im.v1 import *
from lark_oapi.api.verification.v1 import GetVerificationRequest

from .. import adapter
from ...pipeline.longtext.strategies import forward
from ...core import app
from ..types import message as platform_message
from ..types import events as platform_events
from ..types import entities as platform_entities
from ...utils import image


class  AESCipher(object):
    def __init__(self, key):
        self.bs = AES.block_size
        self.key=hashlib.sha256(AESCipher.str_to_bytes(key)).digest()
    @staticmethod
    def str_to_bytes(data):
        u_type = type(b"".decode('utf8'))
        if isinstance(data, u_type):
            return data.encode('utf8')
        return data
    @staticmethod
    def _unpad(s):
        return s[:-ord(s[len(s) - 1:])]
    def decrypt(self, enc):
        iv = enc[:AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return  self._unpad(cipher.decrypt(enc[AES.block_size:]))
    def decrypt_string(self, enc):
        enc = base64.b64decode(enc)
        return  self.decrypt(enc).decode('utf8')


class LarkMessageConverter(adapter.MessageConverter):

    @staticmethod
    async def yiri2target(
        message_chain: platform_message.MessageChain, api_client: lark_oapi.Client
    ) -> typing.Tuple[list]:
        message_elements = []

        pending_paragraph = []

        for msg in message_chain:
            if isinstance(msg, platform_message.Plain):
                pending_paragraph.append({"tag": "md", "text": msg.text})
            elif isinstance(msg, platform_message.At):
                pending_paragraph.append(
                    {"tag": "at", "user_id": msg.target, "style": []}
                )
            elif isinstance(msg, platform_message.AtAll):
                pending_paragraph.append({"tag": "at", "user_id": "all", "style": []})
            elif isinstance(msg, platform_message.Image):

                image_bytes = None

                if msg.base64:
                    image_bytes = base64.b64decode(msg.base64)
                elif msg.url:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(msg.url) as response:
                            image_bytes = await response.read()
                elif msg.path:
                    with open(msg.path, "rb") as f:
                        image_bytes = f.read()

                request: CreateImageRequest = (
                    CreateImageRequest.builder()
                    .request_body(
                        CreateImageRequestBody.builder()
                        .image_type("message")
                        .image(image_bytes)
                        .build()
                    )
                    .build()
                )

                response: CreateImageResponse = await api_client.im.v1.image.acreate(
                    request
                )

                if not response.success():
                    raise Exception(
                        f"client.im.v1.image.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}"
                    )

                image_key = response.data.image_key

                message_elements.append(pending_paragraph)
                message_elements.append(
                    [
                        {
                            "tag": "img",
                            "image_key": image_key,
                        }
                    ]
                )
                pending_paragraph = []
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

        msg_create_time = datetime.datetime.fromtimestamp(
            int(message.create_time) / 1000
        )

        lb_msg_list.append(
            platform_message.Source(id=message.message_id, time=msg_create_time)
        )

        if message.message_type == "text":
            element_list = []

            def text_element_recur(text_ele: dict) -> list[dict]:
                if text_ele["text"] == "":
                    return []

                at_pattern = re.compile(r"@_user_[\d]+")
                at_matches = at_pattern.findall(text_ele["text"])

                name_mapping = {}
                for mathc in at_matches:
                    for mention in message.mentions:
                        if mention.key == mathc:
                            name_mapping[mathc] = mention.name
                            break

                if len(name_mapping.keys()) == 0:
                    return [text_ele]

                # 只处理第一个，剩下的递归处理
                text_split = text_ele["text"].split(list(name_mapping.keys())[0])

                new_list = []

                left_text = text_split[0]
                right_text = text_split[1]

                new_list.extend(
                    text_element_recur({"tag": "text", "text": left_text, "style": []})
                )

                new_list.append(
                    {
                        "tag": "at",
                        "user_id": list(name_mapping.keys())[0],
                        "user_name": name_mapping[list(name_mapping.keys())[0]],
                        "style": [],
                    }
                )

                new_list.extend(
                    text_element_recur({"tag": "text", "text": right_text, "style": []})
                )

                return new_list

            element_list = text_element_recur(
                {"tag": "text", "text": message_content["text"], "style": []}
            )

            message_content = {"title": "", "content": element_list}

        elif message.message_type == "post":
            new_list = []

            for ele in message_content["content"]:
                if type(ele) is dict:
                    new_list.append(ele)
                elif type(ele) is list:
                    new_list.extend(ele)

            message_content["content"] = new_list
        elif message.message_type == "image":
            message_content["content"] = [
                {"tag": "img", "image_key": message_content["image_key"], "style": []}
            ]

        for ele in message_content["content"]:
            if ele["tag"] == "text":
                lb_msg_list.append(platform_message.Plain(text=ele["text"]))
            elif ele["tag"] == "at":
                lb_msg_list.append(platform_message.At(target=ele["user_name"]))
            elif ele["tag"] == "img":
                image_key = ele["image_key"]

                request: GetMessageResourceRequest = (
                    GetMessageResourceRequest.builder()
                    .message_id(message.message_id)
                    .file_key(image_key)
                    .type("image")
                    .build()
                )

                response: GetMessageResourceResponse = (
                    await api_client.im.v1.message_resource.aget(request)
                )

                if not response.success():
                    raise Exception(
                        f"client.im.v1.message_resource.get failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}"
                    )

                image_bytes = response.file.read()
                image_base64 = base64.b64encode(image_bytes).decode()

                image_format = response.raw.headers["content-type"]

                lb_msg_list.append(
                    platform_message.Image(
                        base64=f"data:{image_format};base64,{image_base64}"
                    )
                )

        return platform_message.MessageChain(lb_msg_list)


class LarkEventConverter(adapter.EventConverter):

    @staticmethod
    async def yiri2target(
        event: platform_events.MessageEvent,
    ) -> lark_oapi.im.v1.P2ImMessageReceiveV1:
        pass

    @staticmethod
    async def target2yiri(
        event: lark_oapi.im.v1.P2ImMessageReceiveV1, api_client: lark_oapi.Client
    ) -> platform_events.Event:
        message_chain = await LarkMessageConverter.target2yiri(
            event.event.message, api_client
        )

        if event.event.message.chat_type == "p2p":
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event.event.sender.sender_id.open_id,
                    nickname=event.event.sender.sender_id.union_id,
                    remark="",
                ),
                message_chain=message_chain,
                time=event.event.message.create_time,
            )
        elif event.event.message.chat_type == "group":
            return platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=event.event.sender.sender_id.open_id,
                    member_name=event.event.sender.sender_id.union_id,
                    permission=platform_entities.Permission.Member,
                    group=platform_entities.Group(
                        id=event.event.message.chat_id,
                        name="",
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title="",
                    join_timestamp=0,
                    last_speak_timestamp=0,
                    mute_time_remaining=0,
                ),
                message_chain=message_chain,
                time=event.event.message.create_time,
            )


class LarkAdapter(adapter.MessagePlatformAdapter):

    bot: lark_oapi.ws.Client
    api_client: lark_oapi.Client

    bot_account_id: str  # 用于在流水线中识别at是否是本bot，直接以bot_name作为标识
    lark_tenant_key: str  # 飞书企业key

    message_converter: LarkMessageConverter = LarkMessageConverter()
    event_converter: LarkEventConverter = LarkEventConverter()

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, adapter.MessagePlatformAdapter], None],
    ] = {}

    config: dict
    quart_app: quart.Quart
    ap: app.Application

    def __init__(self, config: dict, ap: app.Application):
        self.config = config
        self.ap = ap
        self.quart_app = quart.Quart(__name__)

        @self.quart_app.route('/lark/callback', methods=['POST'])
        async def lark_callback():
            try:
                data = await quart.request.json

                if 'encrypt' in data:
                    cipher = AESCipher(self.config['encrypt-key'])
                    data = cipher.decrypt_string(data['encrypt'])
                    data = json.loads(data)

                type =  data.get("type")
                if type is None :
                    context = EventContext(data)
                    type = context.header.event_type
                
                if 'url_verification' == type:
                    print(data.get("challenge"))
                    # todo 验证verification token
                    return {
                        "challenge": data.get("challenge")
                    }
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
                    except Exception as e:
                        traceback.print_exc()

                    if event.__class__ in self.listeners:
                        await self.listeners[event.__class__](event, self)

                return {"code": 200, "message": "ok"}
            except Exception as e:
                traceback.print_exc()
                return {"code": 500, "message": "error"}

        async def on_message(event: lark_oapi.im.v1.P2ImMessageReceiveV1):

            lb_event = await self.event_converter.target2yiri(event, self.api_client)

            await self.listeners[type(lb_event)](lb_event, self)

        def sync_on_message(event: lark_oapi.im.v1.P2ImMessageReceiveV1):
            asyncio.create_task(on_message(event))

        event_handler = (
            lark_oapi.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(sync_on_message)
            .build()
        )

        self.bot_account_id = config["bot_name"]

        self.bot = lark_oapi.ws.Client(
            config["app_id"], config["app_secret"], event_handler=event_handler
        )
        self.api_client = (
            lark_oapi.Client.builder()
            .app_id(config["app_id"])
            .app_secret(config["app_secret"])
            .build()
        )

    async def send_message(
        self, target_type: str, target_id: str, message: platform_message.MessageChain
    ):
        pass

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):

        # 不再需要了，因为message_id已经被包含到message_chain中
        # lark_event = await self.event_converter.yiri2target(message_source)
        lark_message = await self.message_converter.yiri2target(
            message, self.api_client
        )

        final_content = {
            "zh_cn": {
                "title": "",
                "content": lark_message,
            },
        }

        request: ReplyMessageRequest = (
            ReplyMessageRequest.builder()
            .message_id(message_source.message_chain.message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .content(json.dumps(final_content))
                .msg_type("post")
                .reply_in_thread(False)
                .uuid(str(uuid.uuid4()))
                .build()
            )
            .build()
        )

        response: ReplyMessageResponse = await self.api_client.im.v1.message.areply(
            request
        )

        if not response.success():
            raise Exception(
                f"client.im.v1.message.reply failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}"
            )

    async def is_muted(self, group_id: int) -> bool:
        return False

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, adapter.MessagePlatformAdapter], None
        ],
    ):
        self.listeners[event_type] = callback

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, adapter.MessagePlatformAdapter], None
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
        return False
