import asyncio
import logging
import typing
from datetime import datetime

from .. import adapter as msadapter
from ..types import events as platform_events, message as platform_message, entities as platform_entities
from ...core import app, entities as core_entities

logger = logging.getLogger(__name__)


class WebChatAdapter(msadapter.MessagePlatformAdapter):
    """WebChat调试适配器，用于流水线调试"""

    ap: app.Application
    logger: logging.Logger
    
    debug_messages: dict[str, list[dict]]
    debug_sessions: dict[str, dict]
    
    def __init__(self, config: dict, ap: app.Application, logger: logging.Logger):
        self.ap = ap
        self.logger = logger
        self.config = config
        self.debug_messages = {}
        self.debug_sessions = {}
        
        self.debug_sessions['webchatperson'] = {
            'type': 'person',
            'id': 'webchatperson',
            'name': '调试私聊'
        }
        self.debug_sessions['webchatgroup'] = {
            'type': 'group', 
            'id': 'webchatgroup',
            'name': '调试群聊'
        }
        
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
            'message_chain': [component.__dict__ for component in message]
        }
        
        self.debug_messages[session_key].append(message_data)
        
        await self.logger.info(f'WebChat发送消息到 {session_key}: {message}')
        
        return {'success': True, 'message_id': message_data['id']}

    async def reply_message(
        self,
        message_source: platform_message.MessageChain,
        message: platform_message.MessageChain,
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
        pass

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        func: typing.Callable[[platform_events.Event, msadapter.MessagePlatformAdapter], typing.Awaitable[None]],
    ):
        """取消注册事件监听器"""
        pass

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

    async def send_debug_message(self, session_type: str, content: str) -> dict:
        """发送调试消息到流水线"""
        session_key = f'webchat{session_type}'
        
        if session_key not in self.debug_messages:
            self.debug_messages[session_key] = []
            
        message_chain = platform_message.MessageChain([
            platform_message.Plain(content)
        ])
        
        user_message = {
            'id': len(self.debug_messages[session_key]) + 1,
            'type': 'user',
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'message_chain': [{'type': 'Plain', 'text': content}]
        }
        
        self.debug_messages[session_key].append(user_message)
        
        if session_type == 'person':
            sender = platform_entities.Friend(id='webchatperson', nickname='调试用户')
            event = platform_events.FriendMessage(
                sender=sender,
                message_chain=message_chain,
                time=datetime.now().timestamp()
            )
            launcher_type = core_entities.LauncherTypes.PERSON
            launcher_id = 'webchatperson'
        else:
            group = platform_entities.Group(id='webchatgroup', name='调试群聊')
            sender = platform_entities.GroupMember(id='webchatperson', nickname='调试用户', group=group)
            event = platform_events.GroupMessage(
                sender=sender,
                message_chain=message_chain,
                time=datetime.now().timestamp()
            )
            launcher_type = core_entities.LauncherTypes.GROUP
            launcher_id = 'webchatgroup'
        
        await self.ap.query_pool.add_query(
            bot_uuid='webchat-debug',
            launcher_type=launcher_type,
            launcher_id=launcher_id,
            sender_id='webchatperson',
            message_event=event,
            message_chain=message_chain,
            adapter=self,
        )
        
        return {'success': True, 'message_id': user_message['id']}

    def get_debug_messages(self, session_type: str) -> list[dict]:
        """获取调试消息历史"""
        session_key = f'webchat{session_type}'
        return self.debug_messages.get(session_key, [])

    def reset_debug_session(self, session_type: str):
        """重置调试会话"""
        session_key = f'webchat{session_type}'
        self.debug_messages[session_key] = []
