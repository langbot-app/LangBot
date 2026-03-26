import asyncio
import hashlib
import logging
from quart import request
from ..wecom_api.WXBizMsgCrypt3 import WXBizMsgCrypt
import base64
import binascii
import httpx
import traceback
from quart import Quart
import xml.etree.ElementTree as ET
from typing import Callable
from .wecomcsevent import WecomCSEvent
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import aiofiles
import time
from ...pkg.platform.wecomcs.token_cache import WecomCSTokenCache
from ...pkg.platform.wecomcs.pull_trigger_publisher import WecomCSPullTriggerPublisher

_logger = logging.getLogger('langbot')


class WecomCSInvalidSyncMsgTokenError(Exception):
    """Raised when WeCom customer service sync_msg token is invalid or expired."""


class WecomCSClient:
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

        redis_mgr = getattr(getattr(logger, 'ap', None), 'redis_mgr', None) if logger else None
        scheduler_config = getattr(getattr(logger, 'ap', None), 'instance_config', None)
        refresh_skew_seconds = 300
        if scheduler_config is not None:
            refresh_skew_seconds = (
                scheduler_config.data.get('wecomcs_scheduler', {}).get('token_refresh_skew_seconds', 300)
            )
        secret_fingerprint = hashlib.sha256(secret.encode('utf-8')).hexdigest()[:16] if secret else ''
        self.token_cache = WecomCSTokenCache(
            corpid=corpid,
            redis_mgr=redis_mgr,
            refresh_skew_seconds=refresh_skew_seconds,
            secret_fingerprint=secret_fingerprint,
        )
        self.bot_uuid = ''
        self.state_store = None
        self.scheduler_enabled = False
        self.pull_trigger_publisher = None
        if scheduler_config is not None:
            scheduler_settings = scheduler_config.data.get('wecomcs_scheduler', {})
            self.scheduler_enabled = bool(scheduler_settings.get('enabled', False))
            pull_stream_shard_count = int(scheduler_settings.get('pull_stream_shard_count', 8) or 8)
            if self.scheduler_enabled and redis_mgr is not None and redis_mgr.is_available():
                self.pull_trigger_publisher = WecomCSPullTriggerPublisher(redis_mgr, pull_stream_shard_count)

        # 用于防止并发获取 access_token
        self._token_lock = asyncio.Lock()
        # 统一 webhook 下会快速返回 success，因此需要持有后台任务引用避免被提前回收
        self._background_tasks: set[asyncio.Task] = set()

        # Customer info cache: {external_userid: (info_dict, timestamp)}
        self._customer_cache: dict[str, tuple[dict, float]] = {}
        self._cache_ttl = 60  # Cache TTL in seconds (1 minute)

        # 只有在非统一模式下才注册独立路由
        if not self.unified_mode:
            self.app.add_url_rule(
                '/callback/command', 'handle_callback', self.handle_callback_request, methods=['GET', 'POST']
            )

        self._message_handlers = {
            'example': [],
        }

    async def get_pic_url(self, media_id: str):
        await self.ensure_access_token()

        url = f'{self.base_url}/media/get?access_token={self.access_token}&media_id={media_id}'

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            if response.headers.get('Content-Type', '').startswith('application/json'):
                data = response.json()
                if data.get('errcode') in [40014, 42001]:
                    await self.token_cache.invalidate()
                    self.access_token = ''
                    return await self.get_pic_url(media_id)
                else:
                    raise Exception('Failed to get image: ' + str(data))

            # 否则是图片，转成 base64
            image_bytes = response.content
            content_type = response.headers.get('Content-Type', '')
            base64_str = base64.b64encode(image_bytes).decode('utf-8')
            base64_str = f'data:{content_type};base64,{base64_str}'
            return base64_str

    # access——token操作
    async def check_access_token(self):
        cached_token = await self.token_cache.get_cached_token()
        if cached_token:
            self.access_token = cached_token
            return True
        return False

    async def check_access_token_for_contacts(self):
        return bool(self.access_token_for_contacts and self.access_token_for_contacts.strip())

    async def ensure_access_token(self):
        """确保 access_token 有效，使用锁防止并发获取。"""
        if await self.check_access_token():
            return self.access_token

        async with self._token_lock:
            # 中文注释：双重检查可以避免并发场景下重复请求企业微信 token 接口。
            if await self.check_access_token():
                return self.access_token

            _logger.debug('[wecomcs] access_token为空，正在获取...')
            self.access_token = await self.token_cache.get_or_refresh(self._fetch_main_access_token_data)
            return self.access_token

    async def refresh_access_token(self):
        """强制刷新主 access_token。"""
        async with self._token_lock:
            # 中文注释：收到 40014 / 42001 时必须绕过本地缓存，强制重新拉取 token。
            await self.token_cache.invalidate()
            self.access_token = await self.token_cache.get_or_refresh(self._fetch_main_access_token_data, force_refresh=True)
            return self.access_token

    async def _request_access_token(self, secret: str):
        """实际请求指定 secret 对应的 access_token 数据。"""
        url = f'{self.base_url}/gettoken?corpid={self.corpid}&corpsecret={secret}'
        _logger.debug(f'[wecomcs] 获取access_token: corpid={self.corpid[:10] if self.corpid else "N/A"}...')
        print(f'[wecomcs] 获取access_token: corpid={self.corpid[:10] if self.corpid else "N/A"}...', flush=True)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                _logger.debug(f'[wecomcs] 正在请求: {url}')
                print('[wecomcs] 正在请求 gettoken API...', flush=True)
                response = await client.get(url)
                print('[wecomcs] gettoken请求完成，正在解析响应...', flush=True)
                _logger.debug(f'[wecomcs] gettoken响应状态: {response.status_code}')
                print(f'[wecomcs] gettoken响应状态: {response.status_code}', flush=True)
                data = response.json()
                _logger.debug(f'[wecomcs] gettoken响应: errcode={data.get("errcode")}, errmsg={data.get("errmsg")}')
                print(f'[wecomcs] gettoken响应: errcode={data.get("errcode")}, errmsg={data.get("errmsg")}', flush=True)
                if 'access_token' in data:
                    return {
                        'access_token': data['access_token'],
                        'expires_in': int(data.get('expires_in', 7200) or 7200),
                    }

                _logger.error(f'[wecomcs] 未获取access token: {data}')
                raise Exception(f'未获取access token: {data}')
        except Exception as e:
            _logger.error(f'[wecomcs] get_access_token异常: {traceback.format_exc()}')
            print(f'[wecomcs] get_access_token异常: {e}', flush=True)
            raise

    async def _fetch_main_access_token_data(self):
        return await self._request_access_token(self.secret)

    async def get_access_token(self, secret):
        """兼容旧接口。"""
        if secret != self.secret:
            token_data = await self._request_access_token(secret)
            return token_data['access_token']
        return await self.ensure_access_token()

    async def fetch_sync_msg_page(self, callback_token: str, open_kfid: str, cursor: str | None = None):
        await self.ensure_access_token()

        url = self.base_url + '/kf/sync_msg?access_token=' + self.access_token
        params = {
            'token': callback_token,
            'voice_format': 0,
            'open_kfid': open_kfid,
        }
        if cursor:
            params['cursor'] = cursor

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=params)
            data = response.json()
            if data.get('errcode') in [40014, 42001]:
                await self.refresh_access_token()
                return await self.fetch_sync_msg_page(callback_token, open_kfid, cursor)
            if data.get('errcode') == 95007:
                _logger.error(f'[wecomcs] sync_msg失败: {data}')
                raise WecomCSInvalidSyncMsgTokenError(data.get('errmsg', 'invalid msg token'))
            if data.get('errcode') != 0:
                _logger.error(f'[wecomcs] sync_msg失败: {data}')
                raise Exception('Failed to get message')

            msg_list = data.get('msg_list') or []
            for msg_data in msg_list:
                if msg_data.get('msgtype') == 'image' and msg_data.get('image'):
                    media_id = msg_data['image'].get('media_id')
                    if media_id:
                        msg_data['picurl'] = await self.get_pic_url(media_id)

            return {
                'msg_list': msg_list,
                'next_cursor': data.get('next_cursor', ''),
                'has_more': bool(data.get('has_more', False)),
            }

    async def get_detailed_message_list(self, xml_msg: str):
        # 中文注释：企业微信一次回调可能携带多条消息，不能只取最后一条，否则会丢消息。
        try:
            if isinstance(xml_msg, bytes):
                xml_msg = xml_msg.decode('utf-8')
            root = ET.fromstring(xml_msg)
            callback_token = root.find('Token').text
            open_kfid = root.find('OpenKfId').text
            _logger.debug(f'[wecomcs] sync_msg参数: token={callback_token[:20] if callback_token else "N/A"}..., open_kfid={open_kfid}')

            page = await self.fetch_sync_msg_page(callback_token, open_kfid)
            msg_list = page.get('msg_list') or []
            if not msg_list:
                _logger.warning('[wecomcs] sync_msg返回空消息列表')
                return []
            return msg_list
        except Exception:
            _logger.error(f'[wecomcs] get_detailed_message_list异常: {traceback.format_exc()}')
            raise

    async def change_service_status(self, userid: str, openkfid: str, servicer: str):
        if not await self.check_access_token():
            await self.ensure_access_token()
        url = self.base_url + '/kf/service_state/get?access_token=' + self.access_token
        async with httpx.AsyncClient(timeout=10.0) as client:
            params = {
                'open_kfid': openkfid,
                'external_userid': userid,
                'service_state': 1,
                'servicer_userid': servicer,
            }
            response = await client.post(url, json=params)
            data = response.json()
            if data['errcode'] == 40014 or data['errcode'] == 42001:
                await self.refresh_access_token()
                return await self.change_service_status(userid, openkfid)
            if data['errcode'] != 0:
                raise Exception('Failed to change service status: ' + str(data))

    async def send_image(self, user_id: str, agent_id: int, media_id: str):
        if not await self.check_access_token():
            await self.ensure_access_token()
        url = self.base_url + '/media/upload?access_token=' + self.access_token
        async with httpx.AsyncClient(timeout=10.0) as client:
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
                raise Exception('Failed to send image: ' + str(e))

            # 企业微信错误码40014和42001，代表accesstoken问题
            if data['errcode'] == 40014 or data['errcode'] == 42001:
                await self.refresh_access_token()
                return await self.send_image(user_id, agent_id, media_id)

            if data['errcode'] != 0:
                raise Exception('Failed to send image: ' + str(data))

    async def send_text_msg(self, open_kfid: str, external_userid: str, msgid: str, content: str):
        if not await self.check_access_token():
            await self.ensure_access_token()

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

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)

            data = response.json()
            if data['errcode'] == 40014 or data['errcode'] == 42001:
                await self.refresh_access_token()
                return await self.send_text_msg(open_kfid, external_userid, msgid, content)
            if data['errcode'] != 0:
                await self.logger.error(
                    f"[wecomcs] 发送消息失败: errcode={data.get('errcode')}, errmsg={data.get('errmsg')}, open_kfid={open_kfid}, external_userid={external_userid}, msgid={msgid}"
                )
                raise Exception(f'Failed to send message: {data}')
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
            _logger.debug(f'[wecomcs] 收到回调请求: method={req.method}')

            msg_signature = req.args.get('msg_signature')
            timestamp = req.args.get('timestamp')
            nonce = req.args.get('nonce')
            try:
                wxcpt = WXBizMsgCrypt(self.token, self.aes, self.corpid)
            except Exception as e:
                _logger.error(f'[wecomcs] 加密组件初始化失败: {e}')
                raise Exception(f'初始化失败，错误码: {e}')

            if req.method == 'GET':
                echostr = req.args.get('echostr')
                ret, reply_echo_str = wxcpt.VerifyURL(msg_signature, timestamp, nonce, echostr)
                _logger.debug(f'[wecomcs] GET验证结果: ret={ret}')
                if ret != 0:
                    raise Exception(f'验证失败，错误码: {ret}')
                return reply_echo_str

            elif req.method == 'POST':
                encrypt_msg = await req.data
                _logger.debug(f'[wecomcs] POST数据长度: {len(encrypt_msg)}')

                ret, xml_msg = wxcpt.DecryptMsg(encrypt_msg, msg_signature, timestamp, nonce)
                _logger.debug(f'[wecomcs] 解密结果: ret={ret}')
                if ret != 0:
                    raise Exception(f'消息解密失败，错误码: {ret}')

                _logger.debug(f'[wecomcs] 解密后XML: {xml_msg[:500] if xml_msg else "空"}')

                if self.scheduler_enabled and self.pull_trigger_publisher and self.bot_uuid:
                    try:
                        stream_name, payload = await self.pull_trigger_publisher.publish_from_xml(
                            self.bot_uuid,
                            xml_msg,
                            webhook_received_at=int(time.time()),
                        )
                        _logger.debug(
                            f'[wecomcs] 已发布pull-trigger: stream={stream_name}, open_kfid={payload.get("open_kfid")}'
                        )
                        return 'success'
                    except Exception:
                        _logger.error(f'[wecomcs] 发布pull-trigger失败，降级为本地后台处理: {traceback.format_exc()}')

                # 中文注释：企业微信客服回调需要尽快返回 success，避免企业微信因为超时反复重试。
                self._create_background_task(self._process_callback_xml(xml_msg), description='process_wecomcs_callback')
                return 'success'
        except Exception as e:
            _logger.error(f'[wecomcs] 回调处理异常: {traceback.format_exc()}')
            return f'Error processing request: {str(e)}', 400

    def _create_background_task(self, coro, description: str):
        """创建后台任务并做好异常回收。"""
        task = asyncio.create_task(coro, name=description)
        self._background_tasks.add(task)

        def _on_done(done_task: asyncio.Task):
            self._background_tasks.discard(done_task)
            try:
                done_task.result()
            except Exception:
                _logger.error(f'[wecomcs] 后台任务执行异常: {traceback.format_exc()}')

        task.add_done_callback(_on_done)
        return task

    async def _process_callback_xml(self, xml_msg: str):
        message_list = await self.get_detailed_message_list(xml_msg)
        _logger.debug(f'[wecomcs] 消息详情: {message_list}')

        if not message_list:
            _logger.debug('[wecomcs] get_detailed_message_list返回空列表')
            return

        for message_data in message_list:
            event = WecomCSEvent.from_payload(message_data)
            _logger.debug(
                f'[wecomcs] 事件对象: type={event.type if event else "N/A"}, user_id={event.user_id if event else "N/A"}'
            )
            if event:
                await self._handle_message(event)
            else:
                _logger.warning(f'[wecomcs] 事件解析返回None, payload={message_data}')

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
        _logger.debug(f'[wecomcs] _handle_message: msg_type={msg_type}, handlers_keys={list(self._message_handlers.keys())}')
        if msg_type in self._message_handlers:
            _logger.debug(f'[wecomcs] 找到处理器, handler_count={len(self._message_handlers[msg_type])}')
            for handler in self._message_handlers[msg_type]:
                _logger.debug(f'[wecomcs] 调用处理器: {handler.__name__ if hasattr(handler, "__name__") else handler}')
                await handler(event)
        else:
            _logger.warning(f'[wecomcs] 没有找到消息类型 {msg_type} 的处理器')

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
            await self.ensure_access_token()

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
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, content=body)
            data = response.json()
            if data['errcode'] == 40014 or data['errcode'] == 42001:
                await self.refresh_access_token()
                return await self.upload_to_work(image)
            if data.get('errcode', 0) != 0:
                raise Exception('failed to upload file')

            media_id = data.get('media_id')
            return media_id

    async def download_image_to_bytes(self, url: str) -> bytes:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    # 进行media_id的获取
    async def get_media_id(self, image: platform_message.Image):
        media_id = await self.upload_to_work(image=image)
        return media_id

    async def get_customer_info(self, external_userid: str) -> dict | None:
        """
        Get customer information by external_userid with caching.

        Uses a 1-minute cache to avoid repeated API calls for the same user.

        Args:
            external_userid: The external user ID of the customer.

        Returns:
            Customer info dict with 'nickname', 'avatar', etc., or None if not found.
        """
        _logger.debug(f'[wecomcs] get_customer_info开始: user_id={external_userid}')

        # 中文注释：这里把缓存、token、接口请求三段耗时拆开打印，便于定位究竟卡在哪一步。
        started_at = time.perf_counter()
        current_time = time.time()
        if external_userid in self._customer_cache:
            cached_info, cached_time = self._customer_cache[external_userid]
            if current_time - cached_time < self._cache_ttl:
                total_elapsed_ms = (time.perf_counter() - started_at) * 1000
                _logger.debug(
                    f'[wecomcs] get_customer_info缓存命中: user_id={external_userid}, total_elapsed_ms={total_elapsed_ms:.2f}'
                )
                return cached_info

        token_started_at = time.perf_counter()
        await self.ensure_access_token()
        token_elapsed_ms = (time.perf_counter() - token_started_at) * 1000

        url = f'{self.base_url}/kf/customer/batchget?access_token={self.access_token}'

        payload = {
            'external_userid_list': [external_userid],
        }

        _logger.debug(f'[wecomcs] get_customer_info: url={url[:60]}...')
        try:
            request_started_at = time.perf_counter()
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                data = response.json()
            request_elapsed_ms = (time.perf_counter() - request_started_at) * 1000
            total_elapsed_ms = (time.perf_counter() - started_at) * 1000
            _logger.debug(
                f'[wecomcs] get_customer_info响应: errcode={data.get("errcode")}, token_elapsed_ms={token_elapsed_ms:.2f}, request_elapsed_ms={request_elapsed_ms:.2f}, total_elapsed_ms={total_elapsed_ms:.2f}'
            )

            if data.get('errcode') in [40014, 42001]:
                await self.token_cache.invalidate()
                self.access_token = ''
                return await self.get_customer_info(external_userid)

            if data.get('errcode', 0) != 0:
                _logger.warning(
                    f'[wecomcs] get_customer_info业务错误: external_userid={external_userid}, errcode={data.get("errcode")}, errmsg={data.get("errmsg")}, payload={data}'
                )
                return None

            invalid_external_userid = data.get('invalid_external_userid') or []
            if external_userid in invalid_external_userid:
                _logger.warning(
                    f'[wecomcs] get_customer_info命中invalid_external_userid: external_userid={external_userid}, invalid_external_userid={invalid_external_userid}'
                )
                return None

            customer_list = data.get('customer_list', [])
            if customer_list:
                customer_info = customer_list[0]
                # 中文注释：成功结果写入短期缓存，减少同一个客户短时间内重复查资料。
                self._customer_cache[external_userid] = (customer_info, current_time)
                return customer_info

            _logger.warning(
                f'[wecomcs] get_customer_info返回空customer_list: external_userid={external_userid}, payload={data}'
            )
            return None
        except Exception as e:
            total_elapsed_ms = (time.perf_counter() - started_at) * 1000
            _logger.error(
                f'[wecomcs] get_customer_info异常: external_userid={external_userid}, error_type={type(e).__name__}, error={e}, total_elapsed_ms={total_elapsed_ms:.2f}'
            )
            return None
