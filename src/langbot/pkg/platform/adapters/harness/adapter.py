"""Minimal EBA adapter lifecycle for authenticated Harness ingress."""

import asyncio

import pydantic
from langbot_plugin.api.definition.abstract.platform.adapter import AbstractPlatformAdapter
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message

from .connection_registry import HarnessConnectionRegistry


class HarnessAdapter(AbstractPlatformAdapter):
    config: dict
    logger: AbstractEventLogger = pydantic.Field(exclude=True)
    listeners: dict = pydantic.Field(default_factory=dict, exclude=True)
    _stopped: asyncio.Event = pydantic.PrivateAttr(default_factory=asyncio.Event)
    _connections: HarnessConnectionRegistry = pydantic.PrivateAttr(default_factory=HarnessConnectionRegistry)

    def __init__(self, config: dict, logger: AbstractEventLogger):
        super().__init__(config=config, logger=logger)

    @property
    def connections(self) -> HarnessConnectionRegistry:
        return self._connections

    def get_supported_events(self) -> list[str]:
        """Only receive standard inbound messages; avoid legacy double dispatch."""
        return ['message.received']

    def register_listener(self, event_type, callback) -> None:
        self.listeners.setdefault(event_type, []).append(callback)

    def unregister_listener(self, event_type, callback) -> None:
        callbacks = self.listeners.get(event_type, [])
        if callback in callbacks:
            callbacks.remove(callback)
        if not callbacks:
            self.listeners.pop(event_type, None)

    async def run_async(self) -> None:
        await self._stopped.wait()

    async def kill(self) -> bool:
        self._stopped.set()
        return True

    def get_launcher_id(self, event) -> str | None:
        """Pipeline dispatch receives a legacy event, so read preserved source metadata."""
        source = getattr(event, 'source_platform_object', None)
        if isinstance(source, dict):
            conversation_id = source.get('harness_session_id')
            if isinstance(conversation_id, str) and conversation_id:
                return conversation_id
        return None

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        raise RuntimeError('Harness proactive messaging is not supported')

    async def reply_message(self, message_source, message: platform_message.MessageChain, quote_origin: bool = False):
        source = getattr(message_source, 'source_platform_object', None)
        connection_id = source.get('harness_connection_id') if isinstance(source, dict) else None
        connection = await self.connections.get(connection_id) if connection_id else None
        if connection is None:
            raise RuntimeError('Harness conversation is not connected')
        await connection.send_payload(
            {
                'type': 'message',
                'role': 'assistant',
                'content': str(message),
                'final': True,
                'conversation_id': source['harness_conversation_id'],
                'processor_uuid': source['harness_processor_uuid'],
            }
        )
        return platform_events.MessageResult(message_id='harness-reply', raw={})
