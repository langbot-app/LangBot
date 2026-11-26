"""Minimal EBA adapter lifecycle for authenticated Harness ingress."""

import asyncio

import pydantic
from langbot_plugin.api.definition.abstract.platform.adapter import AbstractPlatformAdapter
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message

from .event_converter import build_event


class HarnessAdapter(AbstractPlatformAdapter):
    config: dict
    logger: AbstractEventLogger = pydantic.Field(exclude=True)
    listeners: dict = pydantic.Field(default_factory=dict, exclude=True)
    _stopped: asyncio.Event = pydantic.PrivateAttr(default_factory=asyncio.Event)

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

    async def ingest_frame(self, frame: dict, identity: dict[str, str]) -> None:
        """Convert one authenticated frame and notify registered EBA listeners."""
        event = build_event(frame, identity)
        for callback in tuple(self.listeners.get(platform_events.EBAEvent, ())):
            await callback(event, self)

    def get_launcher_id(self, event) -> str | None:
        """Pipeline dispatch receives a legacy event, so read preserved source metadata."""
        source = getattr(event, 'source_platform_object', None)
        if isinstance(source, dict):
            conversation_id = source.get('harness_conversation_id')
            if isinstance(conversation_id, str) and conversation_id:
                return conversation_id
        return None

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        raise RuntimeError('Harness outbound transport is not connected')

    async def reply_message(self, message_source, message: platform_message.MessageChain, quote_origin: bool = False):
        raise RuntimeError('Harness outbound transport is not connected')
