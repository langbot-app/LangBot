from quart import request
from .WXBizMsgCrypt3 import WXBizMsgCrypt
import base64
import binascii
import httpx
import traceback
from quart import Quart
import xml.etree.ElementTree as ET
from typing import Callable, Dict, Any
from .wecomevent import WecomEvent
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import aiofiles


class WecomClient:
    def __init__(
        self,
        corpid: str,
        secret: str,
        token: str,
        EncodingAESKey: str,
        contacts_secret: str,
        logger: None,
    ):
        self.corpid = corpid
        self.secret = secret
        self.access_token_for_contacts = ''
        self.token = token
        self.aes = EncodingAESKey
        self.base_url = 'https://qyapi.weixin.qq.com/cgi-bin'
        self.access_token = ''
        self.secret_for_contacts = contacts_secret
        self.logger = logger
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

    # access——token操作
    async def check_access_token(self):
        return bool(self.access_token and self.access_token.strip())

    async def check_access_token_for_contacts(self):
        return bool(self.access_token_for_contacts and self.access_token_for_contacts.strip())

    async def get_access_token(self, secret):
        url = f'https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self.corpid}&corpsecret={secret}'
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()
            if 'access_token' in data:
                return data['access_token']
            else:
                await self.logger.error(f'获取accesstoken失败:{response.json()}')
                raise Exception(f'未获取access token: {data}')

    async def get_users(self):
        if not self.check_access_token_for_contacts():
            self.access_token_for_contacts = await self.get_access_token(self.secret_for_contacts)

        url = self.base_url + '/user/list_id?access_token=' + self.access_token_for_contacts
        async with httpx.AsyncClient() as client:
            params = {
                'cursor': '',
                'limit': 10000,
            }
            response = await client.post(url, json=params)
            data = response.json()
            if data['errcode'] == 0:
                dept_users = data['dept_user']
                userid = []
                for user in dept_users:
                    userid.append(user['userid'])
                return userid
            else:
                raise Exception('未获取用户')

    async def send_to_all(self, content: str, agent_id: int):
        if not self.check_access_token_for_contacts():
            self.access_token_for_contacts = await self.get_access_token(self.secret_for_contacts)

            url = self.base_url + '/message/send?access_token=' + self.access_token_for_contacts
            user_ids = await self.get_users()
            user_ids_string = '|'.join(user_ids)
            async with httpx.AsyncClient() as client:
                params = {
                    'touser': user_ids_string,
                    'msgtype': 'text',
                    'agentid': agent_id,
                    'text': {
                        'content': content,
                    },
                    'safe': 0,
                    'enable_id_trans': 0,
                    'enable_duplicate_check': 0,
                    'duplicate_check_interval': 1800,
                }
                response = await client.post(url, json=params)
                data = response.json()
                if data['errcode'] != 0:
                    raise Exception('Failed to send message: ' + str(data))

    async def send_image(self, user_id: str, agent_id: int, media_id: str):
        if not await self.check_access_token():
            self.access_token = await self.get_access_token(self.secret)
        url = self.base_url + '/media/upload?access_token=' + self.access_token
        async with httpx.AsyncClient() as client:
            params = {
                'touser': user_id,
                'toparty': '',
                'totag': '',
                'agentid': agent_id,
                'msgtype': 'image',
                'image': {
                    'media_id': media_id,
                },
                'safe': 0,
                'enable_id_trans': 0,
                'enable_duplicate_check': 0,
                'duplicate_check_interval': 1800,
            }
            try:
                response = await client.post(url, json=params)
                data = response.json()
            except Exception as e:
                await self.logger.error(f'发送图片失败:{data}')
                raise Exception('Failed to send image: ' + str(e))

            # 企业微信错误码40014和42001，代表accesstoken问题
            if data['errcode'] == 40014 or data['errcode'] == 42001:
                self.access_token = await self.get_access_token(self.secret)
                return await self.send_image(user_id, agent_id, media_id)

            if data['errcode'] != 0:
                raise Exception('Failed to send image: ' + str(data))

    async def send_private_msg(self, user_id: str, agent_id: int, content: str):
        if not await self.check_access_token():
            self.access_token = await self.get_access_token(self.secret)

        url = self.base_url + '/message/send?access_token=' + self.access_token
        async with httpx.AsyncClient() as client:
            params = {
                'touser': user_id,
                'msgtype': 'text',
                'agentid': agent_id,
                'text': {
                    'content': content,
                },
                'safe': 0,
                'enable_id_trans': 0,
                'enable_duplicate_check': 0,
                'duplicate_check_interval': 1800,
            }
            response = await client.post(url, json=params)
            data = response.json()
            if data['errcode'] == 40014 or data['errcode'] == 42001:
                self.access_token = await self.get_access_token(self.secret)
                return await self.send_private_msg(user_id, agent_id, content)
            if data['errcode'] != 0:
                await self.logger.error(f'发送消息失败:{data}')
                raise Exception('Failed to send message: ' + str(data))

    async def handle_callback_request(self):
        """
        处理回调请求，包括 GET 验证和 POST 消息接收。
        """
        try:
            msg_signature = request.args.get('msg_signature')
            timestamp = request.args.get('timestamp')
            nonce = request.args.get('nonce')

            wxcpt = WXBizMsgCrypt(self.token, self.aes, self.corpid)
            if request.method == 'GET':
                echostr = request.args.get('echostr')
                ret, reply_echo_str = wxcpt.VerifyURL(msg_signature, timestamp, nonce, echostr)
                if ret != 0:
                    await self.logger.error('验证失败')
                    raise Exception(f'验证失败，错误码: {ret}')
                return reply_echo_str

            elif request.method == 'POST':
                encrypt_msg = await request.data
                ret, xml_msg = wxcpt.DecryptMsg(encrypt_msg, msg_signature, timestamp, nonce)
                if ret != 0:
                    await self.logger.error('消息解密失败')
                    raise Exception(f'消息解密失败，错误码: {ret}')

                # 解析消息并处理
                message_data = await self.get_message(xml_msg)
                if message_data:
                    event = WecomEvent.from_payload(message_data)  # 转换为 WecomEvent 对象
                    if event:
                        await self._handle_message(event)

                return 'success'
        except Exception as e:
            await self.logger.error(f'Error in handle_callback_request: {traceback.format_exc()}')
            return f'Error processing request: {str(e)}', 400

    async def run_task(self, host: str, port: int, *args, **kwargs):
        """
        启动 Quart 应用。
        """
        await self.app.run_task(host=host, port=port, *args, **kwargs)

    def on_message(self, msg_type: str):
        """
        注册消息类型处理器。
        """

        def decorator(func: Callable[[WecomEvent], None]):
            if msg_type not in self._message_handlers:
                self._message_handlers[msg_type] = []
            self._message_handlers[msg_type].append(func)
            return func

        return decorator

    async def _handle_message(self, event: WecomEvent):
        """
        处理消息事件。
        """
        msg_type = event.type
        if msg_type in self._message_handlers:
            for handler in self._message_handlers[msg_type]:
                await handler(event)

    async def get_message(self, xml_msg: str) -> Dict[str, Any]:
        """
        解析微信返回的 XML 消息并转换为字典。
        """
        root = ET.fromstring(xml_msg)
        message_data = {
            'ToUserName': root.find('ToUserName').text,
            'FromUserName': root.find('FromUserName').text,
            'CreateTime': int(root.find('CreateTime').text),
            'MsgType': root.find('MsgType').text,
            'Content': root.find('Content').text if root.find('Content') is not None else None,
            'MsgId': int(root.find('MsgId').text) if root.find('MsgId') is not None else None,
            'AgentID': int(root.find('AgentID').text) if root.find('AgentID') is not None else None,
        }
        if message_data['MsgType'] == 'image':
            message_data['MediaId'] = root.find('MediaId').text if root.find('MediaId') is not None else None
            message_data['PicUrl'] = root.find('PicUrl').text if root.find('PicUrl') is not None else None

        return message_data

    @staticmethod
    async def get_image_type(image_bytes: bytes) -> str:
        """
        通过图片的magic numbers判断图片类型
        """
        magic_numbers = {
            b'\xff\xd8\xff': 'jpg',
            b'\x89\x50\x4e\x47': 'png',
            b'\x47\x49\x46': 'gif',
            b'\x42\x4d': 'bmp',
            b'\x00\x00\x01\x00': 'ico',
        }

        for magic, ext in magic_numbers.items():
            if image_bytes.startswith(magic):
                return ext
        return 'jpg'  # 默认返回jpg

    async def upload_to_work(self, image: platform_message.Image):
        """
        获取 media_id
        """
        if not await self.check_access_token():
            self.access_token = await self.get_access_token(self.secret)

        url = self.base_url + '/media/upload?access_token=' + self.access_token + '&type=file'
        file_bytes = None
        file_name = 'uploaded_file.txt'

        # 获取文件的二进制数据
        if image.path:
            async with aiofiles.open(image.path, 'rb') as f:
                file_bytes = await f.read()
                file_name = image.path.split('/')[-1]
        elif image.url:
            file_bytes = await self.download_image_to_bytes(image.url)
            file_name = image.url.split('/')[-1]
        elif image.base64:
            try:
                base64_data = image.base64
                if ',' in base64_data:
                    base64_data = base64_data.split(',', 1)[1]
                padding = 4 - (len(base64_data) % 4) if len(base64_data) % 4 else 0
                padded_base64 = base64_data + '=' * padding
                file_bytes = base64.b64decode(padded_base64)
            except binascii.Error as e:
                raise ValueError(f'Invalid base64 string: {str(e)}')
        else:
            await self.logger.error('Image对象出错')
            raise ValueError('image对象出错')

        # 设置 multipart/form-data 格式的文件
        boundary = '-------------------------acebdf13572468'
        headers = {'Content-Type': f'multipart/form-data; boundary={boundary}'}
        body = (
            (
                f'--{boundary}\r\n'
                f'Content-Disposition: form-data; name="media"; filename="{file_name}"; filelength={len(file_bytes)}\r\n'
                f'Content-Type: application/octet-stream\r\n\r\n'
            ).encode('utf-8')
            + file_bytes
            + f'\r\n--{boundary}--\r\n'.encode('utf-8')
        )

        # 上传文件
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, content=body)
            data = response.json()
            if data['errcode'] == 40014 or data['errcode'] == 42001:
                self.access_token = await self.get_access_token(self.secret)
                media_id = await self.upload_to_work(image)
            if data.get('errcode', 0) != 0:
                await self.logger.error(f'上传图片失败:{data}')
                raise Exception('failed to upload file')

            media_id = data.get('media_id')
            return media_id

    async def download_image_to_bytes(self, url: str) -> bytes:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    # 进行media_id的获取
    async def get_media_id(self, image: platform_message.Image):
        media_id = await self.upload_to_work(image=image)
        return media_id
