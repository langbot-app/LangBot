import asyncio
import json
import traceback
from urllib.parse import parse_qs
from slack_sdk.signature import SignatureVerifier
from quart import Quart, jsonify, request
from slack_sdk.web.async_client import AsyncWebClient
from .slackevent import SlackEvent
from typing import Callable
from collections import OrderedDict
import langbot_plugin.api.entities.builtin.platform.events as platform_events

_MAX_CALLBACK_BODY_BYTES = 1024 * 1024


class SlackClient:
    def __init__(self, bot_token: str, signing_secret: str, logger: None, unified_mode: bool = False):
        self.bot_token = bot_token
        self.signing_secret = signing_secret
        self.unified_mode = unified_mode
        self.app = Quart(__name__)
        self.app.config['MAX_CONTENT_LENGTH'] = _MAX_CALLBACK_BODY_BYTES
        self.client = AsyncWebClient(self.bot_token)

        # 只有在非统一模式下才注册独立路由
        if not self.unified_mode:
            self.app.add_url_rule(
                '/callback/command', 'handle_callback', self.handle_callback_request, methods=['GET', 'POST']
            )

        self._message_handlers = {
            'example': [],
        }
        self.bot_user_id = None  # 避免机器人回复自己的消息
        self.logger = logger
        self.socket_client = None
        self.socket_queue = asyncio.Queue(maxsize=100)
        self.socket_seen = OrderedDict()
        self.socket_stop = asyncio.Event()
        self.socket_worker = None

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
        if self.socket_client is not None:
            return jsonify({'error': 'Socket Mode is enabled'}), 409
        return await self._handle_callback_internal(req)

    async def _handle_callback_internal(self, req):
        """处理回调请求的内部实现。

        Args:
            req: Quart Request 对象
        """
        try:
            body = await req.get_data()
            if len(body) > _MAX_CALLBACK_BODY_BYTES:
                raise ValueError('Slack callback body exceeds the size limit')
            if not SignatureVerifier(self.signing_secret).is_valid_request(body, dict(req.headers)):
                return jsonify({'error': 'Invalid Slack signature'}), 401
            if req.mimetype == 'application/x-www-form-urlencoded':
                data = json.loads(parse_qs(body.decode()).get('payload', ['{}'])[0])
            else:
                data = json.loads(body)
            if 'type' in data:
                if data['type'] == 'url_verification':
                    return data['challenge']

            self._start_worker()
            if not self._enqueue(data, data.get('event_id')):
                return jsonify({'error': 'Slack event queue is full'}), 503
            return '', 200

        except Exception as e:
            await self.logger.error(f'Error in handle_callback_request: {traceback.format_exc()}')
            raise (e)

    async def handle_payload(self, data):
        """Dispatch the same event representation for HTTP and Socket Mode."""
        raw = data.get('event', {})
        for authorization in data.get('authorizations', []):
            if not self.bot_user_id and authorization.get('is_bot') and authorization.get('user_id'):
                self.bot_user_id = authorization['user_id']
                break
        if data.get('type') in {'block_actions', 'view_submission', 'view_closed', 'shortcut', 'message_action'}:
            await self._handle_message(SlackEvent(data), 'event')
            return
        if raw.get('bot_id') or raw.get('subtype') == 'bot_message':
            return
        kind, subtype = raw.get('type'), raw.get('subtype')
        if kind == 'message' and subtype not in (None, 'file_share', 'thread_broadcast'):
            await self._handle_message(SlackEvent(data), 'event')
        elif raw.get('channel_type') == 'im' and kind == 'message':
            await self._handle_message(SlackEvent.from_payload(data))
        elif kind == 'app_mention':
            raw['channel_type'] = 'channel'
            await self._handle_message(SlackEvent.from_payload(data))
        elif kind != 'message':
            await self._handle_message(SlackEvent(data), 'event')

    def _enqueue(self, payload, key=None):
        if key and key in self.socket_seen:
            return True
        try:
            self.socket_queue.put_nowait(payload)
        except asyncio.QueueFull:
            return False
        if key:
            self.socket_seen[key] = True
            while len(self.socket_seen) > 4096:
                self.socket_seen.popitem(last=False)
        return True

    def _start_worker(self):
        if self.socket_worker is not None and not self.socket_worker.done():
            return

        async def worker():
            while True:
                payload = await self.socket_queue.get()
                try:
                    await self.handle_payload(payload)
                except Exception:
                    await self.logger.error('Slack event processing failed')
                finally:
                    self.socket_queue.task_done()

        self.socket_worker = asyncio.create_task(worker())

    async def _socket_request(self, client, req):
        from slack_sdk.socket_mode.response import SocketModeResponse

        if req.type in {'events_api', 'interactive'}:
            key = req.payload.get('event_id') or req.envelope_id
            if not self._enqueue(req.payload, key):
                # Leave unacknowledged so Slack can retry; do not grow tasks without bounds.
                await self.logger.warning('Slack Socket Mode event queue is full')
                return
        await client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))

    async def run_socket(self, app_token):
        from slack_sdk.socket_mode.aiohttp import SocketModeClient

        self.socket_stop.clear()
        self.socket_client = SocketModeClient(app_token=app_token, web_client=self.client)
        self.socket_client.socket_mode_request_listeners.append(self._socket_request)

        self._start_worker()
        try:
            await self.socket_client.connect()
            await self.logger.info('Slack Socket Mode connected')
            await self.socket_stop.wait()
        finally:
            await self.close_socket()

    async def close_socket(self):
        self.socket_stop.set()
        client, self.socket_client = self.socket_client, None
        if client is not None:
            await client.close()
        worker, self.socket_worker = self.socket_worker, None
        if worker is not None:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
        self.socket_seen.clear()
        while not self.socket_queue.empty():
            self.socket_queue.get_nowait()
            self.socket_queue.task_done()

    async def _handle_message(self, event: SlackEvent, kind=None):
        """
        处理消息事件。
        """
        msg_type = kind or event.type
        if msg_type in self._message_handlers:
            for handler in self._message_handlers[msg_type]:
                await handler(event)

    def on_message(self, msg_type: str):
        """注册消息类型处理器"""

        def decorator(func: Callable[[platform_events.Event], None]):
            if msg_type not in self._message_handlers:
                self._message_handlers[msg_type] = []
            self._message_handlers[msg_type].append(func)
            return func

        return decorator

    async def send_message_to_channel(self, text: str, channel_id: str):
        try:
            response = await self.client.chat_postMessage(channel=channel_id, text=text)
            if self.bot_user_id is None and response.get('ok'):
                self.bot_user_id = response.get('message', {}).get('user')
            return response.data if hasattr(response, 'data') else response
        except Exception as e:
            await self.logger.error(f'Error in send_message: {e}')
            raise e

    async def send_message_to_one(self, text: str, user_id: str):
        try:
            response = await self.client.chat_postMessage(channel='@' + user_id, text=text)
            if self.bot_user_id is None and response.get('ok'):
                self.bot_user_id = response.get('message', {}).get('user')

            return response.data if hasattr(response, 'data') else response
        except Exception as e:
            await self.logger.error(f'Error in send_message: {traceback.format_exc()}')
            raise e

    async def run_task(self, host: str, port: int, *args, **kwargs):
        """
        启动 Quart 应用。
        """
        await self.app.run_task(host=host, port=port, *args, **kwargs)
