import json
import traceback
from quart import Quart, jsonify, request
from slack_sdk.web.async_client import AsyncWebClient
from .slackevent import SlackEvent
from typing import Callable
import langbot_plugin.api.entities.builtin.platform.events as platform_events


class SlackClient:
    def __init__(self, bot_token: str, signing_secret: str, logger: None):
        self.bot_token = bot_token
        self.signing_secret = signing_secret
        self.app = Quart(__name__)
        self.client = AsyncWebClient(self.bot_token)
        self.app.add_url_rule(
            '/callback/command', 'handle_callback', self.handle_callback_request, methods=['GET', 'POST']
        )
        self._message_handlers = {
            'example': [],
        }
        self.bot_user_id = None  # 避免机器人回复自己的消息
        self.logger = logger

    async def handle_callback_request(self):
        try:
            body = await request.get_data()
            data = json.loads(body)
            if 'type' in data:
                if data['type'] == 'url_verification':
                    return data['challenge']

            bot_user_id = data.get('event', {}).get('bot_id', '')

            if self.bot_user_id and bot_user_id == self.bot_user_id:
                return jsonify({'status': 'ok'})

            # 处理私信
            if data and data.get('event', {}).get('channel_type') in ['im']:
                event = SlackEvent.from_payload(data)
                await self._handle_message(event)
                return jsonify({'status': 'ok'})

            # 处理群聊
            if data.get('event', {}).get('type') == 'app_mention':
                data.setdefault('event', {})['channel_type'] = 'channel'
                event = SlackEvent.from_payload(data)
                await self._handle_message(event)
                return jsonify({'status': 'ok'})

            return jsonify({'status': 'ok'})

        except Exception as e:
            await self.logger.error(f'Error in handle_callback_request: {traceback.format_exc()}')
            raise (e)

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
