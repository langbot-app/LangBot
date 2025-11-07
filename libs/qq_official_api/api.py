import time
from quart import request
import httpx
from quart import Quart
from typing import Callable, Dict, Any
import langbot_plugin.api.entities.builtin.platform.events as platform_events
from .qqofficialevent import QQOfficialEvent
import json
import traceback
from cryptography.hazmat.primitives.asymmetric import ed25519


def handle_validation(body: dict, bot_secret: str):
    """
    处理 QQ 官方机器人的回调验证请求

    Args:
        body: 包含验证数据的请求体
        bot_secret: 机器人密钥

    Returns:
        包含签名的验证响应
    """
    try:
        # 解析验证数据
        validation_data = body.get('d')
        if not validation_data:
            print("parse http payload failed: missing 'd' field")
            return None

        event_ts = validation_data.get('event_ts')
        plain_token = validation_data.get('plain_token')

        if not event_ts or not plain_token:
            print("parse http payload failed: missing event_ts or plain_token")
            return None

        # 处理 bot_secret：确保长度达到 32 字节（ed25519.SeedSize）
        seed = bot_secret
        while len(seed) < 32:
            seed = seed * 2
        seed = seed[:32]

        # 将 seed 转换为字节
        seed_bytes = seed.encode()

        # 从 seed 生成 ed25519 私钥
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed_bytes)

        msg = event_ts + plain_token
        msg_bytes = msg.encode()

        signature = private_key.sign(msg_bytes)

        # 将签名转换为十六进制字符串
        signature_hex = signature.hex()

        # 构建验证响应
        response = {
            'plain_token': plain_token,
            'signature': signature_hex
        }

        # 打印调试信息
        print(f'[QQ Official Validation]')
        print(f'  event_ts: {event_ts}')
        print(f'  plain_token: {plain_token}')
        print(f'  Message to sign: {msg}')
        print(f'  Signature: {signature_hex}')

        return response

    except Exception as e:
        print(f"handle validation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


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
            try:
                response = await client.post(url, json=params, headers=headers)
                if response.status_code == 200:
                    response_data = response.json()
                access_token = response_data.get('access_token')
                expires_in = int(response_data.get('expires_in', 7200))
                self.access_token_expiry_time = time.time() + expires_in - 60
                if access_token:
                    self.access_token = access_token
            except Exception as e:
                await self.logger.error(f'获取access_token失败: {response_data}')
                raise Exception(f'获取access_token失败: {e}')

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
            # 读取请求数据
            body = await req.get_data()

            print(f'[QQ Official] Received request, body length: {len(body)}')

            payload = json.loads(body)

            # 验证是否为回调验证请求
            if payload.get('op') == 13:
                print(f'[QQ Official] Received callback validation request (op=13)')
                # 生成签名
                response = handle_validation(payload, self.secret)
                print(response)
                print(f'[QQ Official] Returning validation response')
                return response

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
        message_data = {
            't': msg.get('t', {}),
            'user_openid': msg.get('d', {}).get('author', {}).get('user_openid', {}),
            'timestamp': msg.get('d', {}).get('timestamp', {}),
            'd_author_id': msg.get('d', {}).get('author', {}).get('id', {}),
            'content': msg.get('d', {}).get('content', {}),
            'd_id': msg.get('d', {}).get('id', {}),
            'id': msg.get('id', {}),
            'channel_id': msg.get('d', {}).get('channel_id', {}),
            'username': msg.get('d', {}).get('author', {}).get('username', {}),
            'guild_id': msg.get('d', {}).get('guild_id', {}),
            'member_openid': msg.get('d', {}).get('author', {}).get('openid', {}),
            'group_openid': msg.get('d', {}).get('group_openid', {}),
        }
        attachments = msg.get('d', {}).get('attachments', [])
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

    async def is_token_expired(self):
        """检查token是否过期"""
        if self.access_token_expiry_time is None:
            return True
        return time.time() > self.access_token_expiry_time
