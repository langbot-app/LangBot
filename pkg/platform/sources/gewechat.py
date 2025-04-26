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
import xml.etree.ElementTree as ET
from typing import Optional, List, Tuple

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
            elif isinstance(component, platform_message.WeChatMiniPrograms):
                content_list.append({"type": 'WeChatMiniPrograms', 'mini_app_id': component.mini_app_id, 'display_name': component.display_name,
                                     'page_path': component.page_path, 'cover_img_url': component.image_url, 'title': component.title,
                                     'user_name': component.user_name})
            elif isinstance(component, platform_message.WeChatForwardMiniPrograms):
                content_list.append({"type": 'WeChatForwardMiniPrograms', 'xml_data': component.xml_data, 'image_url': component.image_url})
            elif isinstance(component, platform_message.WeChatEmoji):
                content_list.append({'type': 'WeChatEmoji', 'emoji_md5': component.emoji_md5, 'emoji_size': component.emoji_size})
            elif isinstance(component, platform_message.WeChatLink):
                content_list.append({'type': 'WeChatLink', 'link_title': component.link_title, 'link_desc': component.link_desc,
                                     'link_thumb_url': component.link_thumb_url, 'link_url': component.link_url})
            elif isinstance(component, platform_message.WeChatForwardLink):
                content_list.append({'type': 'WeChatForwardLink', 'xml_data': component.xml_data})
            elif isinstance(component, platform_message.Voice):
                content_list.append({"type": "voice", "url": component.url, "length": component.length})       
            elif isinstance(component, platform_message.WeChatForwardImage):
                content_list.append({'type': 'WeChatForwardImage', 'xml_data': component.xml_data})
            elif isinstance(component, platform_message.WeChatForwardFile):
                content_list.append({'type': 'WeChatForwardFile', 'xml_data': component.xml_data})
            elif isinstance(component, platform_message.WeChatAppMsg):
                content_list.append({'type': 'WeChatAppMsg', 'app_msg': component.app_msg})               
            elif isinstance(component, platform_message.Forward):
                for node in component.node_list:
                    content_list.extend(await GewechatMessageConverter.yiri2target(node.message_chain))

        return content_list

    async def target2yiri(
        self,
        message: dict,
        bot_account_id: str
    ) -> platform_message.MessageChain:

        from_user_name = message['Data']['FromUserName']['string'] # 消息发送方
        raw_content = message["Data"]["Content"]["string"]         # 原始消息内容
        sender_id_in_prefix = Optional[str]                        # 群消息的prefix wxid

        # 群聊消息处理艾特前缀
        if from_user_name.endswith("@chatroom"):
            # 检查消息开头，如果有 wxid_sbitaz0mt65n22:\n 则删掉
            # add: 有些用户的wxid不是上述格式。换成user_name: 
            regex = re.compile(r"^[a-zA-Z0-9_\-]{5,20}:")
            line_split = raw_content.split("\n")
            if len(line_split) > 0 and regex.match(line_split[0]):
                raw_content = "\n".join(line_split[1:])
                sender_id_in_prefix = line_split[0].strip(":")

        # 文本消息
        if message["Data"]["MsgType"] == 1:
            # 正则表达式模式，匹配'@'后跟任意数量的非空白字符
            pattern = r'@\S+'
            at_string = f"@{bot_account_id}"
            content_list = []
            if at_string in raw_content:
                content_list.append(platform_message.At(target=bot_account_id))
                content_list.append(platform_message.Plain(raw_content.replace(at_string, '', 1)))
            # 更优雅的替换改名后@机器人，仅仅限于单独AT的情况
            elif "PushContent" in message['Data'] and '在群聊中@了你' in message["Data"]["PushContent"]:
                if '@所有人' in raw_content:  # at全员时候传入atll不当作at自己
                    content_list.append(platform_message.AtAll())
                else:
                    content_list.append(platform_message.At(target=bot_account_id))
                content_list.append(platform_message.Plain(re.sub(pattern, '',raw_content)))
            else:
                content_list = [platform_message.Plain(raw_content)]

            return platform_message.MessageChain(content_list)
                    
        elif message["Data"]["MsgType"] == 3:
            image_xml = raw_content # 已经去除群聊消息前缀
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
                        base64=f"data:image/{image_format};base64,{base64_str}",
                        xml_data = image_xml
                    )
                ])
            except Exception as e:
                print(f"处理图片消息失败: {str(e)}")
                return platform_message.MessageChain([
                    platform_message.Plain(text=f"[图片处理失败]")
                ])
        elif message["Data"]["MsgType"] == 34:
            try:
                audio_base64 = message["Data"]["ImgBuf"]["buffer"]
                return platform_message.MessageChain(
                    [platform_message.Voice(base64=f"data:audio/silk;base64,{audio_base64}")]
                )
            except Exception as e:
                return platform_message.MessageChain(
                    [platform_message.Plain(text="[无法解析群聊语音的消息]")]  # 小测了一下，免费版拿不到群聊语音消息的base64，或者用什么办法解析xml里的url?
                )
        elif message["Data"]["MsgType"] == 49:
            # 支持微信聊天记录的消息类型，将 XML 内容转换为 MessageChain 传递
            #content = message["Data"]["Content"]["string"]
            try:                
                # raw_content已经不会是wxid开头了
                # 下方是移除<?xml,
                xml_data = raw_content
                if raw_content.startswith('<?xml'):
                    xml_list = raw_content.split('\n')[1:]
                    xml_data = '\n'.join(xml_list)
                content_data = ET.fromstring(xml_data)
                # print(xml_data)
                # 拿到细分消息类型，按照gewe接口中描述
                '''
                小程序：33/36
                引用消息：57
                转账消息：2000
                红包消息：2001
                视频号消息：51
                文件发送完成: 6
                '''
                appmsg_data = content_data.find('.//appmsg')
                data_type = appmsg_data.find('.//type').text
                if data_type == '57':
                    user_data = appmsg_data.findtext('.//title') or ""                  # 用户消息
                    quote_data = appmsg_data.find('.//refermsg').findtext('.//content') # 引用原文
                    launcher_id = message['Data']['FromUserName']['string']             # 发送方：消息发送人的wxid/群id
                    sender_id = content_data.findtext('.//fromusername')                # 发送方：单聊用户/群member
                    tousername = message['Wxid']                                        # 接收方: 所属微信的wxid
                    quote_id = appmsg_data.find('.//refermsg').findtext('.//chatusr')   # 引用消息的原发送者

                    message_list =[]
                    # 群特殊处理：引用消息的原发送者是bot or @bot
                    if launcher_id.endswith('@chatroom'): 
                        # 艾特bot处理逻辑
                        is_ats_bot = f"@{bot_account_id}" in raw_content
                        msg_source = message['Data']['MsgSource']
                        msg_source_data = ET.fromstring(msg_source)
                        atuserlist = msg_source_data.findtext("atuserlist") or ""
                        is_ats_bot = is_ats_bot or (tousername in atuserlist)
                        is_ats_all = '@所有人' in raw_content
                        
                        # 引用判断
                        if (quote_id == tousername or is_ats_bot):
                            # 群消息没有@，会被AtBotRule过滤掉
                            message_list.append(platform_message.At(target=bot_account_id))                        
                    
                    message_list.append(platform_message.Quote(
                            sender_id=sender_id,
                            origin=platform_message.MessageChain(
                                # 这里是文本或者xml, 历史原因定义的Plain
                                [platform_message.Plain(quote_data)]
                            )))
                    message_list.append(platform_message.Plain(user_data)) # FIXME: 这里还有wxid
                    return platform_message.MessageChain(message_list)
                elif data_type == '51':
                    return platform_message.MessageChain(
                        [  # platform_message.Plain(text=f'[视频号消息]'),
                         # 消息链中未知消息，把xml和发送人记录
                         platform_message.Unknown(text=raw_content, 
                                                  sender_id_in_prefix=sender_id_in_prefix)]
                    )
                    # print(content_data)
                elif data_type == '2000':
                    return platform_message.MessageChain(
                        [  # platform_message.Plain(text=f'[转账消息]'),
                         platform_message.Unknown(text=raw_content, 
                                                  sender_id_in_prefix=sender_id_in_prefix)]
                    )
                elif data_type == '2001':
                    return platform_message.MessageChain(
                        [  # platform_message.Plain(text=f'[红包消息]'),
                         platform_message.Unknown(text=raw_content, 
                                                  sender_id_in_prefix=sender_id_in_prefix)]
                    )
                elif data_type == '5':
                    return platform_message.MessageChain(
                        [  # platform_message.Plain(text=f'[公众号消息]'),
                         platform_message.Unknown(text=raw_content, 
                                                  sender_id_in_prefix=sender_id_in_prefix)]
                    )
                elif data_type == '33' or data_type == '36':
                    return platform_message.MessageChain(
                        [  # platform_message.Plain(text=f'[小程序消息]'),
                         platform_message.Unknown(text=raw_content, 
                                                  sender_id_in_prefix=sender_id_in_prefix)]
                    )
                # elif data_type == "6":
                #     pass
                # print(data_type.text)
                else:
                    return platform_message.MessageChain(
                            [platform_message.Unknown(text=raw_content, 
                                                  sender_id_in_prefix=sender_id_in_prefix)]
                        )

                    # try:
                    #     content_bytes = content.encode('utf-8')
                    #     decoded_content = base64.b64decode(content_bytes)
                    #     return platform_message.MessageChain(
                    #         [platform_message.Unknown(content=decoded_content)]
                    #     )  # unknown中没有content
                    # except Exception as e:
                    #     return platform_message.MessageChain(
                    #         [platform_message.Plain(text=content)]
                    #     )
            except Exception as e:
                print(f"Error processing type 49 message: {str(e)}")
                return platform_message.MessageChain(
                    [  # platform_message.Plain(text="[无法解析的消息]"),
                     platform_message.Unknown(text=raw_content)]
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
        # print(event)
        # 排除自己发消息回调回答问题
        if event['Wxid'] == event['Data']['FromUserName']['string']:
            return None
        # 排除公众号以及微信团队消息
        if event['Data']['FromUserName']['string'].startswith('gh_')\
                or event['Data']['FromUserName']['string'].startswith('weixin'):
            return None
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
            self.ap.logger.debug(
                f"Gewechat callback event: {data}"
            )
            
            if 'data' in data:
                data['Data'] = data['data']
            if 'type_name' in data:
                data['TypeName'] = data['type_name']
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

    async def _handle_message(
        self,
        message: platform_message.MessageChain,
        target_id: str
    ):
        """统一消息处理核心逻辑"""
        content_list = await self.message_converter.yiri2target(message)
        at_targets = [item["target"] for item in content_list if item["type"] == "at"]

        # 处理@逻辑
        at_targets = at_targets or []
        member_info = []
        if at_targets:
            member_info = self.bot.get_chatroom_member_detail(
                self.config["app_id"],
                target_id,
                at_targets[::-1]
            )["data"]

        # 处理消息组件
        for msg in content_list:
            # 文本消息处理@
            if msg['type'] == 'text' and at_targets:
                for member in member_info:
                    msg['content'] = f'@{member["nickName"]} {msg["content"]}'

            # 统一消息派发
            handler_map = {
                'text': lambda msg: self.bot.post_text(
                    app_id=self.config['app_id'],
                    to_wxid=target_id,
                    content=msg['content'],
                    ats=",".join(at_targets)
                ),
                'image': lambda msg: self.bot.post_image(
                    app_id=self.config['app_id'],
                    to_wxid=target_id,
                    img_url=msg["image"]
                ),
                'WeChatForwardMiniPrograms': lambda msg: self.bot.forward_mini_app(
                    app_id=self.config['app_id'],
                    to_wxid=target_id,
                    xml=msg['xml_data'],
                    cover_img_url=msg.get('image_url')
                ),
                'WeChatEmoji': lambda msg: self.bot.post_emoji(
                    app_id=self.config['app_id'],
                    to_wxid=target_id,
                    emoji_md5=msg['emoji_md5'],
                    emoji_size=msg['emoji_size']
                ),
                'WeChatLink': lambda msg: self.bot.post_link(
                    app_id=self.config['app_id'],
                    to_wxid=target_id,
                    title=msg['link_title'],
                    desc=msg['link_desc'],
                    link_url=msg['link_url'],
                    thumb_url=msg['link_thumb_url'],
                ),
                'WeChatMiniPrograms': lambda msg: self.bot.post_mini_app(
                    app_id=self.config['app_id'],
                    to_wxid=target_id,
                    mini_app_id=msg['mini_app_id'],
                    display_name=msg['display_name'],
                    page_path=msg['page_path'],
                    cover_img_url=msg['cover_img_url'],
                    title=msg['title'],
                    user_name=msg['user_name']
                ),
                'WeChatForwardLink': lambda msg: self.bot.forward_url(
                    app_id=self.config['app_id'],
                    to_wxid=target_id,
                    xml=msg['xml_data']
                ),
                'WeChatForwardImage': lambda msg: self.bot.forward_image(
                    app_id=self.config['app_id'],
                    to_wxid=target_id,
                    xml=msg['xml_data']
                ),
                'WeChatForwardFile': lambda msg: self.bot.forward_file(
                    app_id=self.config['app_id'],
                    to_wxid=target_id,
                    xml=msg['xml_data']
                ),
                'voice': lambda msg: self.bot.post_voice(
                    app_id=self.config['app_id'],
                    to_wxid=target_id,
                    voice_url=msg['url'],
                    voice_duration=msg['length']
                ),
                'WeChatAppMsg': lambda msg: self.bot.post_app_msg(
                    app_id=self.config['app_id'],
                    to_wxid=target_id,
                    appmsg=msg['app_msg']
                )
            }

            if handler := handler_map.get(msg['type']):
                handler(msg)
            else:
                self.ap.logger.warning(f"未处理的消息类型: {msg['type']}")
                continue

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain
    ):
        """主动发送消息"""
        return await self._handle_message(message, target_id)

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False
    ):
        """回复消息"""
        if message_source.source_platform_object:
            target_id = message_source.source_platform_object["Data"]["FromUserName"]["string"]
            return await self._handle_message(message, target_id)

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

        def gewechat_login_process():

            app_id, error_msg = self.bot.login(self.config["app_id"])
            if error_msg:
                raise Exception(f"Gewechat 登录失败: {error_msg}")

            self.config["app_id"] = app_id

            self.ap.logger.info(f"Gewechat 登录成功，app_id: {app_id}")

            self.ap.platform_mgr.write_back_config('gewechat', self, self.config)

            # 获取 nickname
            profile = self.bot.get_profile(self.config["app_id"])
            self.bot_account_id = profile["data"]["nickName"]

            time.sleep(2)

            try:
                # gewechat-server容器重启, token会变，但是还会登录成功
                # 换新token也会收不到回调，要重新登陆下。
                ret = self.bot.set_callback(self.config["token"], self.config["callback_url"])
            except Exception as e:       
                raise Exception(f"设置 Gewechat 回调失败， token失效： {e}")
                

        threading.Thread(target=gewechat_login_process).start()

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
