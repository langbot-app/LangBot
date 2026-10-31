from quart import request
from .WXBizMsgCrypt3 import WXBizMsgCrypt
import asyncio
import base64
import binascii
import contextvars
import functools
import httpx
import os
import traceback
from urllib.parse import quote
from quart import Quart
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from typing import Callable, Dict, Any
from .wecomevent import WecomEvent
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import aiofiles
from langbot.pkg.utils import httpclient

_MAX_MEDIA_BYTES = 10 * 1024 * 1024
_MAX_CALLBACK_BODY_BYTES = 1024 * 1024
_EXTENDED_HTTP_TIMEOUT_SECONDS = 120


async def _read_httpx_media_limited(response: httpx.Response) -> bytes:
    content_length = response.headers.get('Content-Length')
    if content_length is not None:
        try:
            if int(content_length) > _MAX_MEDIA_BYTES:
                raise ValueError('WeCom media exceeds the size limit')
        except (TypeError, ValueError) as exc:
            if 'exceeds' in str(exc):
                raise
    content = bytearray()
    async for chunk in response.aiter_bytes():
        content.extend(chunk)
        if len(content) > _MAX_MEDIA_BYTES:
            raise ValueError('WeCom media exceeds the size limit')
    return bytes(content)


async def _read_local_media_limited(path: str) -> bytes:
    if await asyncio.to_thread(os.path.getsize, path) > _MAX_MEDIA_BYTES:
        raise ValueError('WeCom media exceeds the size limit')
    async with aiofiles.open(path, 'rb') as file:
        content = await file.read(_MAX_MEDIA_BYTES + 1)
    if len(content) > _MAX_MEDIA_BYTES:
        raise ValueError('WeCom media exceeds the size limit')
    return content


async def _decode_media_base64_limited(value: str) -> bytes:
    max_encoded_chars = 4 * ((_MAX_MEDIA_BYTES + 2) // 3) + 4
    if len(value) > max_encoded_chars:
        raise ValueError('WeCom media exceeds the size limit')
    content = await asyncio.to_thread(base64.b64decode, value)
    if len(content) > _MAX_MEDIA_BYTES:
        raise ValueError('WeCom media exceeds the size limit')
    return content


def _bounded_token_retry(method):
    """Allow one token-refresh retry without unbounded async recursion."""

    depth = contextvars.ContextVar(f'{method.__name__}_token_retry_depth', default=0)

    @functools.wraps(method)
    async def wrapped(*args, **kwargs):
        current_depth = depth.get()
        if current_depth >= 2:
            raise RuntimeError(f'{method.__name__} exceeded the token refresh retry limit')
        token = depth.set(current_depth + 1)
        try:
            return await method(*args, **kwargs)
        finally:
            depth.reset(token)

    return wrapped


class WecomClient:
    def __init__(
        self,
        corpid: str,
        secret: str,
        token: str,
        EncodingAESKey: str,
        contacts_secret: str,
        logger: None,
        unified_mode: bool = False,
        api_base_url: str = 'https://qyapi.weixin.qq.com/cgi-bin',
    ):
        self.corpid = corpid
        self.secret = secret
        self.access_token_for_contacts = ''
        self.token = token
        self.aes = EncodingAESKey
        self.base_url = api_base_url
        self.access_token = ''
        self.secret_for_contacts = contacts_secret
        self.logger = logger
        self.unified_mode = unified_mode
        self.app = Quart(__name__)
        self.app.config['MAX_CONTENT_LENGTH'] = _MAX_CALLBACK_BODY_BYTES

        # 只有在非统一模式下才注册独立路由
        if not self.unified_mode:
            self.app.add_url_rule(
                '/callback/command',
                'handle_callback',
                self.handle_callback_request,
                methods=['GET', 'POST'],
            )

        self._message_handlers = {
            'example': [],
        }
        self._http_clients: dict[bool, httpx.AsyncClient] = {}

    @asynccontextmanager
    async def _http_client_context(self, *, unbounded_timeout: bool = False):
        client = self._http_clients.get(unbounded_timeout)
        if client is None or client.is_closed:
            response_hooks = httpclient.httpx_response_limit_hooks()
            client = (
                httpx.AsyncClient(
                    timeout=_EXTENDED_HTTP_TIMEOUT_SECONDS,
                    event_hooks=response_hooks,
                )
                if unbounded_timeout
                else httpx.AsyncClient(event_hooks=response_hooks)
            )
            self._http_clients[unbounded_timeout] = client
        yield client

    async def close(self) -> None:
        clients = list(self._http_clients.values())
        self._http_clients.clear()
        if clients:
            await asyncio.gather(*(client.aclose() for client in clients), return_exceptions=True)

    # access——token操作
    async def check_access_token(self):
        return bool(self.access_token and self.access_token.strip())

    async def check_access_token_for_contacts(self):
        return bool(self.access_token_for_contacts and self.access_token_for_contacts.strip())

    async def get_access_token(self, secret):
        url = f'{self.base_url}/gettoken?corpid={self.corpid}&corpsecret={secret}'
        async with self._http_client_context() as client:
            response = await client.get(url)
            data = await httpclient.parse_json_response(response)
            if 'access_token' in data:
                return data['access_token']
            else:
                await self.logger.error(f'获取accesstoken失败:{data}')
                raise Exception(f'未获取access token: {data}')

    @_bounded_token_retry
    async def get_user_info(self, userid: str) -> dict:
        """
        Get user information by user ID using the application secret.

        Args:
            userid: The user ID to look up.

        Returns:
            dict: User information including 'name' field.
        """
        if not await self.check_access_token():
            self.access_token = await self.get_access_token(self.secret)

        url = self.base_url + '/user/get?access_token=' + self.access_token + '&userid=' + quote(userid)
        async with self._http_client_context() as client:
            response = await client.get(url)
            data = await httpclient.parse_json_response(response)
            if data.get('errcode') == 40014 or data.get('errcode') == 42001:
                self.access_token = await self.get_access_token(self.secret)
                return await self.get_user_info(userid)
            if data.get('errcode', 0) != 0:
                await self.logger.error(f'获取用户信息失败:{data}')
                return {}
            return data

    async def get_users(self):
        if not self.check_access_token_for_contacts():
            self.access_token_for_contacts = await self.get_access_token(self.secret_for_contacts)

        url = self.base_url + '/user/list_id?access_token=' + self.access_token_for_contacts
        async with self._http_client_context() as client:
            params = {
                'cursor': '',
                'limit': 10000,
            }
            response = await client.post(url, json=params)
            data = await httpclient.parse_json_response(response)
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
            async with self._http_client_context() as client:
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
                data = await httpclient.parse_json_response(response)
                if data['errcode'] != 0:
                    raise Exception('Failed to send message: ' + str(data))

    @_bounded_token_retry
    async def send_image(self, user_id: str, agent_id: int, media_id: str):
        if not await self.check_access_token():
            self.access_token = await self.get_access_token(self.secret)

        url = self.base_url + '/message/send?access_token=' + self.access_token
        async with self._http_client_context() as client:
            params = {
                'touser': user_id,
                'msgtype': 'image',
                'agentid': agent_id,
                'image': {
                    'media_id': media_id,
                },
                'safe': 0,
                'enable_id_trans': 0,
                'enable_duplicate_check': 0,
                'duplicate_check_interval': 1800,
            }
            response = await client.post(url, json=params)
            data = await httpclient.parse_json_response(response)
            if data['errcode'] == 40014 or data['errcode'] == 42001:
                self.access_token = await self.get_access_token(self.secret)
                return await self.send_image(user_id, agent_id, media_id)
            if data['errcode'] != 0:
                await self.logger.error(f'发送图片失败:{data}')
                raise Exception('Failed to send image: ' + str(data))

    @_bounded_token_retry
    async def send_voice(self, user_id: str, agent_id: int, media_id: str):
        if not await self.check_access_token():
            self.access_token = await self.get_access_token(self.secret)
        url = self.base_url + '/message/send?access_token=' + self.access_token
        async with self._http_client_context() as client:
            params = {
                'touser': user_id,
                'msgtype': 'voice',
                'agentid': agent_id,
                'voice': {
                    'media_id': media_id,
                },
                'safe': 0,
                'enable_id_trans': 0,
                'enable_duplicate_check': 0,
                'duplicate_check_interval': 1800,
            }
            response = await client.post(url, json=params)
            data = await httpclient.parse_json_response(response)
            if data['errcode'] == 40014 or data['errcode'] == 42001:
                self.access_token = await self.get_access_token(self.secret)
                return await self.send_voice(user_id, agent_id, media_id)
            if data['errcode'] != 0:
                await self.logger.error(f'发送语音失败:{data}')
                raise Exception('Failed to send voice: ' + str(data))

    @_bounded_token_retry
    async def send_file(self, user_id: str, agent_id: int, media_id: str):
        if not await self.check_access_token():
            self.access_token = await self.get_access_token(self.secret)
        url = self.base_url + '/message/send?access_token=' + self.access_token
        async with self._http_client_context() as client:
            params = {
                'touser': user_id,
                'msgtype': 'file',
                'agentid': agent_id,
                'file': {
                    'media_id': media_id,
                },
                'safe': 0,
                'enable_id_trans': 0,
                'enable_duplicate_check': 0,
                'duplicate_check_interval': 1800,
            }
            response = await client.post(url, json=params)
            data = await httpclient.parse_json_response(response)
            if data['errcode'] == 40014 or data['errcode'] == 42001:
                self.access_token = await self.get_access_token(self.secret)
                return await self.send_file(user_id, agent_id, media_id)
            if data['errcode'] != 0:
                await self.logger.error(f'发送文件失败:{data}')
                raise Exception('Failed to send file: ' + str(data))

    @_bounded_token_retry
    async def send_private_msg(self, user_id: str, agent_id: int, content: str):
        if not await self.check_access_token():
            self.access_token = await self.get_access_token(self.secret)

        url = self.base_url + '/message/send?access_token=' + self.access_token
        async with self._http_client_context(unbounded_timeout=True) as client:
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
            data = await httpclient.parse_json_response(response)
            if data['errcode'] == 40014 or data['errcode'] == 42001:
                self.access_token = await self.get_access_token(self.secret)
                return await self.send_private_msg(user_id, agent_id, content)
            if data['errcode'] != 0:
                await self.logger.error(f'发送消息失败:{data}')
                raise Exception('Failed to send message: ' + str(data))

    async def handle_callback_request(self):
        """处理回调请求（独立端口模式，使用全局 request）。"""
        return await self._handle_callback_internal(request)

    async def handle_unified_webhook(self, req):
        """处理回调请求（统一 webhook 模式，显式传递 request）。

        Args:
            req: Quart Request 对象

        Returns:
            响应数据
        """
        return await self._handle_callback_internal(req)

    async def _handle_callback_internal(self, req):
        """
        处理回调请求的内部实现，包括 GET 验证和 POST 消息接收。

        Args:
            req: Quart Request 对象
        """
        try:
            msg_signature = req.args.get('msg_signature')
            timestamp = req.args.get('timestamp')
            nonce = req.args.get('nonce')

            wxcpt = WXBizMsgCrypt(self.token, self.aes, self.corpid)
            if req.method == 'GET':
                echostr = req.args.get('echostr')
                ret, reply_echo_str = wxcpt.VerifyURL(msg_signature, timestamp, nonce, echostr)
                if ret != 0:
                    await self.logger.error('验证失败')
                    raise Exception(f'验证失败，错误码: {ret}')
                return reply_echo_str

            elif req.method == 'POST':
                encrypt_msg = await req.data
                if len(encrypt_msg) > _MAX_CALLBACK_BODY_BYTES:
                    raise ValueError('WeCom callback body exceeds the size limit')
                ret, xml_msg = await asyncio.to_thread(
                    wxcpt.DecryptMsg,
                    encrypt_msg,
                    msg_signature,
                    timestamp,
                    nonce,
                )
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
        root = await asyncio.to_thread(ET.fromstring, xml_msg)
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

    @_bounded_token_retry
    async def upload_image_to_work(self, image: platform_message.Image):
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
            file_bytes = await _read_local_media_limited(image.path)
            file_name = image.path.split('/')[-1]
        elif image.url:
            file_bytes = await self.download_media_to_bytes(image.url)
            file_name = image.url.split('/')[-1]
        elif image.base64:
            try:
                base64_data = image.base64
                if ',' in base64_data:
                    base64_data = base64_data.split(',', 1)[1]
                padding = 4 - (len(base64_data) % 4) if len(base64_data) % 4 else 0
                padded_base64 = base64_data + '=' * padding
                file_bytes = await _decode_media_base64_limited(padded_base64)
            except binascii.Error as e:
                raise ValueError(f'Invalid base64 string: {str(e)}')
        else:
            await self.logger.error('Image对象出错')
            raise ValueError('image对象出错')

        # 设置 multipart/form-data 格式的文件
        if len(file_bytes) > _MAX_MEDIA_BYTES:
            raise ValueError('WeCom media exceeds the size limit')
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
        async with self._http_client_context() as client:
            response = await client.post(url, headers=headers, content=body)
            data = await httpclient.parse_json_response(response)
            if data['errcode'] == 40014 or data['errcode'] == 42001:
                self.access_token = await self.get_access_token(self.secret)
                media_id = await self.upload_image_to_work(image)
            if data.get('errcode', 0) != 0:
                await self.logger.error(f'上传图片失败:{data}')
                raise Exception('failed to upload file')

            media_id = data.get('media_id')
            return media_id

    @_bounded_token_retry
    async def upload_voice_to_work(self, voice: platform_message.Voice):
        """
        上传语音文件到企业微信
        """
        if not await self.check_access_token():
            self.access_token = await self.get_access_token(self.secret)
        url = self.base_url + '/media/upload?access_token=' + self.access_token + '&type=file'
        file_bytes = None
        file_name = 'voice.mp3'

        if voice.path:
            file_bytes = await _read_local_media_limited(voice.path)
            file_name = voice.path.split('/')[-1]
        elif voice.url:
            file_bytes = await self.download_media_to_bytes(voice.url)
            file_name = voice.url.split('/')[-1]
        elif voice.base64:
            try:
                base64_data = voice.base64
                if ',' in base64_data:
                    base64_data = base64_data.split(',', 1)[1]
                padding = 4 - (len(base64_data) % 4) if len(base64_data) % 4 else 0
                padded_base64 = base64_data + '=' * padding
                file_bytes = await _decode_media_base64_limited(padded_base64)
            except binascii.Error as e:
                raise ValueError(f'Invalid base64 string: {str(e)}')
        else:
            await self.logger.error('Voice对象出错')
            raise ValueError('voice对象出错')

        if len(file_bytes) > _MAX_MEDIA_BYTES:
            raise ValueError('WeCom media exceeds the size limit')
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

        # print(body)
        async with self._http_client_context() as client:
            response = await client.post(url, headers=headers, content=body)
            data = await httpclient.parse_json_response(response)
            if data['errcode'] == 40014 or data['errcode'] == 42001:
                self.access_token = await self.get_access_token(self.secret)
                media_id = await self.upload_voice_to_work(voice)
            if data.get('errcode', 0) != 0:
                await self.logger.error(f'上传语音文件失败:{data}')
                raise Exception('failed to upload file')
            media_id = data.get('media_id')
            return media_id

    @_bounded_token_retry
    async def upload_file_to_work(self, file: platform_message.File):
        """
        上传文件到企业微信
        """
        if not await self.check_access_token():
            self.access_token = await self.get_access_token(self.secret)
        url = self.base_url + '/media/upload?access_token=' + self.access_token + '&type=file'
        file_bytes = None
        file_name = 'file.txt'
        if file.path:
            file_bytes = await _read_local_media_limited(file.path)
            file_name = file.path.split('/')[-1]
        elif file.url:
            file_bytes = await self.download_media_to_bytes(file.url)
            file_name = file.url.split('/')[-1]
        elif file.base64:
            try:
                base64_data = file.base64
                if ',' in base64_data:
                    base64_data = base64_data.split(',', 1)[1]
                padding = 4 - (len(base64_data) % 4) if len(base64_data) % 4 else 0
                padded_base64 = base64_data + '=' * padding
                file_bytes = await _decode_media_base64_limited(padded_base64)
            except binascii.Error as e:
                raise ValueError(f'Invalid base64 string: {str(e)}')
        else:
            await self.logger.error('File对象出错')
            raise ValueError('file对象出错')
        if len(file_bytes) > _MAX_MEDIA_BYTES:
            raise ValueError('WeCom media exceeds the size limit')
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
        async with self._http_client_context() as client:
            response = await client.post(url, headers=headers, content=body)
            data = await httpclient.parse_json_response(response)
            if data['errcode'] == 40014 or data['errcode'] == 42001:
                self.access_token = await self.get_access_token(self.secret)
                media_id = await self.upload_file_to_work(file)
            if data.get('errcode', 0) != 0:
                await self.logger.error(f'上传文件失败:{data}')
                raise Exception('failed to upload file')
            media_id = data.get('media_id')
            return media_id

    async def download_media_to_bytes(self, url: str) -> bytes:
        async with self._http_client_context() as client:
            async with client.stream('GET', url) as response:
                response.raise_for_status()
                return await _read_httpx_media_limited(response)

    # 进行media_id的获取
    async def get_media_id(self, media: platform_message.Image | platform_message.Voice | platform_message.File):
        if isinstance(media, platform_message.Image):
            media_id = await self.upload_image_to_work(image=media)
        elif isinstance(media, platform_message.Voice):
            media_id = await self.upload_voice_to_work(voice=media)
        elif isinstance(media, platform_message.File):
            media_id = await self.upload_file_to_work(file=media)
        else:
            raise ValueError('Unsupported media type')
        return media_id
