from __future__ import annotations

import pathlib

import pytest
import yaml
from telegram.ext import CallbackQueryHandler, ChatMemberHandler, MessageHandler, MessageReactionHandler

from langbot.pkg.platform.adapters.telegram.adapter import TelegramAdapter
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class DummyLogger(AbstractEventLogger):
    async def info(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def debug(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def warning(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def error(self, text, images=None, message_session_id=None, no_throw=True):
        pass


def make_adapter() -> TelegramAdapter:
    return TelegramAdapter(
        {
            'token': '123456:ABCDEF_fake_token_for_object_parsing',
            'markdown_card': False,
            'enable-stream-reply': False,
        },
        DummyLogger(),
    )


def test_telegram_adapter_registers_all_declared_update_handlers():
    adapter = make_adapter()

    handlers = adapter.application.handlers[0]

    assert sum(isinstance(handler, MessageHandler) for handler in handlers) == 2
    assert sum(isinstance(handler, ChatMemberHandler) for handler in handlers) == 2
    assert any(isinstance(handler, CallbackQueryHandler) for handler in handlers)
    assert any(isinstance(handler, MessageReactionHandler) for handler in handlers)


@pytest.mark.asyncio
async def test_telegram_adapter_dispatches_only_most_specific_eba_listener():
    adapter = make_adapter()
    calls: list[str] = []

    async def wildcard_listener(event, adapter):
        calls.append('event')

    async def eba_listener(event, adapter):
        calls.append('eba')

    async def message_listener(event, adapter):
        calls.append('message.received')

    adapter.register_listener(platform_events.Event, wildcard_listener)
    adapter.register_listener(platform_events.EBAEvent, eba_listener)
    adapter.register_listener(platform_events.MessageReceivedEvent, message_listener)

    event = platform_events.MessageReceivedEvent(
        message_id=1,
        message_chain=platform_message.MessageChain([platform_message.Plain(text='hello')]),
        sender=platform_entities.User(id=1),
        chat_id=1,
    )

    await adapter._dispatch_eba_event(event)

    assert calls == ['message.received']


@pytest.mark.asyncio
async def test_telegram_adapter_dispatch_falls_back_to_eba_then_event_listener():
    adapter = make_adapter()
    calls: list[str] = []

    async def wildcard_listener(event, adapter):
        calls.append('event')

    async def eba_listener(event, adapter):
        calls.append('eba')

    adapter.register_listener(platform_events.Event, wildcard_listener)
    adapter.register_listener(platform_events.EBAEvent, eba_listener)

    event = platform_events.MessageEditedEvent(
        message_id=1,
        new_content=platform_message.MessageChain([platform_message.Plain(text='edited')]),
        editor=platform_entities.User(id=1),
        chat_id=1,
    )

    await adapter._dispatch_eba_event(event)
    assert calls == ['eba']

    adapter.unregister_listener(platform_events.EBAEvent, eba_listener)
    await adapter._dispatch_eba_event(event)
    assert calls == ['eba', 'event']


def test_telegram_supported_events_match_manifest():
    adapter_events = make_adapter().get_supported_events()
    manifest_path = (
        pathlib.Path(__file__).parents[3]
        / 'src'
        / 'langbot'
        / 'pkg'
        / 'platform'
        / 'adapters'
        / 'telegram'
        / 'manifest.yaml'
    )
    manifest_events = yaml.safe_load(manifest_path.read_text())['spec']['supported_events']

    assert adapter_events == manifest_events
    assert 'message.deleted' not in adapter_events
    assert 'group.info_updated' not in adapter_events
