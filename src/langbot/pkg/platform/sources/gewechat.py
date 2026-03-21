import gewechat_client

import typing
import asyncio
import traceback

import re
import copy
import threading

from langbot.pkg.utils import httpclient

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
from ...utils import image
import xml.etree.ElementTree as ET
from typing import Optional, Tuple
from functools import partial
from ..logger import EventLogger


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
            elif isinstance(component, platform_message.WeChatForwardImage):
                content_list.append({'type': 'WeChatForwardImage', 'xml_data': component.xml_data})
            elif isinstance(component, platform_message.WeChatForwardFile):
                content_list.append({'type': 'WeChatForwardFile', 'xml_data': component.xml_data})
            elif isinstance(component, platform_message.WeChatAppMsg):
                content_list.append({'type': 'WeChatAppMsg', 'app_msg': component.app_msg})
            elif isinstance(component, platform_message.WeChatForwardQuote):
                content_list.append({'type': 'WeChatAppMsg', 'app_msg': component.app_msg})
            elif isinstance(component, platform_message.Forward):
                for node in component.node_list:
                    if node.message_chain:
                        content_list.extend(await GewechatMessageConverter.yiri2target(node.message_chain))

        return content_list

    async def target2yiri(self, message: dict, bot_account_id: str) -> platform_message.MessageChain:
        message_list = []
        ats_bot = False
        content = message['Data']['Content']['string']
        content_no_preifx = content
        is_group_message = self._is_group_message(message)
        if is_group_message:
            ats_bot = self._ats_bot(message, bot_account_id)
            if '@所有人' in content:
                message_list.append(platform_message.AtAll())
            elif ats_bot:
                message_list.append(platform_message.At(target=bot_account_id))
            content_no_preifx, _ = self._extract_content_and_sender(content)

        msg_type = message['Data']['MsgType']

        handler_map = {
            1: self._handler_text,
            3: self._handler_image,
            34: self._handler_voice,
            49: self._handler_compound,
        }

        handler = handler_map.get(msg_type, self._handler_default)
        handler_result = await handler(
            message=message,
            content_no_preifx=content_no_preifx,
        )

        if handler_result and len(handler_result) > 0:
            message_list.extend(handler_result)

        return platform_message.MessageChain(message_list)

    async def _handler_text(self, message: Optional[dict], content_no_preifx: str) -> platform_message.MessageChain:
        if message and self._is_group_message(message):
            pattern = r'@\S{1,20}'
            content_no_preifx = re.sub(pattern, '', content_no_preifx)

        return platform_message.MessageChain([platform_message.Plain(content_no_preifx)])

    async def _handler_image(self, message: Optional[dict], content_no_preifx: str) -> platform_message.MessageChain:
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
                platform_message.WeChatForwardImage(xml_data=image_xml),
            ]
            return platform_message.MessageChain(elements)
        except Exception as e:
            print(f'处理图片失败: {str(e)}')
            return platform_message.MessageChain([platform_message.Unknown('[图片处理失败]')])

    async def _handler_voice(self, message: Optional[dict], content_no_preifx: str) -> platform_message.MessageChain:
        message_List = []
        try:
            audio_base64 = message['Data']['ImgBuf']['buffer']

            if not audio_base64:
                message_List.append(platform_message.Unknown(text='[语音内容为空]'))
                return platform_message.MessageChain(message_List)

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
        try:
            xml_data = ET.fromstring(content_no_preifx)
            appmsg_data = xml_data.find('.//appmsg')
            if appmsg_data:
                data_type = appmsg_data.findtext('.//type', '')

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
                    message=message,
                    xml_data=xml_data,
                )
            else:
                return platform_message.MessageChain([platform_message.Unknown(text=content_no_preifx)])
        except Exception as e:
            print(f'解析复合消息失败: {str(e)}')
            return platform_message.MessageChain([platform_message.Unknown(text=content_no_preifx)])

    async def _handler_compound_quote(
        self, message: Optional[dict], xml_data: ET.Element
    ) -> platform_message.MessageChain:
        message_list = []
        appmsg_data = xml_data.find('.//appmsg')
        quote_data = ''
        user_data = ''
        sender_id = xml_data.findtext('.//fromusername')
        if appmsg_data:
            user_data = appmsg_data.findtext('.//title') or ''
            quote_data = appmsg_data.find('.//refermsg').findtext('.//content')
            message_list.append(
                platform_message.WeChatForwardQuote(app_msg=ET.tostring(appmsg_data, encoding='unicode'))
            )
        if quote_data:
            quote_data_message_list = platform_message.MessageChain()
            try:
                if '<msg>' not in quote_data:
                    quote_data_message_list.append(platform_message.Plain(quote_data))
                else:
                    quote_data_xml = ET.fromstring(quote_data)
                    if quote_data_xml.find('img'):
                        quote_data_message_list.extend(await self._handler_image(None, quote_data))
                    elif quote_data_xml.find('voicemsg'):
                        quote_data_message_list.extend(await self._handler_voice(None, quote_data))
                    elif quote_data_xml.find('videomsg'):
                        quote_data_message_list.extend(await self._handler_default(None, quote_data))
                    else:
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

        return platform_message.MessageChain(message_list)

    async def _handler_compound_file(self, message: dict, xml_data: ET.Element) -> platform_message.MessageChain:
        xml_data_str = ET.tostring(xml_data, encoding='unicode')
        return platform_message.MessageChain([platform_message.WeChatForwardFile(xml_data=xml_data_str)])

    async def _handler_compound_link(self, message: dict, xml_data: ET.Element) -> platform_message.MessageChain:
        message_list = []
        try:
            appmsg = xml_data.find('.//appmsg')
            if appmsg is None:
                return platform_message.MessageChain()
            message_list.append(
                platform_message.WeChatLink(
                    link_title=appmsg.findtext('title', ''),
                    link_desc=appmsg.findtext('des', ''),
                    link_url=appmsg.findtext('url', ''),
                    link_thumb_url=appmsg.findtext('thumburl', ''),
                )
            )
            xml_data_str = ET.tostring(xml_data, encoding='unicode')
            message_list.append(platform_message.WeChatForwardLink(xml_data=xml_data_str))
        except Exception as e:
            print(f'解析链接消息失败: {str(e)}')
        return platform_message.MessageChain(message_list)

    async def _handler_compound_mini_program(
        self, message: dict, xml_data: ET.Element
    ) -> platform_message.MessageChain:
        xml_data_str = ET.tostring(xml_data, encoding='unicode')
        return platform_message.MessageChain([platform_message.WeChatForwardMiniPrograms(xml_data=xml_data_str)])

    async def _handler_default(self, message: Optional[dict], content_no_preifx: str) -> platform_message.MessageChain:
        if message:
            msg_type = message['Data']['MsgType']
        else:
            msg_type = ''
        return platform_message.MessageChain([platform_message.Unknown(text=f'[未知消息类型 msg_type:{msg_type}]')])

    def _handler_compound_unsupported(
        self, message: dict, xml_data: str, text: Optional[str] = None
    ) -> platform_message.MessageChain:
        if not text:
            text = f'[xml_data={xml_data}]'
        content_list = []
        content_list.append(platform_message.Unknown(text=f'[处理未支持复合消息类型[msg_type=49]|{text}'))

        return platform_message.MessageChain(content_list)

    def _ats_bot(self, message: dict, bot_account_id: str) -> bool:
        ats_bot = False
        try:
            to_user_name = message['Wxid']
            raw_content = message['Data']['Content']['string']
            content_no_prefix, _ = self._extract_content_and_sender(raw_content)
            push_content = message.get('Data', {}).get('PushContent', '')
            ats_bot = ats_bot or ('在群聊中@了你' in push_content)
            msg_source = message.get('Data', {}).get('MsgSource', '') or ''
            if len(msg_source) > 0:
                msg_source_data = ET.fromstring(msg_source)
                at_user_list = msg_source_data.findtext('atuserlist') or ''
                ats_bot = ats_bot or (to_user_name in at_user_list)
            if message.get('Data', {}).get('MsgType', 0) == 49:
                xml_data = ET.fromstring(content_no_prefix)
                appmsg_data = xml_data.find('.//appmsg')
                tousername = message['Wxid']
                if appmsg_data:
                    quote_id = appmsg_data.find('.//refermsg').findtext('.//chatusr')
                    ats_bot = ats_bot or (quote_id == tousername)
        except Exception as e:
            print(f'Error in gewechat _ats_bot: {e}')
        finally:
            return ats_bot

    def _extract_content_and_sender(self, raw_content: str) -> Tuple[str, Optional[str]]:
        try:
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
        if event['Wxid'] == event['Data']['FromUserName']['string']:
            return None
        if event['Data']['FromUserName']['string'].startswith('gh_') or event['Data']['FromUserName'][
            'string'
        ].startswith('weixin'):
            return None
        message_chain = await self.message_converter.target2yiri(copy.deepcopy(event), bot_account_id)

        if not message_chain:
            return None

        if '@chatroom' in event['Data']['FromUserName']['string']:
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
    bot: gewechat_client.GewechatClient = None
    bot_uuid: str = None
    message_converter: GewechatMessageConverter = None
    event_converter: GewechatEventConverter = None

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}

    def __init__(self, config: dict, logger: EventLogger):
        super().__init__(
            config=config,
            logger=logger,
        )

        self.message_converter = GewechatMessageConverter(config)
        self.event_converter = GewechatEventConverter(config)

    def set_bot_uuid(self, bot_uuid: str):
        self.bot_uuid = bot_uuid

    async def handle_unified_webhook(self, bot_uuid: str, path: str, request):
        data = await request.json
        await self.logger.debug(f'Gewechat callback event: {data}')

        if 'data' in data:
            data['Data'] = data['data']
        if 'type_name' in data:
            data['TypeName'] = data['type_name']

        if 'testMsg' in data:
            return 'ok'
        elif 'TypeName' in data and data['TypeName'] == 'AddMsg':
            try:
                event = await self.event_converter.target2yiri(data.copy(), self.bot_account_id)
            except Exception:
                await self.logger.error(f'Error in gewechat callback: {traceback.format_exc()}')
                return 'ok'

            if event and event.__class__ in self.listeners:
                await self.listeners[event.__class__](event, self)

            return 'ok'

        return 'ok'

    async def _handle_message(self, message: platform_message.MessageChain, target_id: str):
        content_list = await self.message_converter.yiri2target(message)
        at_targets = [item['target'] for item in content_list if item['type'] == 'at']

        at_targets = at_targets or []
        member_info = []
        if at_targets:
            member_info = self.bot.get_chatroom_member_detail(self.config['app_id'], target_id, at_targets[::-1])[
                'data'
            ]

        for msg in content_list:
            if msg['type'] == 'text' and at_targets:
                for member in member_info:
                    msg['content'] = f'@{member["nickName"]} {msg["content"]}'

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
        return await self._handle_message(message, target_id)

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
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

    def _build_callback_url(self) -> str:
        webhook_prefix = self.config.get('_webhook_prefix', 'http://127.0.0.1:5300').rstrip('/')
        return f'{webhook_prefix}/bots/{self.bot_uuid}'

    async def run_async(self):
        if not self.config['token']:
            session = httpclient.get_session()
            async with session.post(
                f'{self.config["gewechat_url"]}/v2/api/tools/getTokenId',
                json={'app_id': self.config['app_id']},
            ) as response:
                if response.status != 200:
                    raise Exception(f'获取gewechat token失败: {await response.text()}')
                self.config['token'] = (await response.json())['data']

        self.bot = gewechat_client.GewechatClient(f'{self.config["gewechat_url"]}/v2/api', self.config['token'])

        def gewechat_init_process():
            profile = self.bot.get_profile(self.config['app_id'])
            self.bot_account_id = profile['data']['nickName']

            try:
                callback_url = self._build_callback_url()
                self.bot.set_callback(self.config['token'], callback_url)
                print(f'Gewechat 回调地址已设置: {callback_url}')
            except Exception as e:
                raise Exception(f'设置 Gewechat 回调失败，token失效：{e}')

        threading.Thread(target=gewechat_init_process).start()

        # 统一 webhook 模式下，不启动独立的 HTTP 服务
        # 保持适配器运行
        while True:
            await asyncio.sleep(1)

    async def kill(self) -> bool:
        return False
