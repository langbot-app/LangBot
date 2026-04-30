import time
import asyncio
import random
from quart import request
import httpx
from quart import Quart
from typing import Callable, Dict, Any, Optional
import langbot_plugin.api.entities.builtin.platform.events as platform_events
from .qqofficialevent import QQOfficialEvent
import json
import traceback
from cryptography.hazmat.primitives.asymmetric import ed25519

import websockets


class QQOfficialClient:
    def __init__(self, secret: str, token: str, app_id: str, logger: None, unified_mode: bool = False):
        self.unified_mode = unified_mode
        self.app = Quart(__name__)

        # 只有在非统一模式下才注册独立路由
        if not self.unified_mode:
            self.app.add_url_rule(
                '/callback/command',
                'handle_callback',
                self.handle_callback_request,
                methods=['GET', 'POST'],
            )

        self.secret = secret
        self.token = token
        self.app_id = app_id
        self._message_handlers = {}
        self.base_url = 'https://api.sgroup.qq.com'
        self.access_token = ''
        self.access_token_expiry_time = None
        self.logger = logger

    async def check_access_token(self):
        """检查access_token是否存在"""
        if not self.access_token or await self.is_token_expired():
            return False
        return bool(self.access_token and self.access_token.strip())

    async def get_access_token(self):
        """获取access_token"""
        url = 'https://bots.qq.com/app/getAppAccessToken'
        async with httpx.AsyncClient() as client:
            params = {
                'appId': self.app_id,
                'clientSecret': self.secret,
            }
            headers = {
                'content-type': 'application/json',
            }
            response = await client.post(url, json=params, headers=headers)
            if response.status_code != 200:
                raise Exception(f'获取access_token失败: HTTP {response.status_code} {response.text}')
            response_data = response.json()
            access_token = response_data.get('access_token')
            expires_in = int(response_data.get('expires_in', 7200))
            self.access_token_expiry_time = time.time() + expires_in - 60
            if access_token:
                self.access_token = access_token
                print(f'[QQ Official] access_token 获取成功, 有效期 {expires_in}s')
            else:
                raise Exception('获取access_token失败: 返回数据中无access_token')

    async def handle_callback_request(self):
        """处理回调请求（独立端口模式，使用全局 request）"""
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
        """处理回调请求的内部实现。

        Args:
            req: Quart Request 对象
        """
        try:
            body = await req.get_data()

            print(f'[QQ Official] Received request, body length: {len(body)}')

            if not body or len(body) == 0:
                print('[QQ Official] Received empty body, might be health check or GET request')
                return {'code': 0, 'message': 'ok'}, 200

            payload = json.loads(body)

            if payload.get('op') == 13:
                validation_data = payload.get('d')
                if not validation_data:
                    return {'error': "missing 'd' field"}, 400
                response = await self.verify(validation_data)
                return response, 200

            if payload.get('op') == 0:
                message_data = await self.get_message(payload)
                if message_data:
                    event = QQOfficialEvent.from_payload(message_data)
                    await self._handle_message(event)

            return {'code': 0, 'message': 'success'}

        except Exception as e:
            print(f'[QQ Official] ERROR: {traceback.format_exc()}')
            await self.logger.error(f'Error in handle_callback_request: {traceback.format_exc()}')
            return {'error': str(e)}, 400

    async def run_task(self, host: str, port: int, *args, **kwargs):
        """启动 Quart 应用"""
        await self.app.run_task(host=host, port=port, *args, **kwargs)

    def on_message(self, msg_type: str):
        """注册消息类型处理器"""

        def decorator(func: Callable[[platform_events.Event], None]):
            if msg_type not in self._message_handlers:
                self._message_handlers[msg_type] = []
            self._message_handlers[msg_type].append(func)
            return func

        return decorator

    async def _handle_message(self, event: QQOfficialEvent):
        """处理消息事件"""
        msg_type = event.t
        if msg_type in self._message_handlers:
            for handler in self._message_handlers[msg_type]:
                await handler(event)

    async def get_message(self, msg: dict) -> Dict[str, Any]:
        """获取消息"""
        d = msg.get('d', {})
        if not isinstance(d, dict):
            return {}
        message_data = {
            't': msg.get('t', {}),
            'user_openid': d.get('author', {}).get('user_openid', {}),
            'timestamp': d.get('timestamp', {}),
            'd_author_id': d.get('author', {}).get('id', {}),
            'content': d.get('content', {}),
            'd_id': d.get('id', {}),
            'id': msg.get('id', {}),
            'channel_id': d.get('channel_id', {}),
            'username': d.get('author', {}).get('username', {}),
            'guild_id': d.get('guild_id', {}),
            'member_openid': d.get('author', {}).get('openid', {}),
            'group_openid': d.get('group_openid', {}),
        }
        attachments = d.get('attachments', [])
        image_attachments = [attachment['url'] for attachment in attachments if await self.is_image(attachment)]
        image_attachments_type = [
            attachment['content_type'] for attachment in attachments if await self.is_image(attachment)
        ]
        if image_attachments:
            message_data['image_attachments'] = image_attachments[0]
            message_data['content_type'] = image_attachments_type[0]
        else:
            message_data['image_attachments'] = None

        return message_data

    async def is_image(self, attachment: dict) -> bool:
        """判断是否为图片附件"""
        content_type = attachment.get('content_type', '')
        return content_type.startswith('image/')

    async def send_private_text_msg(self, user_openid: str, content: str, msg_id: str):
        """发送私聊消息"""
        if not await self.check_access_token():
            await self.get_access_token()

        url = self.base_url + '/v2/users/' + user_openid + '/messages'
        async with httpx.AsyncClient() as client:
            headers = {
                'Authorization': f'QQBot {self.access_token}',
                'Content-Type': 'application/json',
            }
            data = {
                'content': content,
                'msg_type': 0,
                'msg_id': msg_id,
            }
            response = await client.post(url, headers=headers, json=data)
            response_data = response.json()
            if response.status_code == 200:
                return
            else:
                await self.logger.error(f'发送私聊消息失败: {response_data}')
                raise ValueError(response)

    async def send_group_text_msg(self, group_openid: str, content: str, msg_id: str):
        """发送群聊消息"""
        if not await self.check_access_token():
            await self.get_access_token()

        url = self.base_url + '/v2/groups/' + group_openid + '/messages'
        async with httpx.AsyncClient() as client:
            headers = {
                'Authorization': f'QQBot {self.access_token}',
                'Content-Type': 'application/json',
            }
            data = {
                'content': content,
                'msg_type': 0,
                'msg_id': msg_id,
            }
            response = await client.post(url, headers=headers, json=data)
            if response.status_code == 200:
                return
            else:
                await self.logger.error(f'发送群聊消息失败:{response.json()}')
                raise Exception(response.read().decode())

    async def send_channle_group_text_msg(self, channel_id: str, content: str, msg_id: str):
        """发送频道群聊消息"""
        if not await self.check_access_token():
            await self.get_access_token()

        url = self.base_url + '/channels/' + channel_id + '/messages'
        async with httpx.AsyncClient() as client:
            headers = {
                'Authorization': f'QQBot {self.access_token}',
                'Content-Type': 'application/json',
            }
            params = {
                'content': content,
                'msg_type': 0,
                'msg_id': msg_id,
            }
            response = await client.post(url, headers=headers, json=params)
            if response.status_code == 200:
                return True
            else:
                await self.logger.error(f'发送频道群聊消息失败: {response.json()}')
                raise Exception(response)

    async def send_channle_private_text_msg(self, guild_id: str, content: str, msg_id: str):
        """发送频道私聊消息"""
        if not await self.check_access_token():
            await self.get_access_token()

        url = self.base_url + '/dms/' + guild_id + '/messages'
        async with httpx.AsyncClient() as client:
            headers = {
                'Authorization': f'QQBot {self.access_token}',
                'Content-Type': 'application/json',
            }
            params = {
                'content': content,
                'msg_type': 0,
                'msg_id': msg_id,
            }
            response = await client.post(url, headers=headers, json=params)
            if response.status_code == 200:
                return True
            else:
                await self.logger.error(f'发送频道私聊消息失败: {response.json()}')
                raise Exception(response)

    # ---- 富媒体消息 ----

    # 媒体文件类型
    MEDIA_TYPE_IMAGE = 1
    MEDIA_TYPE_VIDEO = 2
    MEDIA_TYPE_VOICE = 3
    MEDIA_TYPE_FILE = 4

    async def upload_media(
        self,
        target_type: str,
        target_id: str,
        file_type: int,
        file_url: str = None,
        file_data: str = None,
        file_name: str = None,
    ) -> str:
        """上传媒体文件，返回 file_info。

        Args:
            target_type: 'c2c' | 'group'
            target_id: 用户 openid 或群 openid
            file_type: 1=图片, 2=视频, 3=语音, 4=文件
            file_url: 在线 URL（与 file_data 二选一）
            file_data: base64 编码的文件数据或 data URL（与 file_url 二选一）
            file_name: 文件名（file_type=4 时必填）
        """
        if not await self.check_access_token():
            await self.get_access_token()

        if target_type == 'c2c':
            url = f'{self.base_url}/v2/users/{target_id}/files'
        elif target_type == 'group':
            url = f'{self.base_url}/v2/groups/{target_id}/files'
        else:
            raise ValueError(f'Unsupported target_type: {target_type}')

        body = {
            'file_type': file_type,
            'srv_send_msg': False,
        }
        if file_url:
            body['url'] = file_url
        elif file_data:
            # 处理 data URL 格式: data:image/png;base64,xxxxx
            if file_data.startswith('data:'):
                import re

                match = re.match(r'^data:[^;]+;base64,(.+)$', file_data, re.DOTALL)
                if match:
                    body['file_data'] = match.group(1)
                else:
                    body['file_data'] = file_data
            else:
                body['file_data'] = file_data
        else:
            raise ValueError('file_url or file_data is required')

        if file_type == self.MEDIA_TYPE_FILE and file_name:
            body['file_name'] = file_name

        async with httpx.AsyncClient(timeout=120) as client:
            headers = {
                'Authorization': f'QQBot {self.access_token}',
                'Content-Type': 'application/json',
            }
            response = await client.post(url, headers=headers, json=body)
            if response.status_code == 200:
                data = response.json()
                file_info = data.get('file_info', '')
                print(
                    f'[QQ Official] 上传媒体成功, file_info={file_info[:80]}...'
                    if len(file_info) > 80
                    else f'[QQ Official] 上传媒体成功, file_info={file_info}'
                )
                return file_info
            else:
                raise Exception(f'上传媒体失败: HTTP {response.status_code} {response.text}')

    async def _send_media_msg(
        self,
        target_type: str,
        target_id: str,
        file_info: str,
        msg_id: str = None,
        content: str = None,
    ):
        """发送富媒体消息（msg_type=7）"""
        if not await self.check_access_token():
            await self.get_access_token()

        if target_type == 'c2c':
            url = f'{self.base_url}/v2/users/{target_id}/messages'
        elif target_type == 'group':
            url = f'{self.base_url}/v2/groups/{target_id}/messages'
        else:
            raise ValueError(f'Unsupported target_type: {target_type}')

        msg_seq = (int(time.time() * 1000) % 100000000 ^ random.randint(0, 65535)) % 65536
        body = {
            'msg_type': 7,
            'media': {'file_info': file_info},
            'msg_seq': msg_seq,
        }
        if content:
            body['content'] = content
        if msg_id:
            body['msg_id'] = msg_id

        async with httpx.AsyncClient(timeout=120) as client:
            headers = {
                'Authorization': f'QQBot {self.access_token}',
                'Content-Type': 'application/json',
            }
            print(f'[QQ Official] 发送富媒体消息: {json.dumps(body, ensure_ascii=False)[:200]}')
            response = await client.post(url, headers=headers, json=body)
            if response.status_code != 200:
                raise Exception(f'发送富媒体消息失败: HTTP {response.status_code} {response.text}')

    async def send_image_msg(
        self,
        target_type: str,
        target_id: str,
        file_url: str = None,
        file_data: str = None,
        msg_id: str = None,
        content: str = None,
    ):
        """发送图片消息"""
        file_info = await self.upload_media(
            target_type,
            target_id,
            self.MEDIA_TYPE_IMAGE,
            file_url=file_url,
            file_data=file_data,
        )
        await self._send_media_msg(target_type, target_id, file_info, msg_id, content)

    async def send_voice_msg(
        self,
        target_type: str,
        target_id: str,
        file_url: str = None,
        file_data: str = None,
        msg_id: str = None,
    ):
        """发送语音消息"""
        file_info = await self.upload_media(
            target_type,
            target_id,
            self.MEDIA_TYPE_VOICE,
            file_url=file_url,
            file_data=file_data,
        )
        await self._send_media_msg(target_type, target_id, file_info, msg_id)

    async def send_file_msg(
        self,
        target_type: str,
        target_id: str,
        file_url: str = None,
        file_data: str = None,
        file_name: str = None,
        msg_id: str = None,
    ):
        """发送文件消息（含视频）"""
        file_info = await self.upload_media(
            target_type,
            target_id,
            self.MEDIA_TYPE_FILE,
            file_url=file_url,
            file_data=file_data,
            file_name=file_name,
        )
        await self._send_media_msg(target_type, target_id, file_info, msg_id)

    async def send_stream_msg(
        self,
        user_openid: str,
        content: str,
        event_id: str,
        msg_id: str,
        msg_seq: int = 1,
        index: int = 0,
        stream_msg_id: str = None,
        input_state: int = 1,
    ):
        """发送流式消息（C2C 私聊）。

        Args:
            input_state: 1=生成中, 10=生成结束
        """
        if not await self.check_access_token():
            await self.get_access_token()

        url = f'{self.base_url}/v2/users/{user_openid}/stream_messages'
        body = {
            'input_mode': 'replace',
            'input_state': input_state,
            'content_type': 'markdown',
            'content_raw': content,
            'event_id': event_id,
            'msg_id': msg_id,
            'msg_seq': msg_seq,
            'index': index,
        }
        if stream_msg_id:
            body['stream_msg_id'] = stream_msg_id

        async with httpx.AsyncClient(timeout=120) as client:
            headers = {
                'Authorization': f'QQBot {self.access_token}',
                'Content-Type': 'application/json',
            }
            response = await client.post(url, headers=headers, json=body)
            if response.status_code != 200:
                raise Exception(f'发送流式消息失败: HTTP {response.status_code} {response.text}')
            return response.json()

    async def is_token_expired(self):
        """检查token是否过期"""
        if self.access_token_expiry_time is None:
            return True
        return time.time() > self.access_token_expiry_time

    async def repeat_seed(self, bot_secret: str, target_size: int = 32) -> bytes:
        seed = bot_secret
        while len(seed) < target_size:
            seed *= 2
        return seed[:target_size].encode('utf-8')

    async def verify(self, validation_payload: dict):
        seed = await self.repeat_seed(self.secret)
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed)

        event_ts = validation_payload.get('event_ts', '')
        plain_token = validation_payload.get('plain_token', '')
        msg = event_ts + plain_token

        # sign
        signature = private_key.sign(msg.encode()).hex()

        response = {
            'plain_token': plain_token,
            'signature': signature,
        }
        return response

    # ---- WebSocket Gateway ----
    # 参考文档: https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/event-emit.html

    # 基础事件（默认有权限）
    INTENT_GUILDS = 1 << 0
    INTENT_GUILD_MEMBERS = 1 << 1
    # 公域消息事件（默认有权限）
    INTENT_PUBLIC_GUILD_MESSAGES = 1 << 30
    # 私域消息事件（需要申请权限，公网机器人不应使用）
    # INTENT_GUILD_MESSAGES = 1 << 9
    # 私信事件
    INTENT_DIRECT_MESSAGE = 1 << 12
    # 群聊和单聊事件
    INTENT_GROUP_AND_C2C = 1 << 25
    # 互动事件
    INTENT_INTERACTION = 1 << 26

    # 默认 intents：基础事件 + 公域消息 + 私信 + 群聊单聊 + 互动
    FULL_INTENTS = (
        INTENT_GUILDS
        | INTENT_GUILD_MEMBERS
        | INTENT_PUBLIC_GUILD_MESSAGES
        | INTENT_DIRECT_MESSAGE
        | INTENT_GROUP_AND_C2C
        | INTENT_INTERACTION
    )

    async def get_gateway_url(self) -> str:
        """获取 WebSocket 网关地址"""
        if not await self.check_access_token():
            await self.get_access_token()

        url = f'{self.base_url}/gateway'
        async with httpx.AsyncClient() as client:
            headers = {
                'Authorization': f'QQBot {self.access_token}',
            }
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                ws_url = data.get('url', '')
                if not ws_url:
                    raise Exception('Gateway URL is empty')
                return ws_url
            else:
                raise Exception(f'获取 Gateway URL 失败: HTTP {response.status_code} {response.text}')

    async def _background_token_refresh(self):
        """在 token 到期前主动刷新"""
        try:
            while True:
                if self.access_token_expiry_time:
                    remain = self.access_token_expiry_time - time.time()
                    if remain > 120:
                        await asyncio.sleep(remain - 60)
                        continue
                self.access_token = ''
                self.access_token_expiry_time = None
                if await self.check_access_token():
                    await asyncio.sleep(60)
                else:
                    await self.get_access_token()
                    await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass

    async def connect_gateway(
        self,
        on_event: Callable[[str, dict], Any],
        on_ready: Optional[Callable[[], Any]] = None,
        on_error: Optional[Callable[[Exception], Any]] = None,
    ):
        """WebSocket 网关连接，含重连逻辑。单次调用处理一次连接生命周期。

        Args:
            on_event: 收到 op=0 Dispatch 事件时的回调，参数为 (event_type, event_data)
            on_ready: 连接就绪 (收到 READY) 时的回调
            on_error: 发生错误时的回调
        """
        session_id = ''
        last_seq = 0
        heartbeat_interval = 45000
        reconnect_attempts = 0
        max_reconnect_attempts = 100
        backoff_delays = [1, 2, 5, 10, 30, 60]
        rate_limit_delay = 60
        should_refresh_token = False
        ws = None
        heartbeat_task = None

        async def schedule_reconnect(custom_delay: Optional[int] = None):
            nonlocal reconnect_attempts
            reconnect_attempts += 1
            if reconnect_attempts > max_reconnect_attempts:
                err = Exception(f'重连次数超过 {max_reconnect_attempts}，停止重连')
                print(f'[QQ Official WS] {err}')
                if on_error:
                    on_error(err)
                return
            delay = (
                custom_delay
                if custom_delay is not None
                else backoff_delays[min(reconnect_attempts - 1, len(backoff_delays) - 1)]
            )
            print(f'[QQ Official WS] 将在 {delay}s 后重连 (第 {reconnect_attempts} 次)')
            await asyncio.sleep(delay)
            # 直接调用 connect_gateway 进行重连，避免并发问题
            await self.connect_gateway(on_event, on_ready, on_error)

        async def _heartbeat_loop(ws_conn, interval_ms):
            interval_sec = interval_ms / 1000.0
            try:
                while True:
                    await asyncio.sleep(interval_sec)
                    try:
                        payload = {'op': 1, 'd': last_seq}
                        await ws_conn.send(json.dumps(payload))
                    except Exception:
                        break
            except asyncio.CancelledError:
                pass

        # 清理旧连接
        if heartbeat_task:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            heartbeat_task = None

        if ws:
            try:
                await ws.close()
            except Exception:
                pass
            ws = None

        # 刷新 token
        if should_refresh_token:
            self.access_token = ''
            self.access_token_expiry_time = None
            should_refresh_token = False

        try:
            ws_url = await self.get_gateway_url()
            print(f'[QQ Official WS] 获取网关地址成功: {ws_url[:60]}...')
        except Exception as e:
            error_msg = str(e)
            print(f'[QQ Official WS] 获取网关地址失败: {e}')
            await self.logger.error(f'获取网关地址失败: {e}')
            if '100017' in error_msg or '频率' in error_msg or 'Too many' in error_msg:
                print(f'[QQ Official WS] 检测到频率限制，等待 {rate_limit_delay}s 后重连')
                await schedule_reconnect(rate_limit_delay)
            else:
                await schedule_reconnect()
            return

        try:
            print('[QQ Official WS] 正在连接 WebSocket...')
            ws = await websockets.connect(ws_url)
            print('[QQ Official WS] WebSocket 连接成功')
        except Exception as e:
            print(f'[QQ Official WS] WebSocket 连接失败: {e}')
            await self.logger.error(f'WebSocket 连接失败: {e}')
            await schedule_reconnect()
            return

        try:
            async for raw_msg in ws:
                try:
                    payload = json.loads(raw_msg)
                except json.JSONDecodeError:
                    await self.logger.error(f'解析消息失败: {raw_msg}')
                    continue

                op = payload.get('op')
                d = payload.get('d', {})
                s = payload.get('s')
                t = payload.get('t')

                if not isinstance(d, dict):
                    d = {}

                if op == 10:  # Hello
                    heartbeat_interval = d.get('heartbeat_interval', 45000)
                    print(f'[QQ Official WS] 收到 Hello, heartbeat_interval={heartbeat_interval}ms')

                    # 发送 Identify 或 Resume
                    if session_id and last_seq > 0:
                        resume_payload = {
                            'op': 6,
                            'd': {
                                'token': f'QQBot {self.access_token}',
                                'session_id': session_id,
                                'seq': last_seq,
                            },
                        }
                        await ws.send(json.dumps(resume_payload))
                        print(f'[QQ Official WS] 发送 Resume, session_id={session_id}, seq={last_seq}')
                    else:
                        identify_payload = {
                            'op': 2,
                            'd': {
                                'token': f'QQBot {self.access_token}',
                                'intents': self.FULL_INTENTS,
                                'shard': [0, 1],
                            },
                        }
                        await ws.send(json.dumps(identify_payload))
                        print(f'[QQ Official WS] 发送 Identify, intents={self.FULL_INTENTS}')

                    # 启动心跳
                    heartbeat_task = asyncio.create_task(_heartbeat_loop(ws, heartbeat_interval))

                elif op == 0:  # Dispatch
                    if s is not None:
                        last_seq = s

                    if t == 'READY':
                        session_id = d.get('session_id', '')
                        reconnect_attempts = 0
                        print(f'[QQ Official WS] ✅ READY, session_id={session_id}')
                        if on_ready:
                            try:
                                result = on_ready()
                                if asyncio.iscoroutine(result):
                                    await result
                            except Exception:
                                pass
                        asyncio.create_task(self._background_token_refresh())

                    elif t == 'RESUMED':
                        reconnect_attempts = 0
                        print('[QQ Official WS] ✅ RESUMED')

                    else:
                        print(f'[QQ Official WS] 收到事件: {t}, seq={s}')
                        if on_event:
                            try:
                                result = on_event(t, d)
                                if asyncio.iscoroutine(result):
                                    await result
                            except Exception:
                                await self.logger.error(f'处理事件 {t} 失败: {traceback.format_exc()}')

                elif op == 11:  # Heartbeat ACK
                    pass

                elif op == 7:  # Reconnect
                    print('[QQ Official WS] 收到 Reconnect 指令')
                    try:
                        await ws.close()
                    except Exception:
                        pass
                    await schedule_reconnect()
                    return

                elif op == 9:  # Invalid Session
                    can_resume = d.get('can_resume', False)
                    print(f'[QQ Official WS] Invalid Session, can_resume={can_resume}')
                    if not can_resume:
                        session_id = ''
                        last_seq = 0
                        should_refresh_token = True
                    try:
                        await ws.close()
                    except Exception:
                        pass
                    await schedule_reconnect(3)
                    return

            # 连接关闭
            try:
                close_code = ws.close_code
                close_reason = ws.close_reason or ''
            except Exception:
                close_code = None
                close_reason = ''
            print(f'[QQ Official WS] 连接关闭, code={close_code}, reason={close_reason}')

            if close_code == 4004:
                should_refresh_token = True
            elif close_code in (4006, 4007, 4009):
                session_id = ''
                last_seq = 0
                should_refresh_token = True
            elif close_code == 4008:
                print(f'[QQ Official WS] 触发频率限制，等待 {rate_limit_delay}s 后重连')
                await schedule_reconnect(rate_limit_delay)
                return
            elif close_code in (4914, 4915):
                err = Exception(f'Bot 下线/封禁 (close_code={close_code})')
                if on_error:
                    on_error(err)
                return
            elif close_code in (4900, 4901, 4902, 4903, 4904, 4905, 4906, 4907, 4908, 4909, 4910, 4911, 4912, 4913):
                session_id = ''
                last_seq = 0

            if close_code != 1000:
                await schedule_reconnect()
        finally:
            if heartbeat_task:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            if ws:
                try:
                    await ws.close()
                except Exception:
                    pass

    async def connect_gateway_loop(
        self,
        on_event: Callable[[str, dict], Any],
        on_ready: Optional[Callable[[], Any]] = None,
        on_error: Optional[Callable[[Exception], Any]] = None,
    ):
        """持续重连的网关循环。"""
        await self.connect_gateway(on_event, on_ready, on_error)
