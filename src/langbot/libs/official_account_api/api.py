# 微信公众号的加解密算法与企业微信一样，所以直接使用企业微信的加解密算法文件
import time
import traceback
from langbot.libs.wecom_api.WXBizMsgCrypt3 import WXBizMsgCrypt
import xml.etree.ElementTree as ET
from quart import Quart, request
import hashlib
from typing import Callable
from langbot.libs.official_account_api.oaevent import OAEvent

import asyncio


xml_template = """
<xml>
    <ToUserName><![CDATA[{to_user}]]></ToUserName>
    <FromUserName><![CDATA[{from_user}]]></FromUserName>
    <CreateTime>{create_time}</CreateTime>
    <MsgType><![CDATA[text]]></MsgType>
    <Content><![CDATA[{content}]]></Content>
</xml>
"""


class OAClient:
    def __init__(self, token: str, EncodingAESKey: str, AppID: str, Appsecret: str, logger: None):
        self.token = token
        self.aes = EncodingAESKey
        self.appid = AppID
        self.appsecret = Appsecret
        self.base_url = 'https://api.weixin.qq.com'
        self.access_token = ''
        self.app = Quart(__name__)
        self.app.add_url_rule(
            '/callback/command',
            'handle_callback',
            self.handle_callback_request,
            methods=['GET', 'POST'],
        )
        self._message_handlers = {
            'example': [],
        }
        self.access_token_expiry_time = None
        self.msg_id_map = {}
        self.generated_content = {}
        self.logger = logger

    async def handle_callback_request(self):
        try:
            # 每隔100毫秒查询是否生成ai回答
            start_time = time.time()
            signature = request.args.get('signature', '')
            timestamp = request.args.get('timestamp', '')
            nonce = request.args.get('nonce', '')
            echostr = request.args.get('echostr', '')
            msg_signature = request.args.get('msg_signature', '')
            if msg_signature is None:
                await self.logger.error('msg_signature不在请求体中')
                raise Exception('msg_signature不在请求体中')

            if request.method == 'GET':
                # 校验签名
                check_str = ''.join(sorted([self.token, timestamp, nonce]))
                check_signature = hashlib.sha1(check_str.encode('utf-8')).hexdigest()

                if check_signature == signature:
                    return echostr  # 验证成功返回echostr
                else:
                    await self.logger.error('拒绝请求')
                    raise Exception('拒绝请求')
            elif request.method == 'POST':
                encryt_msg = await request.data
                wxcpt = WXBizMsgCrypt(self.token, self.aes, self.appid)
                ret, xml_msg = wxcpt.DecryptMsg(encryt_msg, msg_signature, timestamp, nonce)
                xml_msg = xml_msg.decode('utf-8')

                if ret != 0:
                    await self.logger.error('消息解密失败')
                    raise Exception('消息解密失败')

                message_data = await self.get_message(xml_msg)
                if message_data:
                    event = OAEvent.from_payload(message_data)
                    if event:
                        await self._handle_message(event)

                root = ET.fromstring(xml_msg)
                from_user = root.find('FromUserName').text  # 发送者
                to_user = root.find('ToUserName').text  # 机器人

                timeout = 4.80
                interval = 0.1
                while True:
                    content = self.generated_content.pop(message_data['MsgId'], None)
                    if content:
                        response_xml = xml_template.format(
                            to_user=from_user,
                            from_user=to_user,
                            create_time=int(time.time()),
                            content=content,
                        )

                        return response_xml

                    if time.time() - start_time >= timeout:
                        break

                    await asyncio.sleep(interval)

                if self.msg_id_map.get(message_data['MsgId'], 1) == 3:
                    # response_xml = xml_template.format(
                    #     to_user=from_user,
                    #     from_user=to_user,
                    #     create_time=int(time.time()),
                    #     content = "请求失效：暂不支持公众号超过15秒的请求，如有需求，请联系 LangBot 团队。"
                    # )
                    print('请求失效：暂不支持公众号超过15秒的请求，如有需求，请联系 LangBot 团队。')
                    return ''

        except Exception:
            await self.logger.error(f'handle_callback_request失败: {traceback.format_exc()}')
            traceback.print_exc()

    async def get_message(self, xml_msg: str):
        root = ET.fromstring(xml_msg)

        message_data = {
            'ToUserName': root.find('ToUserName').text,
            'FromUserName': root.find('FromUserName').text,
            'CreateTime': int(root.find('CreateTime').text),
            'MsgType': root.find('MsgType').text,
            'Content': root.find('Content').text if root.find('Content') is not None else None,
            'MsgId': int(root.find('MsgId').text) if root.find('MsgId') is not None else None,
        }

        return message_data

    async def run_task(self, host: str, port: int, *args, **kwargs):
        """
        启动 Quart 应用。
        """
        await self.app.run_task(host=host, port=port, *args, **kwargs)

    def on_message(self, msg_type: str):
        """
        注册消息类型处理器。
        """

        def decorator(func: Callable[[OAEvent], None]):
            if msg_type not in self._message_handlers:
                self._message_handlers[msg_type] = []
            self._message_handlers[msg_type].append(func)
            return func

        return decorator

    async def _handle_message(self, event: OAEvent):
        """
        处理消息事件。
        """
        message_id = event.message_id
        if message_id in self.msg_id_map.keys():
            self.msg_id_map[message_id] += 1
            return

        self.msg_id_map[message_id] = 1
        msg_type = event.type
        if msg_type in self._message_handlers:
            for handler in self._message_handlers[msg_type]:
                await handler(event)

    async def set_message(self, msg_id: int, content: str):
        self.generated_content[msg_id] = content


class OAClientForLongerResponse:
    def __init__(
        self,
        token: str,
        EncodingAESKey: str,
        AppID: str,
        Appsecret: str,
        LoadingMessage: str,
        logger: None,
    ):
        self.token = token
        self.aes = EncodingAESKey
        self.appid = AppID
        self.appsecret = Appsecret
        self.base_url = 'https://api.weixin.qq.com'
        self.access_token = ''
        self.app = Quart(__name__)
        self.app.add_url_rule(
            '/callback/command',
            'handle_callback',
            self.handle_callback_request,
            methods=['GET', 'POST'],
        )
        self._message_handlers = {
            'example': [],
        }
        self.access_token_expiry_time = None
        self.loading_message = LoadingMessage
        self.msg_queue = {}
        self.user_msg_queue = {}
        self.logger = logger

    async def handle_callback_request(self):
        try:
            signature = request.args.get('signature', '')
            timestamp = request.args.get('timestamp', '')
            nonce = request.args.get('nonce', '')
            echostr = request.args.get('echostr', '')
            msg_signature = request.args.get('msg_signature', '')

            if msg_signature is None:
                await self.logger.error('msg_signature不在请求体中')
                raise Exception('msg_signature不在请求体中')

            if request.method == 'GET':
                check_str = ''.join(sorted([self.token, timestamp, nonce]))
                check_signature = hashlib.sha1(check_str.encode('utf-8')).hexdigest()
                return echostr if check_signature == signature else '拒绝请求'

            elif request.method == 'POST':
                encryt_msg = await request.data
                wxcpt = WXBizMsgCrypt(self.token, self.aes, self.appid)
                ret, xml_msg = wxcpt.DecryptMsg(encryt_msg, msg_signature, timestamp, nonce)
                xml_msg = xml_msg.decode('utf-8')

                if ret != 0:
                    await self.logger.error('消息解密失败')
                    raise Exception('消息解密失败')

                # 解析 XML
                root = ET.fromstring(xml_msg)
                from_user = root.find('FromUserName').text
                to_user = root.find('ToUserName').text

                if self.msg_queue.get(from_user) and self.msg_queue[from_user][0]['content']:
                    queue_top = self.msg_queue[from_user].pop(0)
                    queue_content = queue_top['content']

                    # 弹出用户消息
                    if self.user_msg_queue.get(from_user) and self.user_msg_queue[from_user]:
                        self.user_msg_queue[from_user].pop(0)

                    response_xml = xml_template.format(
                        to_user=from_user,
                        from_user=to_user,
                        create_time=int(time.time()),
                        content=queue_content,
                    )
                    return response_xml

                else:
                    response_xml = xml_template.format(
                        to_user=from_user,
                        from_user=to_user,
                        create_time=int(time.time()),
                        content=self.loading_message,
                    )

                    if self.user_msg_queue.get(from_user) and self.user_msg_queue[from_user][0]['content']:
                        return response_xml
                    else:
                        message_data = await self.get_message(xml_msg)

                        if message_data:
                            event = OAEvent.from_payload(message_data)
                            if event:
                                self.user_msg_queue.setdefault(from_user, []).append(
                                    {
                                        'content': event.message,
                                    }
                                )
                                await self._handle_message(event)

                        return response_xml

        except Exception:
            await self.logger.error(f'handle_callback_request失败: {traceback.format_exc()}')
            traceback.print_exc()

    async def get_message(self, xml_msg: str):
        root = ET.fromstring(xml_msg)

        message_data = {
            'ToUserName': root.find('ToUserName').text,
            'FromUserName': root.find('FromUserName').text,
            'CreateTime': int(root.find('CreateTime').text),
            'MsgType': root.find('MsgType').text,
            'Content': root.find('Content').text if root.find('Content') is not None else None,
            'MsgId': int(root.find('MsgId').text) if root.find('MsgId') is not None else None,
        }

        return message_data

    async def run_task(self, host: str, port: int, *args, **kwargs):
        """
        启动 Quart 应用。
        """
        await self.app.run_task(host=host, port=port, *args, **kwargs)

    def on_message(self, msg_type: str):
        """
        注册消息类型处理器。
        """

        def decorator(func: Callable[[OAEvent], None]):
            if msg_type not in self._message_handlers:
                self._message_handlers[msg_type] = []
            self._message_handlers[msg_type].append(func)
            return func

        return decorator

    async def _handle_message(self, event: OAEvent):
        """
        处理消息事件。
        """

        msg_type = event.type
        if msg_type in self._message_handlers:
            for handler in self._message_handlers[msg_type]:
                await handler(event)

    async def set_message(self, from_user: int, message_id: int, content: str):
        if from_user not in self.msg_queue:
            self.msg_queue[from_user] = []

        self.msg_queue[from_user].append(
            {
                'msg_id': message_id,
                'content': content,
            }
        )
