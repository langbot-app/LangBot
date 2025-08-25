import gewechat_client

import typing
import asyncio
import traceback
import time
import re
import copy
import threading

import quart
import aiohttp

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from ....core import app
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
from ....utils import image
import xml.etree.ElementTree as ET
from typing import Optional, Tuple
from functools import partial
from ...logger import EventLogger


class GewechatMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    def __init__(self, config: dict):
        self.config = config

    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain) -> list[dict]:
        content_list = []
        for component in message_chain:
            if isinstance(component, platform_message.At):
                content_list.append({'type': 'at', 'target': component.target})
            elif isinstance(component, platform_message.Plain):
                content_list.append({'type': 'text', 'content': component.text})
            elif isinstance(component, platform_message.Image):
                if not component.url:
                    pass
                content_list.append({'type': 'image', 'image': component.url})

            elif isinstance(component, platform_message.Voice):
                content_list.append({'type': 'voice', 'url': component.url, 'length': component.length})
            elif isinstance(component, platform_message.Forward):
                for node in component.node_list:
                    content_list.extend(await GewechatMessageConverter.yiri2target(node.message_chain))
                content_list.append({'type': 'image', 'image': component.url})
            elif isinstance(component, platform_message.WeChatMiniPrograms):
                content_list.append(
                    {
                        'type': 'WeChatMiniPrograms',
                        'mini_app_id': component.mini_app_id,
                        'display_name': component.display_name,
                        'page_path': component.page_path,
                        'cover_img_url': component.image_url,
                        'title': component.title,
                        'user_name': component.user_name,
                    }
                )
            elif isinstance(component, platform_message.WeChatForwardMiniPrograms):
                content_list.append(
                    {
                        'type': 'WeChatForwardMiniPrograms',
                        'xml_data': component.xml_data,
                        'image_url': component.image_url,
                    }
                )
            elif isinstance(component, platform_message.WeChatEmoji):
                content_list.append(
                    {
                        'type': 'WeChatEmoji',
                        'emoji_md5': component.emoji_md5,
                        'emoji_size': component.emoji_size,
                    }
                )
            elif isinstance(component, platform_message.WeChatLink):
                content_list.append(
                    {
                        'type': 'WeChatLink',
                        'link_title': component.link_title,
                        'link_desc': component.link_desc,
                        'link_thumb_url': component.link_thumb_url,
                        'link_url': component.link_url,
                    }
                )
            elif isinstance(component, platform_message.WeChatForwardLink):
                content_list.append({'type': 'WeChatForwardLink', 'xml_data': component.xml_data})
            elif isinstance(component, platform_message.Voice):
                content_list.append({'type': 'voice', 'url': component.url, 'length': component.length})
            elif isinstance(component, platform_message.WeChatForwardImage):
                content_list.append({'type': 'WeChatForwardImage', 'xml_data': component.xml_data})
            elif isinstance(component, platform_message.WeChatForwardFile):
                content_list.append({'type': 'WeChatForwardFile', 'xml_data': component.xml_data})
            elif isinstance(component, platform_message.WeChatAppMsg):
                content_list.append({'type': 'WeChatAppMsg', 'app_msg': component.app_msg})
            # 引用消息转发
            elif isinstance(component, platform_message.WeChatForwardQuote):
                content_list.append({'type': 'WeChatAppMsg', 'app_msg': component.app_msg})
            elif isinstance(component, platform_message.Forward):
                for node in component.node_list:
                    if node.message_chain:
                        content_list.extend(await GewechatMessageConverter.yiri2target(node.message_chain))

        return content_list

    async def target2yiri(self, message: dict, bot_account_id: str) -> platform_message.MessageChain:
        """外部消息转平台消息"""
        # 数据预处理
        message_list = []
        ats_bot = False  # 是否被@
        content = message['Data']['Content']['string']
        content_no_preifx = content  # 群消息则去掉前缀
        is_group_message = self._is_group_message(message)
        if is_group_message:
            ats_bot = self._ats_bot(message, bot_account_id)
            if '@所有人' in content:
                message_list.append(platform_message.AtAll())
            elif ats_bot:
                message_list.append(platform_message.At(target=bot_account_id))
            content_no_preifx, _ = self._extract_content_and_sender(content)

        msg_type = message['Data']['MsgType']

        # 映射消息类型到处理器方法
        handler_map = {
            1: self._handler_text,
            3: self._handler_image,
            34: self._handler_voice,
            49: self._handler_compound,  # 复合类型
        }

        # 分派处理
        handler = handler_map.get(msg_type, self._handler_default)
        handler_result = await handler(
            message=message,  # 原始的message
            content_no_preifx=content_no_preifx,  # 处理后的content
        )

        if handler_result and len(handler_result) > 0:
            message_list.extend(handler_result)

        return platform_message.MessageChain(message_list)

    async def _handler_text(self, message: Optional[dict], content_no_preifx: str) -> platform_message.MessageChain:
        """处理文本消息 (msg_type=1)"""
        if message and self._is_group_message(message):
            pattern = r'@\S{1,20}'
            content_no_preifx = re.sub(pattern, '', content_no_preifx)

        return platform_message.MessageChain([platform_message.Plain(content_no_preifx)])

    async def _handler_image(self, message: Optional[dict], content_no_preifx: str) -> platform_message.MessageChain:
        """处理图像消息 (msg_type=3)"""
        try:
            image_xml = content_no_preifx
            if not image_xml:
                return platform_message.MessageChain([platform_message.Unknown('[图片内容为空]')])

            base64_str, image_format = await image.get_gewechat_image_base64(
                gewechat_url=self.config['gewechat_url'],
                gewechat_file_url=self.config['gewechat_file_url'],
                app_id=self.config['app_id'],
                xml_content=image_xml,
                token=self.config['token'],
                image_type=2,
            )

            elements = [
                platform_message.Image(base64=f'data:image/{image_format};base64,{base64_str}'),
                platform_message.WeChatForwardImage(xml_data=image_xml),  # 微信消息转发
            ]
            return platform_message.MessageChain(elements)
        except Exception as e:
            print(f'处理图片失败: {str(e)}')
            return platform_message.MessageChain([platform_message.Unknown('[图片处理失败]')])

    async def _handler_voice(self, message: Optional[dict], content_no_preifx: str) -> platform_message.MessageChain:
        """处理语音消息 (msg_type=34)"""
        message_List = []
        try:
            # 从消息中提取语音数据（需根据实际数据结构调整字段名）
            audio_base64 = message['Data']['ImgBuf']['buffer']

            # 验证语音数据有效性
            if not audio_base64:
                message_List.append(platform_message.Unknown(text='[语音内容为空]'))
                return platform_message.MessageChain(message_List)

            # 转换为平台支持的语音格式（如 Silk 格式）
            voice_element = platform_message.Voice(base64=f'data:audio/silk;base64,{audio_base64}')
            message_List.append(voice_element)

        except KeyError as e:
            print(f'语音数据字段缺失: {str(e)}')
            message_List.append(platform_message.Unknown(text='[语音数据解析失败]'))
        except Exception as e:
            print(f'处理语音消息异常: {str(e)}')
            message_List.append(platform_message.Unknown(text='[语音处理失败]'))

        return platform_message.MessageChain(message_List)

    async def _handler_compound(self, message: Optional[dict], content_no_preifx: str) -> platform_message.MessageChain:
        """处理复合消息 (msg_type=49)，根据子类型分派"""
        try:
            xml_data = ET.fromstring(content_no_preifx)
            appmsg_data = xml_data.find('.//appmsg')
            if appmsg_data:
                data_type = appmsg_data.findtext('.//type', '')

                # 二次分派处理器
                sub_handler_map = {
                    '57': self._handler_compound_quote,
                    '5': self._handler_compound_link,
                    '6': self._handler_compound_file,
                    '33': self._handler_compound_mini_program,
                    '36': self._handler_compound_mini_program,
                    '2000': partial(self._handler_compound_unsupported, text='[转账消息]'),
                    '2001': partial(self._handler_compound_unsupported, text='[红包消息]'),
                    '51': partial(self._handler_compound_unsupported, text='[视频号消息]'),
                }

                handler = sub_handler_map.get(data_type, self._handler_compound_unsupported)
                return await handler(
                    message=message,  # 原始msg
                    xml_data=xml_data,  # xml数据
                )
            else:
                return platform_message.MessageChain([platform_message.Unknown(text=content_no_preifx)])
        except Exception as e:
            print(f'解析复合消息失败: {str(e)}')
            return platform_message.MessageChain([platform_message.Unknown(text=content_no_preifx)])

    async def _handler_compound_quote(
        self, message: Optional[dict], xml_data: ET.Element
    ) -> platform_message.MessageChain:
        """处理引用消息 (data_type=57)"""
        message_list = []
        # print("_handler_compound_quote", ET.tostring(xml_data, encoding='unicode'))
        appmsg_data = xml_data.find('.//appmsg')
        quote_data = ''  # 引用原文
        user_data = ''  # 用户消息
        sender_id = xml_data.findtext('.//fromusername')  # 发送方：单聊用户/群member
        if appmsg_data:
            user_data = appmsg_data.findtext('.//title') or ''
            quote_data = appmsg_data.find('.//refermsg').findtext('.//content')
            message_list.append(
                platform_message.WeChatForwardQuote(app_msg=ET.tostring(appmsg_data, encoding='unicode'))
            )
        # quote_data原始的消息
        if quote_data:
            quote_data_message_list = platform_message.MessageChain()
            # 文本消息
            try:
                if '<msg>' not in quote_data:
                    quote_data_message_list.append(platform_message.Plain(quote_data))
                else:
                    # 引用消息展开
                    quote_data_xml = ET.fromstring(quote_data)
                    if quote_data_xml.find('img'):
                        quote_data_message_list.extend(await self._handler_image(None, quote_data))
                    elif quote_data_xml.find('voicemsg'):
                        quote_data_message_list.extend(await self._handler_voice(None, quote_data))
                    elif quote_data_xml.find('videomsg'):
                        quote_data_message_list.extend(await self._handler_default(None, quote_data))  # 先不处理
                    else:
                        # appmsg
                        quote_data_message_list.extend(await self._handler_compound(None, quote_data))
            except Exception as e:
                print(f'处理引用消息异常 expcetion:{e}')
                quote_data_message_list.append(platform_message.Plain(quote_data))
            message_list.append(
                platform_message.Quote(
                    sender_id=sender_id,
                    origin=quote_data_message_list,
                )
            )
            if len(user_data) > 0:
                pattern = r'@\S{1,20}'
                user_data = re.sub(pattern, '', user_data)
                message_list.append(platform_message.Plain(user_data))

        # for comp in message_list:
        #     if isinstance(comp, platform_message.Quote):
        #         print(f"quote_message_chain len={len(message_list)}")
        #         print(f"quote_message_chain send_id={comp.sender_id}" )
        #         for quote_item in comp.origin:
        #             print(f"--quote_message_component [msg_type={quote_item.type}][message={quote_item}]" )
        #     else:
        #         print(f"quote_message_chain plain [msg_type={comp.type}][message={comp.text}]")
        return platform_message.MessageChain(message_list)

    async def _handler_compound_file(self, message: dict, xml_data: ET.Element) -> platform_message.MessageChain:
        """处理文件消息 (data_type=6)"""
        xml_data_str = ET.tostring(xml_data, encoding='unicode')
        return platform_message.MessageChain([platform_message.WeChatForwardFile(xml_data=xml_data_str)])

    async def _handler_compound_link(self, message: dict, xml_data: ET.Element) -> platform_message.MessageChain:
        """处理链接消息（如公众号文章、外部网页）"""
        message_list = []
        try:
            # 解析 XML 中的链接参数
            appmsg = xml_data.find('.//appmsg')
            if appmsg is None:
                return platform_message.MessageChain()
            message_list.append(
                platform_message.WeChatLink(
                    link_title=appmsg.findtext('title', ''),
                    link_desc=appmsg.findtext('des', ''),
                    link_url=appmsg.findtext('url', ''),
                    link_thumb_url=appmsg.findtext('thumburl', ''),  # 这个字段拿不到
                )
            )
            # 转发消息
            xml_data_str = ET.tostring(xml_data, encoding='unicode')
            # print(xml_data_str)
            message_list.append(platform_message.WeChatForwardLink(xml_data=xml_data_str))
        except Exception as e:
            print(f'解析链接消息失败: {str(e)}')
        return platform_message.MessageChain(message_list)

    async def _handler_compound_mini_program(
        self, message: dict, xml_data: ET.Element
    ) -> platform_message.MessageChain:
        """处理小程序消息（如小程序卡片、服务通知）"""
        xml_data_str = ET.tostring(xml_data, encoding='unicode')
        return platform_message.MessageChain([platform_message.WeChatForwardMiniPrograms(xml_data=xml_data_str)])

    async def _handler_default(self, message: Optional[dict], content_no_preifx: str) -> platform_message.MessageChain:
        """处理未知消息类型"""
        if message:
            msg_type = message['Data']['MsgType']
        else:
            msg_type = ''
        return platform_message.MessageChain([platform_message.Unknown(text=f'[未知消息类型 msg_type:{msg_type}]')])

    def _handler_compound_unsupported(
        self, message: dict, xml_data: str, text: Optional[str] = None
    ) -> platform_message.MessageChain:
        """处理未支持复合消息类型(msg_type=49)子类型"""
        if not text:
            text = f'[xml_data={xml_data}]'
        content_list = []
        content_list.append(platform_message.Unknown(text=f'[处理未支持复合消息类型[msg_type=49]|{text}'))

        return platform_message.MessageChain(content_list)

    # 返回是否被艾特
    def _ats_bot(self, message: dict, bot_account_id: str) -> bool:
        ats_bot = False
        try:
            to_user_name = message['Wxid']  # 接收方: 所属微信的wxid
            raw_content = message['Data']['Content']['string']  # 原始消息内容
            content_no_prefix, _ = self._extract_content_and_sender(raw_content)
            # 直接艾特机器人（这个有bug，当被引用的消息里面有@bot,会套娃
            # ats_bot =  ats_bot or (f"@{bot_account_id}" in content_no_prefix)
            # 文本类@bot
            push_content = message.get('Data', {}).get('PushContent', '')
            ats_bot = ats_bot or ('在群聊中@了你' in push_content)
            # 引用别人时@bot
            msg_source = message.get('Data', {}).get('MsgSource', '') or ''
            if len(msg_source) > 0:
                msg_source_data = ET.fromstring(msg_source)
                at_user_list = msg_source_data.findtext('atuserlist') or ''
                ats_bot = ats_bot or (to_user_name in at_user_list)
            # 引用bot
            if message.get('Data', {}).get('MsgType', 0) == 49:
                xml_data = ET.fromstring(content_no_prefix)
                appmsg_data = xml_data.find('.//appmsg')
                tousername = message['Wxid']
                if appmsg_data:  # 接收方: 所属微信的wxid
                    quote_id = appmsg_data.find('.//refermsg').findtext('.//chatusr')  # 引用消息的原发送者
                    ats_bot = ats_bot or (quote_id == tousername)
        except Exception as e:
            print(f'Error in gewechat _ats_bot: {e}')
        finally:
            return ats_bot

    # 提取一下content前面的sender_id, 和去掉前缀的内容
    def _extract_content_and_sender(self, raw_content: str) -> Tuple[str, Optional[str]]:
        try:
            # 检查消息开头，如果有 wxid_sbitaz0mt65n22:\n 则删掉
            # add: 有些用户的wxid不是上述格式。换成user_name:
            regex = re.compile(r'^[a-zA-Z0-9_\-]{5,20}:')
            line_split = raw_content.split('\n')
            if len(line_split) > 0 and regex.match(line_split[0]):
                raw_content = '\n'.join(line_split[1:])
                sender_id = line_split[0].strip(':')
                return raw_content, sender_id
        except Exception as e:
            print(f'_extract_content_and_sender got except: {e}')
        finally:
            return raw_content, None

    # 是否是群消息
    def _is_group_message(self, message: dict) -> bool:
        from_user_name = message['Data']['FromUserName']['string']
        return from_user_name.endswith('@chatroom')


class GewechatEventConverter(abstract_platform_adapter.AbstractEventConverter):
    def __init__(self, config: dict):
        self.config = config
        self.message_converter = GewechatMessageConverter(config)

    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent) -> dict:
        pass

    async def target2yiri(self, event: dict, bot_account_id: str) -> platform_events.MessageEvent:
        # print(event)
        # 排除自己发消息回调回答问题
        if event['Wxid'] == event['Data']['FromUserName']['string']:
            return None
        # 排除公众号以及微信团队消息
        if event['Data']['FromUserName']['string'].startswith('gh_') or event['Data']['FromUserName'][
            'string'
        ].startswith('weixin'):
            return None
        message_chain = await self.message_converter.target2yiri(copy.deepcopy(event), bot_account_id)

        if not message_chain:
            return None

        if '@chatroom' in event['Data']['FromUserName']['string']:
            # 找出开头的 wxid_ 字符串，以:结尾
            sender_wxid = event['Data']['Content']['string'].split(':')[0]

            return platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=sender_wxid,
                    member_name=event['Data']['FromUserName']['string'],
                    permission=platform_entities.Permission.Member,
                    group=platform_entities.Group(
                        id=event['Data']['FromUserName']['string'],
                        name=event['Data']['FromUserName']['string'],
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                    join_timestamp=0,
                    last_speak_timestamp=0,
                    mute_time_remaining=0,
                ),
                message_chain=message_chain,
                time=event['Data']['CreateTime'],
                source_platform_object=event,
            )
        else:
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event['Data']['FromUserName']['string'],
                    nickname=event['Data']['FromUserName']['string'],
                    remark='',
                ),
                message_chain=message_chain,
                time=event['Data']['CreateTime'],
                source_platform_object=event,
            )


class GeWeChatAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    name: str = 'gewechat'  # 定义适配器名称

    bot: gewechat_client.GewechatClient
    quart_app: quart.Quart

    bot_account_id: str

    config: dict

    ap: app.Application

    message_converter: GewechatMessageConverter
    event_converter: GewechatEventConverter

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}

    def __init__(self, config: dict, ap: app.Application, logger: EventLogger):
        self.config = config
        self.ap = ap
        self.logger = logger
        self.quart_app = quart.Quart(__name__)

        self.message_converter = GewechatMessageConverter(config)
        self.event_converter = GewechatEventConverter(config)

        @self.quart_app.route('/gewechat/callback', methods=['POST'])
        async def gewechat_callback():
            data = await quart.request.json
            # print(json.dumps(data, indent=4, ensure_ascii=False))
            await self.logger.debug(f'Gewechat callback event: {data}')

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
                except Exception:
                    await self.logger.error(f'Error in gewechat callback: {traceback.format_exc()}')

                if event.__class__ in self.listeners:
                    await self.listeners[event.__class__](event, self)

                return 'ok'

    async def _handle_message(self, message: platform_message.MessageChain, target_id: str):
        """统一消息处理核心逻辑"""
        content_list = await self.message_converter.yiri2target(message)
        at_targets = [item['target'] for item in content_list if item['type'] == 'at']

        # 处理@逻辑
        at_targets = at_targets or []
        member_info = []
        if at_targets:
            member_info = self.bot.get_chatroom_member_detail(self.config['app_id'], target_id, at_targets[::-1])[
                'data'
            ]

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
                    ats=','.join(at_targets),
                ),
                'image': lambda msg: self.bot.post_image(
                    app_id=self.config['app_id'],
                    to_wxid=target_id,
                    img_url=msg['image'],
                ),
                'WeChatForwardMiniPrograms': lambda msg: self.bot.forward_mini_app(
                    app_id=self.config['app_id'],
                    to_wxid=target_id,
                    xml=msg['xml_data'],
                    cover_img_url=msg.get('image_url'),
                ),
                'WeChatEmoji': lambda msg: self.bot.post_emoji(
                    app_id=self.config['app_id'],
                    to_wxid=target_id,
                    emoji_md5=msg['emoji_md5'],
                    emoji_size=msg['emoji_size'],
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
                    user_name=msg['user_name'],
                ),
                'WeChatForwardLink': lambda msg: self.bot.forward_url(
                    app_id=self.config['app_id'], to_wxid=target_id, xml=msg['xml_data']
                ),
                'WeChatForwardImage': lambda msg: self.bot.forward_image(
                    app_id=self.config['app_id'], to_wxid=target_id, xml=msg['xml_data']
                ),
                'WeChatForwardFile': lambda msg: self.bot.forward_file(
                    app_id=self.config['app_id'], to_wxid=target_id, xml=msg['xml_data']
                ),
                'voice': lambda msg: self.bot.post_voice(
                    app_id=self.config['app_id'],
                    to_wxid=target_id,
                    voice_url=msg['url'],
                    voice_duration=msg['length'],
                ),
                'WeChatAppMsg': lambda msg: self.bot.post_app_msg(
                    app_id=self.config['app_id'],
                    to_wxid=target_id,
                    appmsg=msg['app_msg'],
                ),
                'at': lambda msg: None,
            }

            if handler := handler_map.get(msg['type']):
                handler(msg)
            else:
                await self.logger.warning(f'未处理的消息类型: {msg["type"]}')
                continue

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        """主动发送消息"""
        return await self._handle_message(message, target_id)

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        """回复消息"""
        if message_source.source_platform_object:
            target_id = message_source.source_platform_object['Data']['FromUserName']['string']
            return await self._handle_message(message, target_id)

    async def is_muted(self, group_id: int) -> bool:
        pass

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
        pass

    async def run_async(self):
        if not self.config['token']:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.config["gewechat_url"]}/v2/api/tools/getTokenId',
                    json={'app_id': self.config['app_id']},
                ) as response:
                    if response.status != 200:
                        raise Exception(f'获取gewechat token失败: {await response.text()}')
                    self.config['token'] = (await response.json())['data']

        self.bot = gewechat_client.GewechatClient(f'{self.config["gewechat_url"]}/v2/api', self.config['token'])

        def gewechat_login_process():
            app_id, error_msg = self.bot.login(self.config['app_id'])
            if error_msg:
                raise Exception(f'Gewechat 登录失败: {error_msg}')

            self.config['app_id'] = app_id

            print(f'Gewechat 登录成功，app_id: {app_id}')

            # 获取 nickname
            profile = self.bot.get_profile(self.config['app_id'])
            self.bot_account_id = profile['data']['nickName']

            time.sleep(2)

            try:
                # gewechat-server容器重启, token会变，但是还会登录成功
                # 换新token也会收不到回调，要重新登陆下。
                self.bot.set_callback(self.config['token'], self.config['callback_url'])
            except Exception as e:
                raise Exception(f'设置 Gewechat 回调失败， token失效： {e}')

        threading.Thread(target=gewechat_login_process).start()

        async def shutdown_trigger_placeholder():
            while True:
                await asyncio.sleep(1)

        await self.quart_app.run_task(
            host='0.0.0.0',
            port=self.config['port'],
            shutdown_trigger=shutdown_trigger_placeholder,
        )

    async def kill(self) -> bool:
        pass
