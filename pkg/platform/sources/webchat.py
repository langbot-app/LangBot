import asyncio
import logging
import typing
from datetime import datetime

from .. import adapter as msadapter
from ..types import events as platform_events, message as platform_message, entities as platform_entities
from ...core import app
from ..logger import EventLogger

logger = logging.getLogger(__name__)


class WebChatAdapter(msadapter.MessagePlatformAdapter):
    """WebChat调试适配器，用于流水线调试"""

    debug_messages: dict[str, list[dict]]
    debug_sessions: dict[str, dict]

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, msadapter.MessagePlatformAdapter], None],
    ] = {}

    def __init__(self, config: dict, ap: app.Application, logger: EventLogger):
        self.ap = ap
        self.logger = logger
        self.config = config
        self.debug_messages = {}
        self.debug_sessions = {}

        self.debug_sessions['webchatperson'] = {'type': 'person', 'id': 'webchatperson', 'name': '调试私聊'}
        self.debug_sessions['webchatgroup'] = {'type': 'group', 'id': 'webchatgroup', 'name': '调试群聊'}

        self.debug_messages['webchatperson'] = []
        self.debug_messages['webchatgroup'] = []

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ) -> dict:
        """发送消息到调试会话"""
        session_key = target_id

        if session_key not in self.debug_messages:
            self.debug_messages[session_key] = []

        message_data = {
            'id': len(self.debug_messages[session_key]) + 1,
            'type': 'bot',
            'content': str(message),
            'timestamp': datetime.now().isoformat(),
            'message_chain': [component.__dict__ for component in message],
        }

        self.debug_messages[session_key].append(message_data)

        await self.logger.info(f'Send message to {session_key}: {message}')

        return {'success': True, 'message_id': message_data['id']}

    async def reply_message(
        self,
        message_source: platform_message.MessageChain,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ) -> dict:
        """回复消息"""
        source_components = [comp for comp in message_source if isinstance(comp, platform_message.Source)]
        if source_components:
            source = source_components[0]
            session_key = getattr(source, 'session_id', 'webchatperson')
        else:
            session_key = 'webchatperson'

        return await self.send_message('person', session_key, message)

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        func: typing.Callable[[platform_events.Event, msadapter.MessagePlatformAdapter], typing.Awaitable[None]],
    ):
        """注册事件监听器"""
        self.listeners[event_type] = func

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        func: typing.Callable[[platform_events.Event, msadapter.MessagePlatformAdapter], typing.Awaitable[None]],
    ):
        """取消注册事件监听器"""
        del self.listeners[event_type]

    async def run_async(self):
        """运行适配器"""
        await self.logger.info('WebChat调试适配器已启动')

        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            await self.logger.info('WebChat调试适配器已停止')
            raise

    async def kill(self):
        """停止适配器"""
        await self.logger.info('WebChat调试适配器正在停止')

    async def send_debug_message(
        self, pipeline_uuid: str, session_type: str, message_chain_obj: typing.List[dict]
    ) -> None:
        """发送调试消息到流水线"""
        session_key = f'webchat{session_type}'

        if session_key not in self.debug_messages:
            self.debug_messages[session_key] = []

        message_chain = platform_message.MessageChain.parse_obj(message_chain_obj)

        user_message = {
            'id': len(self.debug_messages[session_key]) + 1,
            'type': 'user',
            'content': str(message_chain),
            'timestamp': datetime.now().isoformat(),
            'message_chain_obj': message_chain_obj,
        }

        self.debug_messages[session_key].append(user_message)

        if session_type == 'person':
            sender = platform_entities.Friend(id='webchatperson', nickname='User')
            event = platform_events.FriendMessage(
                sender=sender, message_chain=message_chain, time=datetime.now().timestamp()
            )
        else:
            group = platform_entities.Group(id='webchatgroup', name='Group')
            sender = platform_entities.GroupMember(id='webchatperson', nickname='User', group=group)
            event = platform_events.GroupMessage(
                sender=sender, message_chain=message_chain, time=datetime.now().timestamp()
            )

        self.ap.platform_mgr.webchat_proxy_bot.bot_entity.use_pipeline_uuid = pipeline_uuid

        if event.__class__ in self.listeners:
            await self.listeners[event.__class__](event, self)

        return None

    def get_debug_messages(self, session_type: str) -> list[dict]:
        """获取调试消息历史"""
        session_key = f'webchat{session_type}'
        return self.debug_messages.get(session_key, [])

    def reset_debug_session(self, session_type: str):
        """重置调试会话"""
        session_key = f'webchat{session_type}'
        self.debug_messages[session_key] = []
