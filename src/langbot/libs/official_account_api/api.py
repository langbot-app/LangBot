# 微信公众号的加解密算法与企业微信一样，所以直接使用企业微信的加解密算法文件
import time
import traceback
from langbot.libs.wecom_api.WXBizMsgCrypt3 import WXBizMsgCrypt
import xml.etree.ElementTree as ET
from quart import Quart, request
import hashlib
import hmac
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

_MAX_CALLBACK_BODY_BYTES = 1024 * 1024


async def _read_callback_xml(client, req):
    body = await req.data
    if len(body) > _MAX_CALLBACK_BODY_BYTES:
        raise ValueError('Official Account callback body exceeds the size limit')
    root = ET.fromstring(body)
    if root.find('Encrypt') is not None:
        crypt = WXBizMsgCrypt(client.token, client.aes, client.appid)
        code, xml = await asyncio.to_thread(
            crypt.DecryptMsg, body, req.args.get('msg_signature', ''),
            req.args.get('timestamp', ''), req.args.get('nonce', ''),
        )
        if code != 0:
            raise ValueError('Official Account callback decryption failed')
        return xml.decode('utf-8') if isinstance(xml, bytes) else xml
    digest = hashlib.sha1(''.join(sorted([
        client.token, req.args.get('timestamp', ''), req.args.get('nonce', ''),
    ])).encode('utf-8')).hexdigest()
    if not hmac.compare_digest(digest, req.args.get('signature', '')):
        raise ValueError('Official Account callback signature verification failed')
    return body.decode('utf-8')


class OAClient:
    _STATE_TTL_SECONDS = 600
    _STATE_MAX = 4096
    _MAX_CONTENT_CHARS = 200000

    def __init__(
        self,
        token: str,
        EncodingAESKey: str,
        AppID: str,
        Appsecret: str,
        logger: None,
        unified_mode: bool = False,
        api_base_url: str = 'https://api.weixin.qq.com',
    ):
        self.token = token
        self.aes = EncodingAESKey
        self.appid = AppID
        self.appsecret = Appsecret
        self.base_url = api_base_url
        self.access_token = ''
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
        self.access_token_expiry_time = None
        self.msg_id_map = {}
        self._processing_tasks: set[asyncio.Task] = set()
        self.generated_content = {}
        self._msg_seen_at = {}
        self._generated_at = {}
        self._last_state_prune = 0.0
        self.logger = logger

    def _prune_state(self) -> None:
        now = time.monotonic()
        if now - self._last_state_prune >= 60:
            self._last_state_prune = now
            for message_id, seen_at in tuple(self._msg_seen_at.items()):
                if now - seen_at > self._STATE_TTL_SECONDS:
                    self._msg_seen_at.pop(message_id, None)
                    self.msg_id_map.pop(message_id, None)
            for message_id, generated_at in tuple(self._generated_at.items()):
                if now - generated_at > self._STATE_TTL_SECONDS:
                    self._generated_at.pop(message_id, None)
                    self.generated_content.pop(message_id, None)
        while len(self.msg_id_map) > self._STATE_MAX:
            message_id = next(iter(self.msg_id_map))
            self.msg_id_map.pop(message_id, None)
            self._msg_seen_at.pop(message_id, None)
        while len(self.generated_content) > self._STATE_MAX:
            message_id = next(iter(self.generated_content))
            self.generated_content.pop(message_id, None)
            self._generated_at.pop(message_id, None)

    def clear(self) -> None:
        for task in self._processing_tasks:
            task.cancel()
        self._processing_tasks.clear()
        self.msg_id_map.clear()
        self.generated_content.clear()
        self._msg_seen_at.clear()
        self._generated_at.clear()

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
        """处理回调请求的内部实现，包括 GET 验证和 POST 消息接收。

        Args:
            req: Quart Request 对象
        """
        try:
            # 每隔100毫秒查询是否生成ai回答
            start_time = time.time()
            signature = req.args.get('signature', '')
            timestamp = req.args.get('timestamp', '')
            nonce = req.args.get('nonce', '')
            echostr = req.args.get('echostr', '')
            msg_signature = req.args.get('msg_signature', '')
            if msg_signature is None:
                await self.logger.error('msg_signature不在请求体中')
                raise Exception('msg_signature不在请求体中')

            if req.method == 'GET':
                if msg_signature:
                    wxcpt = WXBizMsgCrypt(self.token, self.aes, self.appid)
                    ret, reply_echo = wxcpt.VerifyURL(msg_signature, timestamp, nonce, echostr)
                    if ret == 0:
                        return reply_echo
                    await self.logger.error(
                        'OfficialAccount encrypted URL verification failed: '
                        f'ret={ret}, timestamp_present={bool(timestamp)}, nonce_present={bool(nonce)}, '
                        f'echostr_present={bool(echostr)}'
                    )

                # Plaintext callback verification.
                check_str = ''.join(sorted([self.token, timestamp, nonce]))
                check_signature = hashlib.sha1(check_str.encode('utf-8')).hexdigest()

                if check_signature == signature:
                    return echostr  # 验证成功返回echostr
                else:
                    await self.logger.error(
                        'OfficialAccount plaintext URL verification failed: '
                        f'signature_present={bool(signature)}, timestamp_present={bool(timestamp)}, '
                        f'nonce_present={bool(nonce)}, echostr_present={bool(echostr)}'
                    )
                    return 'signature verification failed', 403
            elif req.method == 'POST':
                xml_msg = await _read_callback_xml(self, req)

                message_data = await self.get_message(xml_msg)
                if message_data:
                    event = OAEvent.from_payload(message_data)
                    if event:
                        from langbot.pkg.core.task_boundary import create_detached_task

                        task = create_detached_task(self._process_message(event))
                        self._processing_tasks.add(task)
                        task.add_done_callback(self._processing_tasks.discard)

                root = await asyncio.to_thread(ET.fromstring, xml_msg)
                from_user = root.find('FromUserName').text  # 发送者
                to_user = root.find('ToUserName').text  # 机器人

                timeout = 4.80
                interval = 0.1
                while True:
                    content = self.generated_content.pop(message_data['MsgId'], None)
                    self._generated_at.pop(message_data['MsgId'], None)
                    if content:
                        response_xml = xml_template.format(
                            to_user=from_user,
                            from_user=to_user,
                            create_time=int(time.time()),
                            content=content.replace(']]>', ']]]]><![CDATA[>'),
                        )

                        return response_xml

                    if time.time() - start_time >= timeout:
                        break

                    await asyncio.sleep(interval)

                return 'success'

        except Exception:
            await self.logger.error(f'handle_callback_request失败: {traceback.format_exc()}')
            traceback.print_exc()

    async def get_message(self, xml_msg: str):
        root = await asyncio.to_thread(ET.fromstring, xml_msg)

        message_data = {element.tag: element.text for element in root}
        message_data['CreateTime'] = int(message_data.get('CreateTime') or 0)
        if message_data.get('MsgId'):
            message_data['MsgId'] = int(message_data['MsgId'])
        else:
            message_data['MsgId'] = ':'.join(str(message_data.get(key) or '') for key in (
                'FromUserName', 'CreateTime', 'Event', 'EventKey',
            ))

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

    async def _process_message(self, event: OAEvent):
        try:
            await self._handle_message(event)
        except Exception:
            await self.logger.error(f'OfficialAccount processing failed: {traceback.format_exc()}')

    async def _handle_message(self, event: OAEvent):
        """
        处理消息事件。
        """
        message_id = event.message_id
        self._prune_state()
        if message_id in self.msg_id_map.keys():
            self.msg_id_map[message_id] += 1
            self._msg_seen_at[message_id] = time.monotonic()
            return

        self.msg_id_map[message_id] = 1
        self._msg_seen_at[message_id] = time.monotonic()
        msg_type = event.type
        if msg_type in self._message_handlers:
            for handler in self._message_handlers[msg_type]:
                await handler(event)

    async def set_message(self, msg_id: int, content: str):
        self.generated_content[msg_id] = str(content)[: self._MAX_CONTENT_CHARS]
        self._generated_at[msg_id] = time.monotonic()
        self._prune_state()


class OAClientForLongerResponse:
    _MAX_USERS = 4096
    _MAX_MESSAGES_PER_USER = 20
    _MAX_CONTENT_CHARS = 200000

    def __init__(
        self,
        token: str,
        EncodingAESKey: str,
        AppID: str,
        Appsecret: str,
        LoadingMessage: str,
        logger: None,
        unified_mode: bool = False,
        api_base_url: str = 'https://api.weixin.qq.com',
        customer_service: bool = False,
    ):
        self.token = token
        self.aes = EncodingAESKey
        self.appid = AppID
        self.appsecret = Appsecret
        self.base_url = api_base_url
        self.access_token = ''
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
        self.access_token_expiry_time = None
        self.loading_message = LoadingMessage
        from .customer_service import CustomerServiceReplies

        self.customer_service = CustomerServiceReplies(AppID, Appsecret, api_base_url) if customer_service else None
        self._callback_responses = {}
        self.msg_queue = {}
        self.user_msg_queue = {}
        self._processing_tasks: set[asyncio.Task] = set()
        self._last_queue_cleanup = 0.0
        self.logger = logger

    def _prune_queues(self) -> None:
        now = time.monotonic()
        if now - self._last_queue_cleanup >= 60:
            self._last_queue_cleanup = now
            for user_id, queue in tuple(self.msg_queue.items()):
                if not queue:
                    self.msg_queue.pop(user_id, None)
            for user_id, queue in tuple(self.user_msg_queue.items()):
                if not queue:
                    self.user_msg_queue.pop(user_id, None)
        while len(self.msg_queue) > self._MAX_USERS:
            self.msg_queue.pop(next(iter(self.msg_queue)), None)
        while len(self.user_msg_queue) > self._MAX_USERS:
            self.user_msg_queue.pop(next(iter(self.user_msg_queue)), None)

    def clear(self) -> None:
        self.msg_queue.clear()
        self.user_msg_queue.clear()
        self._callback_responses.clear()
        for task in self._processing_tasks:
            task.cancel()
        self._processing_tasks.clear()

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
        """处理回调请求的内部实现，包括 GET 验证和 POST 消息接收。

        Args:
            req: Quart Request 对象
        """
        try:
            signature = req.args.get('signature', '')
            timestamp = req.args.get('timestamp', '')
            nonce = req.args.get('nonce', '')
            echostr = req.args.get('echostr', '')
            msg_signature = req.args.get('msg_signature', '')

            if msg_signature is None:
                await self.logger.error('msg_signature不在请求体中')
                raise Exception('msg_signature不在请求体中')

            if req.method == 'GET':
                if msg_signature:
                    wxcpt = WXBizMsgCrypt(self.token, self.aes, self.appid)
                    ret, reply_echo = wxcpt.VerifyURL(msg_signature, timestamp, nonce, echostr)
                    if ret == 0:
                        return reply_echo
                    await self.logger.error(
                        'OfficialAccount encrypted URL verification failed: '
                        f'ret={ret}, timestamp_present={bool(timestamp)}, nonce_present={bool(nonce)}, '
                        f'echostr_present={bool(echostr)}'
                    )

                check_str = ''.join(sorted([self.token, timestamp, nonce]))
                check_signature = hashlib.sha1(check_str.encode('utf-8')).hexdigest()
                if check_signature == signature:
                    return echostr
                await self.logger.error(
                    'OfficialAccount plaintext URL verification failed: '
                    f'signature_present={bool(signature)}, timestamp_present={bool(timestamp)}, '
                    f'nonce_present={bool(nonce)}, echostr_present={bool(echostr)}'
                )
                return 'signature verification failed', 403

            elif req.method == 'POST':
                xml_msg = await _read_callback_xml(self, req)

                # 解析 XML
                root = await asyncio.to_thread(ET.fromstring, xml_msg)
                from_user = root.find('FromUserName').text
                to_user = root.find('ToUserName').text
                message_key = (from_user, root.findtext('MsgId') or (
                    root.findtext('CreateTime'), root.findtext('Event'), root.findtext('EventKey')
                ))
                cached = self._callback_responses.get(message_key)
                if cached and time.monotonic() - cached[0] < 600:
                    return cached[1]

                def remember(response):
                    self._callback_responses[message_key] = (time.monotonic(), response)
                    while len(self._callback_responses) > self._MAX_USERS:
                        self._callback_responses.pop(next(iter(self._callback_responses)))
                    return response

                if self.msg_queue.get(from_user) and self.msg_queue[from_user][0]['content']:
                    queue_top = self.msg_queue[from_user].pop(0)
                    queue_content = queue_top['content']

                    # 弹出用户消息
                    if self.user_msg_queue.get(from_user) and self.user_msg_queue[from_user]:
                        self.user_msg_queue[from_user].pop(0)
                    self._prune_queues()

                    response_xml = xml_template.format(
                        to_user=from_user,
                        from_user=to_user,
                        create_time=int(time.time()),
                        content=queue_content.replace(']]>', ']]]]><![CDATA[>'),
                    )
                    return remember(response_xml)

                else:
                    response_xml = xml_template.format(
                        to_user=from_user,
                        from_user=to_user,
                        create_time=int(time.time()),
                        content=self.loading_message.replace(']]>', ']]]]><![CDATA[>'),
                    )
                    if not self.loading_message:
                        response_xml = 'success'

                    if self.user_msg_queue.get(from_user):
                        return remember(response_xml)
                    else:
                        message_data = await self.get_message(xml_msg)

                        if message_data:
                            event = OAEvent.from_payload(message_data)
                            if event:
                                self.user_msg_queue.setdefault(from_user, []).append(
                                    {
                                        'content': str(event.message)[: self._MAX_CONTENT_CHARS],
                                    }
                                )
                                self.user_msg_queue[from_user] = self.user_msg_queue[from_user][
                                    -self._MAX_MESSAGES_PER_USER :
                                ]
                                self._prune_queues()
                                # The callback must return the loading reply immediately.
                                # Native listeners establish their own Workspace scope.
                                from langbot.pkg.core.task_boundary import create_detached_task

                                task = create_detached_task(self._process_pending_message(event))
                                self._processing_tasks.add(task)
                                task.add_done_callback(self._processing_tasks.discard)

                        return remember(response_xml)

        except Exception:
            await self.logger.error(f'handle_callback_request失败: {traceback.format_exc()}')
            traceback.print_exc()

    async def get_message(self, xml_msg: str):
        root = await asyncio.to_thread(ET.fromstring, xml_msg)

        message_data = {element.tag: element.text for element in root}
        message_data['CreateTime'] = int(message_data.get('CreateTime') or 0)
        if message_data.get('MsgId'):
            message_data['MsgId'] = int(message_data['MsgId'])
        else:
            message_data['MsgId'] = ':'.join(str(message_data.get(key) or '') for key in (
                'FromUserName', 'CreateTime', 'Event', 'EventKey',
            ))

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

    async def _process_pending_message(self, event: OAEvent):
        try:
            await self._handle_message(event)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.user_msg_queue.pop(event.user_id, None)
            await self.logger.error(f'OfficialAccount passive processing failed: {traceback.format_exc()}')

    async def set_message(self, from_user: int, message_id: int, content: str):
        if self.customer_service is not None:
            try:
                code = await self.customer_service.send(str(from_user), content)
            except Exception as exc:
                # Do not expose request URLs containing access tokens or AppSecret.
                self.user_msg_queue.pop(from_user, None)
                raise RuntimeError(f'OfficialAccount customer message failed ({type(exc).__name__})') from None
            if code == 0:
                self.user_msg_queue.pop(from_user, None)
                return False
            if code not in {48001, 45015, 45047, 43004}:
                self.user_msg_queue.pop(from_user, None)
                raise RuntimeError(f'OfficialAccount customer message rejected: errcode={code}')
            await self.logger.info(
                f'OfficialAccount customer message unavailable (errcode={code}); reply queued for next message'
            )
        if from_user not in self.msg_queue:
            self.msg_queue[from_user] = []

        self.msg_queue[from_user].append(
            {
                'msg_id': message_id,
                'content': str(content)[: self._MAX_CONTENT_CHARS],
            }
        )
        self.msg_queue[from_user] = self.msg_queue[from_user][-self._MAX_MESSAGES_PER_USER :]
        self._prune_queues()
        return True
