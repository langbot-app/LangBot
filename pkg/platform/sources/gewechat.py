from __future__ import annotations

import gewechat_client

import typing
import asyncio
import traceback
import time
import re
import base64
import uuid
import json
import os
import copy
import datetime
import threading

import quart
import aiohttp

from .. import adapter
from ...pipeline.longtext.strategies import forward
from ...core import app
from ..types import message as platform_message
from ..types import events as platform_events
from ..types import entities as platform_entities
from ...utils import image


class GewechatMessageConverter(adapter.MessageConverter):

    def __init__(self, config: dict):
        self.config = config

    @staticmethod
    async def yiri2target(
        message_chain: platform_message.MessageChain
    ) -> list[dict]:
        content_list = []
        for component in message_chain:
            if isinstance(component, platform_message.At):
                content_list.append({"type": "at", "target": component.target})
            elif isinstance(component, platform_message.Plain):
                content_list.append({"type": "text", "content": component.text})
            elif isinstance(component, platform_message.Image):
                if not component.url:
                    pass
                content_list.append({"type": "image", "image": component.url})


            elif isinstance(component, platform_message.Voice):
                content_list.append({"type": "voice", "url": component.url, "length": component.length})
            elif isinstance(component, platform_message.Forward):
                for node in component.node_list:
                    content_list.extend(await GewechatMessageConverter.yiri2target(node.message_chain))

        return content_list

    async def target2yiri(
        self,
        message: dict,
        bot_account_id: str
    ) -> platform_message.MessageChain:

        if message["Data"]["MsgType"] == 1:
            # 检查消息开头，如果有 wxid_sbitaz0mt65n22:\n 则删掉
            regex = re.compile(r"^wxid_.*:")

            line_split = message["Data"]["Content"]["string"].split("\n")

            if len(line_split) > 0 and regex.match(line_split[0]):
                message["Data"]["Content"]["string"] = "\n".join(line_split[1:])

            at_string = f'@{bot_account_id}'
            content_list = []
            if at_string in message["Data"]["Content"]["string"]:
                content_list.append(platform_message.At(target=bot_account_id))
                content_list.append(platform_message.Plain(message["Data"]["Content"]["string"].replace(at_string, "", 1)))
            else:
                content_list = [platform_message.Plain(message["Data"]["Content"]["string"])]

            return platform_message.MessageChain(content_list)
                    
        elif message["Data"]["MsgType"] == 3:
            image_xml = message["Data"]["Content"]["string"]
            if not image_xml:
                return platform_message.MessageChain([
                    platform_message.Plain(text="[图片内容为空]")
                ])


            try:
                base64_str, image_format = await image.get_gewechat_image_base64(
                    gewechat_url=self.config["gewechat_url"],
                    gewechat_file_url=self.config["gewechat_file_url"],
                    app_id=self.config["app_id"],
                    xml_content=image_xml,
                    token=self.config["token"],
                    image_type=2,
                )

                return platform_message.MessageChain([
                    platform_message.Image(
                        base64=f"data:image/{image_format};base64,{base64_str}"
                    )
                ])
            except Exception as e:
                print(f"处理图片消息失败: {str(e)}")
                return platform_message.MessageChain([
                    platform_message.Plain(text=f"[图片处理失败]")
                ])
        elif message["Data"]["MsgType"] == 34:
            audio_base64 = message["Data"]["ImgBuf"]["buffer"]
            return platform_message.MessageChain(
                [platform_message.Voice(base64=f"data:audio/silk;base64,{audio_base64}")]
            )
        elif message["Data"]["MsgType"] == 49:
            # 支持微信聊天记录的消息类型，将 XML 内容转换为 MessageChain 传递
            try:
                content = message["Data"]["Content"]["string"]

                try:
                    content_bytes = content.encode('utf-8')
                    decoded_content = base64.b64decode(content_bytes)
                    return platform_message.MessageChain(
                        [platform_message.Unknown(content=decoded_content)]
                    )
                except Exception as e:
                    return platform_message.MessageChain(
                        [platform_message.Plain(text=content)]
                    )
            except Exception as e:
                print(f"Error processing type 49 message: {str(e)}")
                return platform_message.MessageChain(
                    [platform_message.Plain(text="[无法解析的消息]")]
                )

class GewechatEventConverter(adapter.EventConverter):

    def __init__(self, config: dict):
        self.config = config
        self.message_converter = GewechatMessageConverter(config)

    @staticmethod
    async def yiri2target(
        event: platform_events.MessageEvent
    ) -> dict:
        pass

    async def target2yiri(
        self,
        event: dict,
        bot_account_id: str
    ) -> platform_events.MessageEvent:
        message_chain = await self.message_converter.target2yiri(copy.deepcopy(event), bot_account_id)

        if not message_chain:
            return None
        
        if '@chatroom' in event["Data"]["FromUserName"]["string"]:
            # 找出开头的 wxid_ 字符串，以:结尾
            sender_wxid = event["Data"]["Content"]["string"].split(":")[0]

            return platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=sender_wxid,
                    member_name=event["Data"]["FromUserName"]["string"],
                    permission=platform_entities.Permission.Member,
                    group=platform_entities.Group(
                        id=event["Data"]["FromUserName"]["string"],
                        name=event["Data"]["FromUserName"]["string"],
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title="",
                    join_timestamp=0,
                    last_speak_timestamp=0,
                    mute_time_remaining=0,
                ),
                message_chain=message_chain,
                time=event["Data"]["CreateTime"],
                source_platform_object=event,
            )
        else:
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event["Data"]["FromUserName"]["string"],
                    nickname=event["Data"]["FromUserName"]["string"],
                    remark='',
                ),
                message_chain=message_chain,
                time=event["Data"]["CreateTime"],
                source_platform_object=event,
            )


class GeWeChatAdapter(adapter.MessagePlatformAdapter):

    name: str = "gewechat"  # 定义适配器名称

    bot: gewechat_client.GewechatClient
    quart_app: quart.Quart

    bot_account_id: str

    config: dict

    ap: app.Application

    message_converter: GewechatMessageConverter
    event_converter: GewechatEventConverter

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, adapter.MessagePlatformAdapter], None],
    ] = {}
    
    def __init__(self, config: dict, ap: app.Application):
        self.config = config
        self.ap = ap

        self.quart_app = quart.Quart(__name__)

        self.message_converter = GewechatMessageConverter(config)
        self.event_converter = GewechatEventConverter(config)

        @self.quart_app.route('/gewechat/callback', methods=['POST'])
        async def gewechat_callback():
            data = await quart.request.json
            # print(json.dumps(data, indent=4, ensure_ascii=False))

            if 'testMsg' in data:
                return 'ok'
            elif 'TypeName' in data and data['TypeName'] == 'AddMsg':
                try:

                    event = await self.event_converter.target2yiri(data.copy(), self.bot_account_id)
                except Exception as e:
                    traceback.print_exc()

                if event.__class__ in self.listeners:
                    await self.listeners[event.__class__](event, self)

                return 'ok'

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain
    ):
        geweap_msg = await GewechatMessageConverter.yiri2target(message)
        # 此处加上群消息at处理
        # ats = [item["target"] for item in geweap_msg if item["type"] == "at"]

        for msg in geweap_msg:
            if msg['type'] == 'text':
                await self.bot.post_text(app_id=self.config['app_id'], to_wxid=target_id, content=msg['content'])

            elif msg['type'] == 'image':

                await self.bot.post_image(app_id=self.config['app_id'], to_wxid=target_id, img_url=msg["image"])



    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False
    ):
        content_list = await self.message_converter.yiri2target(message)

        ats = [item["target"] for item in content_list if item["type"] == "at"]

        for msg in content_list:
            if msg["type"] == "text":

                if ats:
                    member_info = self.bot.get_chatroom_member_detail(
                        self.config["app_id"],
                        message_source.source_platform_object["Data"]["FromUserName"]["string"],
                        ats[::-1]
                    )["data"]

                    for member in member_info:
                        msg['content'] = f'@{member["nickName"]} {msg["content"]}'

                self.bot.post_text(
                    app_id=self.config["app_id"],
                    to_wxid=message_source.source_platform_object["Data"]["FromUserName"]["string"],
                    content=msg["content"],
                    ats=','.join(ats)
                )

    async def is_muted(self, group_id: int) -> bool:
        pass

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[[platform_events.Event, adapter.MessagePlatformAdapter], None]
    ):
        self.listeners[event_type] = callback

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[[platform_events.Event, adapter.MessagePlatformAdapter], None]
    ):
        pass

    async def run_async(self):
        
        if not self.config["token"]:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.config['gewechat_url']}/v2/api/tools/getTokenId",
                    json={"app_id": self.config["app_id"]}
                ) as response:
                    if response.status != 200:
                        raise Exception(f"获取gewechat token失败: {await response.text()}")
                    self.config["token"] = (await response.json())["data"]

        self.bot = gewechat_client.GewechatClient(
            f"{self.config['gewechat_url']}/v2/api",
            self.config["token"]
        )

        app_id, error_msg = self.bot.login(self.config["app_id"])
        if error_msg:
            raise Exception(f"Gewechat 登录失败: {error_msg}")

        self.config["app_id"] = app_id

        self.ap.logger.info(f"Gewechat 登录成功，app_id: {app_id}")

        await self.ap.platform_mgr.write_back_config('gewechat', self, self.config)

        # 获取 nickname
        profile = self.bot.get_profile(self.config["app_id"])
        self.bot_account_id = profile["data"]["nickName"]

        def thread_set_callback():
            time.sleep(3)
            ret = self.bot.set_callback(self.config["token"], self.config["callback_url"])
            print('设置 Gewechat 回调：', ret)

        threading.Thread(target=thread_set_callback).start()

        async def shutdown_trigger_placeholder():
            while True:
                await asyncio.sleep(1)

        await self.quart_app.run_task(
            host='0.0.0.0',
            port=self.config["port"],
            shutdown_trigger=shutdown_trigger_placeholder,
        )

    async def kill(self) -> bool:
        pass
