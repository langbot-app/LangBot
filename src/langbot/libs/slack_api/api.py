import asyncio
import json
import traceback
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
            data = await asyncio.to_thread(json.loads, body)
            if 'type' in data:
                if data['type'] == 'url_verification':
                    return data['challenge']

            await self.handle_payload(data)
            return jsonify({'status': 'ok'})

        except Exception as e:
            await self.logger.error(f'Error in handle_callback_request: {traceback.format_exc()}')
            raise (e)

    async def handle_payload(self, data):
        """Dispatch the same event representation for HTTP and Socket Mode."""
        raw = data.get('event', {})
        if raw.get('bot_id') or raw.get('subtype') == 'bot_message':
            return
        if raw.get('channel_type') == 'im':
            await self._handle_message(SlackEvent.from_payload(data))
        elif raw.get('type') == 'app_mention':
            raw['channel_type'] = 'channel'
            await self._handle_message(SlackEvent.from_payload(data))

    async def _socket_request(self, client, req):
        from slack_sdk.socket_mode.response import SocketModeResponse

        if req.type == 'events_api':
            key = req.payload.get('event_id') or req.envelope_id
            if key not in self.socket_seen:
                try:
                    self.socket_queue.put_nowait(req.payload)
                except asyncio.QueueFull:
                    # Leave unacknowledged so Slack can retry; do not grow tasks without bounds.
                    await self.logger.warning('Slack Socket Mode event queue is full')
                    return
                self.socket_seen[key] = True
                while len(self.socket_seen) > 4096:
                    self.socket_seen.popitem(last=False)
        await client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))

    async def run_socket(self, app_token):
        from slack_sdk.socket_mode.aiohttp import SocketModeClient

        self.socket_stop.clear()
        self.socket_client = SocketModeClient(app_token=app_token, web_client=self.client)
        self.socket_client.socket_mode_request_listeners.append(self._socket_request)

        async def worker():
            while True:
                payload = await self.socket_queue.get()
                try:
                    await self.handle_payload(payload)
                except Exception:
                    await self.logger.error('Slack Socket Mode event processing failed')
                finally:
                    self.socket_queue.task_done()

        self.socket_worker = asyncio.create_task(worker())
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

    async def _handle_message(self, event: SlackEvent):
        """
        处理消息事件。
        """
        msg_type = event.type
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
                self.bot_user_id = response['message']['bot_id']
            return
        except Exception as e:
            await self.logger.error(f'Error in send_message: {e}')
            raise e

    async def send_message_to_one(self, text: str, user_id: str):
        try:
            response = await self.client.chat_postMessage(channel='@' + user_id, text=text)
            if self.bot_user_id is None and response.get('ok'):
                self.bot_user_id = response['message']['bot_id']

            return
        except Exception as e:
            await self.logger.error(f'Error in send_message: {traceback.format_exc()}')
            raise e

    async def run_task(self, host: str, port: int, *args, **kwargs):
        """
        启动 Quart 应用。
        """
        await self.app.run_task(host=host, port=port, *args, **kwargs)
