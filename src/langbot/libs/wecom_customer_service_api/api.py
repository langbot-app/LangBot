from quart import request
from ..wecom_api.WXBizMsgCrypt3 import WXBizMsgCrypt
import asyncio
import base64
import binascii
import contextvars
import functools
import httpx
import json
import os
import traceback
from quart import Quart
import xml.etree.ElementTree as ET
from typing import Callable
from .wecomcsevent import WecomCSEvent
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import aiofiles
import time
from contextlib import asynccontextmanager
from langbot.pkg.utils import httpclient

_MAX_MEDIA_BYTES = 10 * 1024 * 1024
_MAX_CALLBACK_BODY_BYTES = 1024 * 1024


async def _read_httpx_media_limited(response: httpx.Response) -> bytes:
    content_length = response.headers.get('Content-Length')
    if content_length is not None:
        try:
            if int(content_length) > _MAX_MEDIA_BYTES:
                raise ValueError('WeCom customer-service media exceeds the size limit')
        except (TypeError, ValueError) as exc:
            if 'exceeds' in str(exc):
                raise
    content = bytearray()
    async for chunk in response.aiter_bytes():
        content.extend(chunk)
        if len(content) > _MAX_MEDIA_BYTES:
            raise ValueError('WeCom customer-service media exceeds the size limit')
    return bytes(content)


async def _read_local_media_limited(path: str) -> bytes:
    if await asyncio.to_thread(os.path.getsize, path) > _MAX_MEDIA_BYTES:
        raise ValueError('WeCom customer-service media exceeds the size limit')
    async with aiofiles.open(path, 'rb') as file:
        content = await file.read(_MAX_MEDIA_BYTES + 1)
    if len(content) > _MAX_MEDIA_BYTES:
        raise ValueError('WeCom customer-service media exceeds the size limit')
    return content


async def _decode_media_base64_limited(value: str) -> bytes:
    max_encoded_chars = 4 * ((_MAX_MEDIA_BYTES + 2) // 3) + 4
    if len(value) > max_encoded_chars:
        raise ValueError('WeCom customer-service media exceeds the size limit')
    content = await asyncio.to_thread(base64.b64decode, value)
    if len(content) > _MAX_MEDIA_BYTES:
        raise ValueError('WeCom customer-service media exceeds the size limit')
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


class WecomCSClient:
    _CUSTOMER_CACHE_MAX = 4096

    def __init__(
        self,
        corpid: str,
        secret: str,
        token: str,
        EncodingAESKey: str,
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
        self.logger = logger
        self.unified_mode = unified_mode
        self.app = Quart(__name__)
        self.app.config['MAX_CONTENT_LENGTH'] = _MAX_CALLBACK_BODY_BYTES

        # Customer info cache: {external_userid: (info_dict, timestamp)}
        self._customer_cache: dict[str, tuple[dict, float]] = {}
        self._cache_ttl = 60  # Cache TTL in seconds (1 minute)
        self._customer_cache_cleanup_at = 0.0

        # 只有在非统一模式下才注册独立路由
        if not self.unified_mode:
            self.app.add_url_rule(
                '/callback/command', 'handle_callback', self.handle_callback_request, methods=['GET', 'POST']
            )

        self._message_handlers = {
            'example': [],
        }
        self._http_client: httpx.AsyncClient | None = None

    @asynccontextmanager
    async def _http_client_context(self):
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(event_hooks=httpclient.httpx_response_limit_hooks())
        yield self._http_client

    async def close(self) -> None:
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    @_bounded_token_retry
    async def get_pic_url(self, media_id: str):
        if not await self.check_access_token():
            self.access_token = await self.get_access_token(self.secret)

        url = f'{self.base_url}/media/get?access_token={self.access_token}&media_id={media_id}'

        async with self._http_client_context() as client:
            async with client.stream('GET', url) as response:
                image_bytes = await _read_httpx_media_limited(response)
                content_type = response.headers.get('Content-Type', '')
                if content_type.startswith('application/json'):
                    data = json.loads(image_bytes)
                    if data.get('errcode') in [40014, 42001]:
                        self.access_token = await self.get_access_token(self.secret)
                        return await self.get_pic_url(media_id)
                    raise Exception('Failed to get image: ' + str(data))

                # 否则是图片，转成 base64
                base64_str = (await asyncio.to_thread(base64.b64encode, image_bytes)).decode('utf-8')
                return f'data:{content_type};base64,{base64_str}'

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
                raise Exception(f'未获取access token: {data}')

    @_bounded_token_retry
    async def get_detailed_message_list(self, xml_msg: str):
        # 在本方法中解析消息，并且获得消息的具体内容
        if isinstance(xml_msg, bytes):
            xml_msg = xml_msg.decode('utf-8')
        root = await asyncio.to_thread(ET.fromstring, xml_msg)
        token = root.find('Token').text
        open_kfid = root.find('OpenKfId').text

        # if open_kfid in self.openkfid_list:
        #     return None
        # else:
        #     self.openkfid_list.append(open_kfid)

        if not await self.check_access_token():
            self.access_token = await self.get_access_token(self.secret)

        url = self.base_url + '/kf/sync_msg?access_token=' + self.access_token
        async with self._http_client_context() as client:
            params = {
                'token': token,
                'voice_format': 0,
                'open_kfid': open_kfid,
            }
            response = await client.post(url, json=params)
            data = await httpclient.parse_json_response(response)
            if data['errcode'] == 40014 or data['errcode'] == 42001:
                self.access_token = await self.get_access_token(self.secret)
                return await self.get_detailed_message_list(xml_msg)
            if data['errcode'] != 0:
                raise Exception('Failed to get message')

            last_msg_data = data['msg_list'][-1]
            open_kfid = last_msg_data.get('open_kfid')
            # 进行获取图片操作
            if last_msg_data.get('msgtype') == 'image':
                media_id = last_msg_data.get('image').get('media_id')
                picurl = await self.get_pic_url(media_id)
                last_msg_data['picurl'] = picurl
            # await self.change_service_status(userid=external_userid,openkfid=open_kfid,servicer=servicer)
            return last_msg_data

    @_bounded_token_retry
    async def change_service_status(self, userid: str, openkfid: str, servicer: str):
        if not await self.check_access_token():
            self.access_token = await self.get_access_token(self.secret)
        url = self.base_url + '/kf/service_state/get?access_token=' + self.access_token
        async with self._http_client_context() as client:
            params = {
                'open_kfid': openkfid,
                'external_userid': userid,
                'service_state': 1,
                'servicer_userid': servicer,
            }
            response = await client.post(url, json=params)
            data = await httpclient.parse_json_response(response)
            if data['errcode'] == 40014 or data['errcode'] == 42001:
                self.access_token = await self.get_access_token(self.secret)
                return await self.change_service_status(userid, openkfid, servicer)
            if data['errcode'] != 0:
                raise Exception('Failed to change service status: ' + str(data))

    @_bounded_token_retry
    async def send_image(self, user_id: str, agent_id: int, media_id: str):
        if not await self.check_access_token():
            self.access_token = await self.get_access_token(self.secret)
        url = self.base_url + '/media/upload?access_token=' + self.access_token
        async with self._http_client_context() as client:
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
                data = await httpclient.parse_json_response(response)
            except Exception as e:
                raise Exception('Failed to send image: ' + str(e))

            # 企业微信错误码40014和42001，代表accesstoken问题
            if data['errcode'] == 40014 or data['errcode'] == 42001:
                self.access_token = await self.get_access_token(self.secret)
                return await self.send_image(user_id, agent_id, media_id)

            if data['errcode'] != 0:
                raise Exception('Failed to send image: ' + str(data))

    @_bounded_token_retry
    async def send_text_msg(self, open_kfid: str, external_userid: str, msgid: str, content: str):
        if not await self.check_access_token():
            self.access_token = await self.get_access_token(self.secret)

        url = f'{self.base_url}/kf/send_msg?access_token={self.access_token}'

        payload = {
            'touser': external_userid,
            'open_kfid': open_kfid,
            'msgid': msgid,
            'msgtype': 'text',
            'text': {
                'content': content,
            },
        }

        async with self._http_client_context() as client:
            response = await client.post(url, json=payload)

            data = await httpclient.parse_json_response(response)
            if data['errcode'] == 40014 or data['errcode'] == 42001:
                self.access_token = await self.get_access_token(self.secret)
                return await self.send_text_msg(open_kfid, external_userid, msgid, content)
            if data['errcode'] != 0:
                await self.logger.error(f'发送消息失败：{data}')
                raise Exception('Failed to send message')
            return data

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
            try:
                wxcpt = WXBizMsgCrypt(self.token, self.aes, self.corpid)
            except Exception as e:
                raise Exception(f'初始化失败，错误码: {e}')

            if req.method == 'GET':
                echostr = req.args.get('echostr')
                ret, reply_echo_str = wxcpt.VerifyURL(msg_signature, timestamp, nonce, echostr)
                if ret != 0:
                    raise Exception(f'验证失败，错误码: {ret}')
                return reply_echo_str

            elif req.method == 'POST':
                encrypt_msg = await req.data
                if len(encrypt_msg) > _MAX_CALLBACK_BODY_BYTES:
                    raise ValueError('WeCom customer-service callback body exceeds the size limit')
                ret, xml_msg = await asyncio.to_thread(
                    wxcpt.DecryptMsg,
                    encrypt_msg,
                    msg_signature,
                    timestamp,
                    nonce,
                )
                if ret != 0:
                    raise Exception(f'消息解密失败，错误码: {ret}')

                # 解析消息并处理
                message_data = await self.get_detailed_message_list(xml_msg)
                if message_data is not None:
                    event = WecomCSEvent.from_payload(message_data)
                    if event:
                        await self._handle_message(event)

                return 'success'
        except Exception as e:
            if self.logger:
                await self.logger.error(f'Error in handle_callback_request: {traceback.format_exc()}')
            else:
                traceback.print_exc()
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

        def decorator(func: Callable[[WecomCSEvent], None]):
            if msg_type not in self._message_handlers:
                self._message_handlers[msg_type] = []
            self._message_handlers[msg_type].append(func)
            return func

        return decorator

    async def _handle_message(self, event: WecomCSEvent):
        """
        处理消息事件。
        """
        msg_type = event.type
        if msg_type in self._message_handlers:
            for handler in self._message_handlers[msg_type]:
                await handler(event)

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
            file_bytes = await _read_local_media_limited(image.path)
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
                file_bytes = await _decode_media_base64_limited(padded_base64)
            except binascii.Error as e:
                raise ValueError(f'Invalid base64 string: {str(e)}')
        else:
            raise ValueError('image对象出错')

        # 设置 multipart/form-data 格式的文件
        if len(file_bytes) > _MAX_MEDIA_BYTES:
            raise ValueError('WeCom customer-service media exceeds the size limit')
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
                media_id = await self.upload_to_work(image)
            if data.get('errcode', 0) != 0:
                raise Exception('failed to upload file')

            media_id = data.get('media_id')
            return media_id

    async def download_image_to_bytes(self, url: str) -> bytes:
        async with self._http_client_context() as client:
            async with client.stream('GET', url) as response:
                response.raise_for_status()
                return await _read_httpx_media_limited(response)

    # 进行media_id的获取
    async def get_media_id(self, image: platform_message.Image):
        media_id = await self.upload_to_work(image=image)
        return media_id

    @_bounded_token_retry
    async def get_customer_info(self, external_userid: str) -> dict | None:
        """
        Get customer information by external_userid with caching.

        Uses a 1-minute cache to avoid repeated API calls for the same user.

        Args:
            external_userid: The external user ID of the customer.

        Returns:
            Customer info dict with 'nickname', 'avatar', etc., or None if not found.
        """
        # Check cache first
        current_time = time.time()
        if current_time - self._customer_cache_cleanup_at >= 30:
            self._customer_cache_cleanup_at = current_time
            for user_id, (_, cached_time) in tuple(self._customer_cache.items()):
                if current_time - cached_time >= self._cache_ttl:
                    self._customer_cache.pop(user_id, None)
        if external_userid in self._customer_cache:
            cached_info, cached_time = self._customer_cache[external_userid]
            if current_time - cached_time < self._cache_ttl:
                return cached_info

        # Cache miss or expired, fetch from API
        if not await self.check_access_token():
            self.access_token = await self.get_access_token(self.secret)

        url = f'{self.base_url}/kf/customer/batchget?access_token={self.access_token}'

        payload = {
            'external_userid_list': [external_userid],
        }

        async with self._http_client_context() as client:
            response = await client.post(url, json=payload)
            data = await httpclient.parse_json_response(response)

            if data.get('errcode') in [40014, 42001]:
                self.access_token = await self.get_access_token(self.secret)
                return await self.get_customer_info(external_userid)

            if data.get('errcode', 0) != 0:
                if self.logger:
                    await self.logger.warning(f'Failed to get customer info: {data}')
                return None

            customer_list = data.get('customer_list', [])
            if customer_list:
                customer_info = customer_list[0]
                # Store in cache
                self._customer_cache[external_userid] = (customer_info, current_time)
                while len(self._customer_cache) > self._CUSTOMER_CACHE_MAX:
                    self._customer_cache.pop(next(iter(self._customer_cache)), None)
                return customer_info
            return None

    def clear(self) -> None:
        self._customer_cache.clear()
