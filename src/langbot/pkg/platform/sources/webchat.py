import asyncio
import logging
import typing
from datetime import datetime

import pydantic

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
from ...core import app

logger = logging.getLogger(__name__)


class WebChatMessage(pydantic.BaseModel):
    id: int
    role: str
    content: str
    message_chain: list[dict]
    timestamp: str
    is_final: bool = False


class WebChatSession:
    id: str
    message_lists: dict[str, list[WebChatMessage]] = {}
    resp_waiters: dict[int, asyncio.Future[WebChatMessage]]
    resp_queues: dict[int, asyncio.Queue[WebChatMessage]]

    def __init__(self, id: str):
        self.id = id
        self.message_lists = {}
        self.resp_waiters = {}
        self.resp_queues = {}

    def get_message_list(self, pipeline_uuid: str) -> list[WebChatMessage]:
        if pipeline_uuid not in self.message_lists:
            self.message_lists[pipeline_uuid] = []

        return self.message_lists[pipeline_uuid]


class WebChatAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    """WebChat调试适配器，用于流水线调试"""

    webchat_person_session: WebChatSession = pydantic.Field(exclude=True, default_factory=WebChatSession)
    webchat_group_session: WebChatSession = pydantic.Field(exclude=True, default_factory=WebChatSession)

    listeners: dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = pydantic.Field(default_factory=dict, exclude=True)

    is_stream: bool = pydantic.Field(exclude=True)
    debug_messages: dict[str, list[dict]] = pydantic.Field(default_factory=dict, exclude=True)

    ap: app.Application = pydantic.Field(exclude=True)

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger, **kwargs):
        super().__init__(
            config=config,
            logger=logger,
            **kwargs,
        )

        self.webchat_person_session = WebChatSession(id='webchatperson')
        self.webchat_group_session = WebChatSession(id='webchatgroup')

        self.bot_account_id = 'webchatbot'

        self.debug_messages = {}

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

        return message_data

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ) -> dict:
        """回复消息"""
        message_data = WebChatMessage(
            id=-1,
            role='assistant',
            content=str(message),
            message_chain=[component.__dict__ for component in message],
            timestamp=datetime.now().isoformat(),
        )

        # notify waiter
        if isinstance(message_source, platform_events.FriendMessage):
            await self.webchat_person_session.resp_queues[message_source.message_chain.message_id].put(message_data)
        elif isinstance(message_source, platform_events.GroupMessage):
            await self.webchat_group_session.resp_queues[message_source.message_chain.message_id].put(message_data)

        return message_data.model_dump()

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ) -> dict:
        """回复消息"""
        message_data = WebChatMessage(
            id=-1,
            role='assistant',
            content=str(message),
            message_chain=[component.__dict__ for component in message],
            timestamp=datetime.now().isoformat(),
        )

        # notify waiter
        session = (
            self.webchat_group_session
            if isinstance(message_source, platform_events.GroupMessage)
            else self.webchat_person_session
        )
        if message_source.message_chain.message_id not in session.resp_waiters:
            # session.resp_waiters[message_source.message_chain.message_id] = asyncio.Queue()
            queue = session.resp_queues[message_source.message_chain.message_id]

        # if isinstance(message_source, platform_events.FriendMessage):
        #     queue = self.webchat_person_session.resp_queues[message_source.message_chain.message_id]
        # elif isinstance(message_source, platform_events.GroupMessage):
        #     queue = self.webchat_group_session.resp_queues[message_source.message_chain.message_id]
        if is_final and bot_message.tool_calls is None:
            message_data.is_final = True
        # print(message_data)
        await queue.put(message_data)

        return message_data.model_dump()

    async def is_stream_output_supported(self) -> bool:
        return self.is_stream

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        func: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], typing.Awaitable[None]
        ],
    ):
        """注册事件监听器"""
        self.listeners[event_type] = func

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        func: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], typing.Awaitable[None]
        ],
    ):
        """取消注册事件监听器"""
        del self.listeners[event_type]

    async def is_muted(self, group_id: int) -> bool:
        return False

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

    async def send_webchat_message(
        self,
        pipeline_uuid: str,
        session_type: str,
        message_chain_obj: typing.List[dict],
        is_stream: bool = False,
    ) -> dict:
        self.is_stream = is_stream
        """发送调试消息到流水线"""
        if session_type == 'person':
            use_session = self.webchat_person_session
        else:
            use_session = self.webchat_group_session

        message_chain = platform_message.MessageChain.parse_obj(message_chain_obj)

        message_id = len(use_session.get_message_list(pipeline_uuid)) + 1

        use_session.resp_queues[message_id] = asyncio.Queue()
        logger.debug(f'Initialized queue for message_id: {message_id}')

        use_session.get_message_list(pipeline_uuid).append(
            WebChatMessage(
                id=message_id,
                role='user',
                content=str(message_chain),
                message_chain=message_chain_obj,
                timestamp=datetime.now().isoformat(),
            )
        )

        message_chain.insert(0, platform_message.Source(id=message_id, time=datetime.now().timestamp()))

        if session_type == 'person':
            sender = platform_entities.Friend(id='webchatperson', nickname='User', remark='User')
            event = platform_events.FriendMessage(
                sender=sender, message_chain=message_chain, time=datetime.now().timestamp()
            )
        else:
            group = platform_entities.Group(
                id='webchatgroup', name='Group', permission=platform_entities.Permission.Member
            )
            sender = platform_entities.GroupMember(
                id='webchatperson',
                member_name='User',
                group=group,
                permission=platform_entities.Permission.Member,
            )
            event = platform_events.GroupMessage(
                sender=sender, message_chain=message_chain, time=datetime.now().timestamp()
            )

        self.ap.platform_mgr.webchat_proxy_bot.bot_entity.use_pipeline_uuid = pipeline_uuid

        # trigger pipeline
        if event.__class__ in self.listeners:
            await self.listeners[event.__class__](event, self)

        if is_stream:
            queue = use_session.resp_queues[message_id]
            msg_id = len(use_session.get_message_list(pipeline_uuid)) + 1
            while True:
                resp_message = await queue.get()
                resp_message.id = msg_id
                if resp_message.is_final:
                    resp_message.id = msg_id
                    use_session.get_message_list(pipeline_uuid).append(resp_message)
                    yield resp_message.model_dump()
                    break
                yield resp_message.model_dump()
            use_session.resp_queues.pop(message_id)

        else:  # non-stream
            # set waiter
            # waiter = asyncio.Future[WebChatMessage]()
            # use_session.resp_waiters[message_id] = waiter
            # # waiter.add_done_callback(lambda future: use_session.resp_waiters.pop(message_id))
            #
            # resp_message = await waiter
            #
            # resp_message.id = len(use_session.get_message_list(pipeline_uuid)) + 1
            #
            # use_session.get_message_list(pipeline_uuid).append(resp_message)
            #
            # yield resp_message.model_dump()
            msg_id = len(use_session.get_message_list(pipeline_uuid)) + 1

            queue = use_session.resp_queues[message_id]
            resp_message = await queue.get()
            use_session.get_message_list(pipeline_uuid).append(resp_message)
            resp_message.id = msg_id
            resp_message.is_final = True

            yield resp_message.model_dump()

    def get_webchat_messages(self, pipeline_uuid: str, session_type: str) -> list[dict]:
        """获取调试消息历史"""
        if session_type == 'person':
            return [message.model_dump() for message in self.webchat_person_session.get_message_list(pipeline_uuid)]
        else:
            return [message.model_dump() for message in self.webchat_group_session.get_message_list(pipeline_uuid)]
