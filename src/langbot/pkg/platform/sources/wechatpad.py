import requests
import websocket
import json
import time
import httpx

from langbot.libs.wechatpad_api.client import WeChatPadClient

import typing
import asyncio
import traceback
import re
import base64
import copy
import threading

import quart

from langbot.pkg.platform.logger import EventLogger
import xml.etree.ElementTree as ET
from typing import Optional, Tuple
from functools import partial
import logging
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger


class WeChatPadMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        self.bot = WeChatPadClient(config['wechatpad_url'], config['token'])
        self.config = config
        self.logger = logger

        # super().__init__(
        #     config = config,
        #     bot = bot,
        #     logger = logger,
        # )

    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain) -> list[dict]:
        content_list = []

        for component in message_chain:
            if isinstance(component, platform_message.AtAll):
                content_list.append({'type': 'at', 'target': 'all'})
            elif isinstance(component, platform_message.At):
                content_list.append({'type': 'at', 'target': component.target})
            elif isinstance(component, platform_message.Plain):
                content_list.append({'type': 'text', 'content': component.text})
            elif isinstance(component, platform_message.Image):
                if component.url:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(component.url)

                        if response.status_code == 200:
                            file_bytes = response.content
                            base64_str = base64.b64encode(file_bytes).decode('utf-8')  # 返回字符串格式
                        else:
                            raise Exception('获取文件失败')
                    # pass
                    content_list.append({'type': 'image', 'image': base64_str})
                elif component.base64:
                    content_list.append({'type': 'image', 'image': component.base64})

            elif isinstance(component, platform_message.WeChatEmoji):
                content_list.append(
                    {'type': 'WeChatEmoji', 'emoji_md5': component.emoji_md5, 'emoji_size': component.emoji_size}
                )
            elif isinstance(component, platform_message.Voice):
                content_list.append({'type': 'voice', 'data': component.url, 'duration': component.length, 'forma': 0})
            elif isinstance(component, platform_message.WeChatAppMsg):
                content_list.append({'type': 'WeChatAppMsg', 'app_msg': component.app_msg})
            elif isinstance(component, platform_message.Forward):
                for node in component.node_list:
                    if node.message_chain:
                        content_list.extend(await WeChatPadMessageConverter.yiri2target(node.message_chain))

        return content_list

    async def target2yiri(
        self,
        message: dict,
        bot_account_id: str,
    ) -> platform_message.MessageChain:
        """外部消息转平台消息"""
        # 数据预处理
        message_list = []
        bot_wxid = self.config['wxid']
        ats_bot = False  # 是否被@
        content = message['content']['str']
        content_no_preifx = content  # 群消息则去掉前缀
        is_group_message = self._is_group_message(message)
        if is_group_message:
            ats_bot = self._ats_bot(message, bot_account_id)

            self.logger.info(f'ats_bot: {ats_bot}; bot_account_id: {bot_account_id}; bot_wxid: {bot_wxid}')
            if '@所有人' in content:
                message_list.append(platform_message.AtAll())
            if ats_bot:
                message_list.append(platform_message.At(target=bot_account_id))

            # 解析@信息并生成At组件
            at_targets = self._extract_at_targets(message)
            for target_id in at_targets:
                if target_id != bot_wxid:  # 避免重复添加机器人的At
                    message_list.append(platform_message.At(target=target_id))

            content_no_preifx, _ = self._extract_content_and_sender(content)

        msg_type = message['msg_type']

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

        return platform_message.MessageChain([platform_message.Plain(text=content_no_preifx)])

    async def _handler_image(self, message: Optional[dict], content_no_preifx: str) -> platform_message.MessageChain:
        """处理图像消息 (msg_type=3)"""
        try:
            image_xml = content_no_preifx
            if not image_xml:
                return platform_message.MessageChain([platform_message.Unknown('[图片内容为空]')])
            root = ET.fromstring(image_xml)

            # 提取img标签的属性
            img_tag = root.find('img')
            if img_tag is not None:
                aeskey = img_tag.get('aeskey')
                cdnthumburl = img_tag.get('cdnthumburl')
                # cdnmidimgurl = img_tag.get('cdnmidimgurl')

            image_data = self.bot.cdn_download(aeskey=aeskey, file_type=1, file_url=cdnthumburl)
            if image_data['Data']['FileData'] == '':
                image_data = self.bot.cdn_download(aeskey=aeskey, file_type=2, file_url=cdnthumburl)
            base64_str = image_data['Data']['FileData']
            # self.logger.info(f"data:image/png;base64,{base64_str}")

            elements = [
                platform_message.Image(base64=f'data:image/png;base64,{base64_str}'),
                # platform_message.WeChatForwardImage(xml_data=image_xml)  # 微信消息转发
            ]
            return platform_message.MessageChain(elements)
        except Exception as e:
            self.logger.error(f'处理图片失败: {str(e)}')
            return platform_message.MessageChain([platform_message.Unknown('[图片处理失败]')])

    async def _handler_voice(self, message: Optional[dict], content_no_preifx: str) -> platform_message.MessageChain:
        """处理语音消息 (msg_type=34)"""
        message_List = []
        try:
            # 从消息中提取语音数据（需根据实际数据结构调整字段名）
            # audio_base64 = message["img_buf"]["buffer"]
            voice_xml = content_no_preifx
            new_msg_id = message['new_msg_id']
            root = ET.fromstring(voice_xml)

            # 提取voicemsg标签的属性
            voicemsg = root.find('voicemsg')
            if voicemsg is not None:
                bufid = voicemsg.get('bufid')
                length = voicemsg.get('voicelength')
            voice_data = self.bot.get_msg_voice(buf_id=str(bufid), length=int(length), msgid=str(new_msg_id))
            audio_base64 = voice_data['Data']['Base64']

            # 验证语音数据有效性
            if not audio_base64:
                message_List.append(platform_message.Unknown(text='[语音内容为空]'))
                return platform_message.MessageChain(message_List)

            # 转换为平台支持的语音格式（如 Silk 格式）
            voice_element = platform_message.Voice(base64=f'data:audio/silk;base64,{audio_base64}')
            message_List.append(voice_element)

        except KeyError as e:
            self.logger.error(f'语音数据字段缺失: {str(e)}')
            message_List.append(platform_message.Unknown(text='[语音数据解析失败]'))
        except Exception as e:
            self.logger.error(f'处理语音消息异常: {str(e)}')
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
                    '74': self._handler_compound_file,
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
            self.logger.error(f'解析复合消息失败: {str(e)}')
            return platform_message.MessageChain([platform_message.Unknown(text=content_no_preifx)])

    async def _handler_compound_quote(
        self, message: Optional[dict], xml_data: ET.Element
    ) -> platform_message.MessageChain:
        """处理引用消息 (data_type=57)"""
        message_list = []
        #         self.logger.info("_handler_compound_quote", ET.tostring(xml_data, encoding='unicode'))
        appmsg_data = xml_data.find('.//appmsg')
        quote_data = ''  # 引用原文
        # quote_id = None  # 引用消息的原发送者
        # tousername = None  # 接收方: 所属微信的wxid
        user_data = ''  # 用户消息
        sender_id = xml_data.findtext('.//fromusername')  # 发送方：单聊用户/群member

        # 引用消息转发
        if appmsg_data:
            user_data = appmsg_data.findtext('.//title') or ''
            quote_data = appmsg_data.find('.//refermsg').findtext('.//content')
            # quote_id = appmsg_data.find('.//refermsg').findtext('.//chatusr')
            message_list.append(platform_message.WeChatAppMsg(app_msg=ET.tostring(appmsg_data, encoding='unicode')))
        # if message:
        #     tousername = message['to_user_name']['str']

        if quote_data:
            quote_data_message_list = platform_message.MessageChain()
            # 文本消息
            try:
                if '<msg>' not in quote_data:
                    quote_data_message_list.append(platform_message.Plain(text=quote_data))
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
                self.logger.error(f'处理引用消息异常 expcetion:{e}')
                quote_data_message_list.append(platform_message.Plain(text=quote_data))
            message_list.append(
                platform_message.Quote(
                    sender_id=sender_id,
                    origin=quote_data_message_list,
                )
            )
            if len(user_data) > 0:
                pattern = r'@\S{1,20}'
                user_data = re.sub(pattern, '', user_data)
                message_list.append(platform_message.Plain(text=user_data))

        return platform_message.MessageChain(message_list)

    async def _handler_compound_file(self, message: dict, xml_data: ET.Element) -> platform_message.MessageChain:
        """处理文件消息 (data_type=6)"""
        file_data = xml_data.find('.//appmsg')

        if file_data.findtext('.//type', '') == '74':
            return None

        else:
            xml_data_str = ET.tostring(xml_data, encoding='unicode')
            # print(xml_data_str)

            # 提取img标签的属性
            # print(xml_data)
            file_name = file_data.find('title').text
            file_id = file_data.find('md5').text
            # file_szie = file_data.find('totallen')

            # print(file_data)
            if file_data is not None:
                aeskey = xml_data.findtext('.//appattach/aeskey')
                cdnthumburl = xml_data.findtext('.//appattach/cdnattachurl')
                # cdnmidimgurl = img_tag.get('cdnmidimgurl')

            # print(aeskey,cdnthumburl)

            file_data = self.bot.cdn_download(aeskey=aeskey, file_type=5, file_url=cdnthumburl)

            file_base64 = file_data['Data']['FileData']
            # print(file_data)
            file_size = file_data['Data']['TotalSize']

            # print(file_base64)
            return platform_message.MessageChain(
                [
                    platform_message.WeChatFile(
                        file_id=file_id, file_name=file_name, file_size=file_size, file_base64=file_base64
                    ),
                    platform_message.WeChatForwardFile(xml_data=xml_data_str),
                ]
            )

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
            # 还没有发链接的接口, 暂时还需要自己构造appmsg, 先用WeChatAppMsg。
            message_list.append(platform_message.WeChatAppMsg(app_msg=ET.tostring(appmsg, encoding='unicode')))
        except Exception as e:
            self.logger.error(f'解析链接消息失败: {str(e)}')
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
            msg_type = message['msg_type']
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
            to_user_name = message['to_user_name']['str']  # 接收方: 所属微信的wxid
            raw_content = message['content']['str']  # 原始消息内容
            content_no_prefix, _ = self._extract_content_and_sender(raw_content)
            # 直接艾特机器人（这个有bug，当被引用的消息里面有@bot,会套娃
            # ats_bot =  ats_bot or (f"@{bot_account_id}" in content_no_prefix)
            # 文本类@bot
            push_content = message.get('push_content', '')
            ats_bot = ats_bot or ('在群聊中@了你' in push_content)
            # 引用别人时@bot
            msg_source = message.get('msg_source', '') or ''
            if len(msg_source) > 0:
                msg_source_data = ET.fromstring(msg_source)
                at_user_list = msg_source_data.findtext('atuserlist') or ''
                ats_bot = ats_bot or (to_user_name in at_user_list)
            # 引用bot
            if message.get('msg_type', 0) == 49:
                xml_data = ET.fromstring(content_no_prefix)
                appmsg_data = xml_data.find('.//appmsg')
                tousername = message['to_user_name']['str']
                if appmsg_data:  # 接收方: 所属微信的wxid
                    quote_id = appmsg_data.find('.//refermsg').findtext('.//chatusr')  # 引用消息的原发送者
                    ats_bot = ats_bot or (quote_id == tousername)
        except Exception as e:
            self.logger.error(f'_ats_bot got except: {e}')
        finally:
            return ats_bot

    # 提取一下at的wxid列表
    def _extract_at_targets(self, message: dict) -> list[str]:
        """从消息中提取被@用户的ID列表"""
        at_targets = []
        try:
            # 从msg_source中解析atuserlist
            msg_source = message.get('msg_source', '') or ''
            if len(msg_source) > 0:
                msg_source_data = ET.fromstring(msg_source)
                at_user_list = msg_source_data.findtext('atuserlist') or ''
                if at_user_list:
                    # atuserlist格式通常是逗号分隔的用户ID列表
                    at_targets = [user_id.strip() for user_id in at_user_list.split(',') if user_id.strip()]
        except Exception as e:
            self.logger.error(f'_extract_at_targets got except: {e}')
        return at_targets

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
            self.logger.error(f'_extract_content_and_sender got except: {e}')
        finally:
            return raw_content, None

    # 是否是群消息
    def _is_group_message(self, message: dict) -> bool:
        from_user_name = message['from_user_name']['str']
        return from_user_name.endswith('@chatroom')


class WeChatPadEventConverter(abstract_platform_adapter.AbstractEventConverter):
    def __init__(self, config: dict, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.message_converter = WeChatPadMessageConverter(self.config, self.logger)
        # super().__init__(
        #     config=config,
        #     message_converter=message_converter,
        #     logger = logger,
        # )

    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent) -> dict:
        pass

    async def target2yiri(
        self,
        event: dict,
        bot_account_id: str,
    ) -> platform_events.MessageEvent:
        # 排除公众号以及微信团队消息
        if (
            event['from_user_name']['str'].startswith('gh_')
            or event['from_user_name']['str'] == 'weixin'
            or event['from_user_name']['str'] == 'newsapp'
            or event['from_user_name']['str'] == self.config['wxid']
        ):
            return None
        message_chain = await self.message_converter.target2yiri(copy.deepcopy(event), bot_account_id)

        if not message_chain:
            return None

        if '@chatroom' in event['from_user_name']['str']:
            # 找出开头的 wxid_ 字符串，以:结尾
            sender_wxid = event['content']['str'].split(':')[0]

            return platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=sender_wxid,
                    member_name=event['from_user_name']['str'],
                    permission=platform_entities.Permission.Member,
                    group=platform_entities.Group(
                        id=event['from_user_name']['str'],
                        name=event['from_user_name']['str'],
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                    join_timestamp=0,
                    last_speak_timestamp=0,
                    mute_time_remaining=0,
                ),
                message_chain=message_chain,
                time=event['create_time'],
                source_platform_object=event,
            )
        else:
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event['from_user_name']['str'],
                    nickname=event['from_user_name']['str'],
                    remark='',
                ),
                message_chain=message_chain,
                time=event['create_time'],
                source_platform_object=event,
            )


class WeChatPadAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    name: str = 'WeChatPad'  # 定义适配器名称

    bot: WeChatPadClient
    quart_app: quart.Quart

    bot_account_id: str

    config: dict

    logger: EventLogger

    message_converter: WeChatPadMessageConverter
    event_converter: WeChatPadEventConverter

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}

    def __init__(self, config: dict, logger: EventLogger):
        quart_app = quart.Quart(__name__)

        message_converter = WeChatPadMessageConverter(config, logger)
        event_converter = WeChatPadEventConverter(config, logger)
        bot = WeChatPadClient(config['wechatpad_url'], config['token'])
        super().__init__(
            config=config,
            logger=logger,
            quart_app=quart_app,
            message_converter=message_converter,
            event_converter=event_converter,
            listeners={},
            bot_account_id='',
            name='WeChatPad',
            bot=bot,
        )

    async def ws_message(self, data):
        """处理接收到的消息"""

        try:
            event = await self.event_converter.target2yiri(data.copy(), self.bot_account_id)
        except Exception:
            await self.logger.error(f'Error in wechatpad callback: {traceback.format_exc()}')

        if event.__class__ in self.listeners:
            await self.listeners[event.__class__](event, self)

        return 'ok'

    async def _handle_message(self, message: platform_message.MessageChain, target_id: str):
        """统一消息处理核心逻辑"""
        content_list = await self.message_converter.yiri2target(message)
        # print(content_list)
        at_targets = [item['target'] for item in content_list if item['type'] == 'at']
        # print(at_targets)
        # 处理@逻辑
        at_targets = at_targets or []
        member_info = []
        if at_targets:
            member_info = self.bot.get_chatroom_member_detail(
                target_id,
            )['Data']['member_data']['chatroom_member_list']

        # 处理消息组件
        for msg in content_list:
            # 文本消息处理@
            if msg['type'] == 'text' and at_targets:
                if 'all' in at_targets:
                    msg['content'] = f'@所有人 {msg["content"]}'
                else:
                    at_nick_name_list = []
                    for member in member_info:
                        if member['user_name'] in at_targets:
                            at_nick_name_list.append(f'@{member["nick_name"]}')
                    msg['content'] = f'{" ".join(at_nick_name_list)} {msg["content"]}'

            # 统一消息派发
            handler_map = {
                'text': lambda msg: self.bot.send_text_message(
                    to_wxid=target_id, message=msg['content'], ats=['notify@all'] if 'all' in at_targets else at_targets
                ),
                'image': lambda msg: self.bot.send_image_message(
                    to_wxid=target_id, img_url=msg['image'], ats=['notify@all'] if 'all' in at_targets else at_targets
                ),
                'WeChatEmoji': lambda msg: self.bot.send_emoji_message(
                    to_wxid=target_id, emoji_md5=msg['emoji_md5'], emoji_size=msg['emoji_size']
                ),
                'voice': lambda msg: self.bot.send_voice_message(
                    to_wxid=target_id,
                    voice_data=msg['data'],
                    voice_duration=msg['duration'],
                    voice_forma=msg['forma'],
                ),
                'WeChatAppMsg': lambda msg: self.bot.send_app_message(
                    to_wxid=target_id,
                    app_message=msg['app_msg'],
                    type=0,
                ),
                'at': lambda msg: None,
            }

            if handler := handler_map.get(msg['type']):
                handler(msg)
            else:
                self.logger.warning(f'未处理的消息类型: {msg["type"]}')
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
            target_id = message_source.source_platform_object['from_user_name']['str']
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
        if not self.config['admin_key'] and not self.config['token']:
            raise RuntimeError('无wechatpad管理密匙，请填入配置文件后重启')
        else:
            if self.config['token']:
                self.bot = WeChatPadClient(self.config['wechatpad_url'], self.config['token'])
                data = self.bot.get_login_status()
                if data['Code'] == 300 and data['Text'] == '你已退出微信':
                    response = requests.post(
                        f'{self.config["wechatpad_url"]}/admin/GenAuthKey1?key={self.config["admin_key"]}',
                        json={'Count': 1, 'Days': 365},
                    )
                    if response.status_code != 200:
                        raise Exception(f'获取token失败: {response.text}')
                    self.config['token'] = response.json()['Data'][0]

            elif not self.config['token']:
                response = requests.post(
                    f'{self.config["wechatpad_url"]}/admin/GenAuthKey1?key={self.config["admin_key"]}',
                    json={'Count': 1, 'Days': 365},
                )
                if response.status_code != 200:
                    raise Exception(f'获取token失败: {response.text}')
                self.config['token'] = response.json()['Data'][0]

        self.bot = WeChatPadClient(self.config['wechatpad_url'], self.config['token'], logger=self.logger)
        await self.logger.info(self.config['token'])
        thread_1 = threading.Event()

        def wechat_login_process():
            # 不登录，这些先注释掉，避免登陆态尝试拉qrcode。
            # login_data =self.bot.get_login_qr()

            # url = login_data['Data']["QrCodeUrl"]

            profile = self.bot.get_profile()
            # self.logger.info(profile)

            self.bot_account_id = profile['Data']['userInfo']['nickName']['str']
            self.config['wxid'] = profile['Data']['userInfo']['userName']['str']
            thread_1.set()

        # asyncio.create_task(wechat_login_process)
        threading.Thread(target=wechat_login_process).start()

        def connect_websocket_sync() -> None:
            thread_1.wait()
            uri = f'{self.config["wechatpad_ws"]}/GetSyncMsg?key={self.config["token"]}'
            print(f'Connecting to WebSocket: {uri}')

            def on_message(ws, message):
                try:
                    data = json.loads(message)
                    # 这里需要确保ws_message是同步的，或者使用asyncio.run调用异步方法
                    asyncio.run(self.ws_message(data))
                except json.JSONDecodeError:
                    self.logger.error(f'Non-JSON message: {message[:100]}...')

            def on_error(ws, error):
                self.logger.error(f'WebSocket error: {str(error)[:200]}')

            def on_close(ws, close_status_code, close_msg):
                self.logger.info('WebSocket closed, reconnecting...')
                time.sleep(5)
                connect_websocket_sync()  # 自动重连

            def on_open(ws):
                self.logger.info('WebSocket connected successfully!')

            ws = websocket.WebSocketApp(
                uri, on_message=on_message, on_error=on_error, on_close=on_close, on_open=on_open
            )
            ws.run_forever(ping_interval=60, ping_timeout=20)

        # 直接调用同步版本（会阻塞）
        # connect_websocket_sync()

        # 这行代码会在WebSocket连接断开后才会执行
        thread = threading.Thread(target=connect_websocket_sync, name='WebSocketClientThread', daemon=True)
        thread.start()
        self.logger.info('WebSocket client thread started')

    async def kill(self) -> bool:
        pass
