from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.harness import ws as harness_ws
from langbot.pkg.platform.adapters.harness.adapter import HarnessAdapter
from langbot.pkg.platform.adapters.harness.bindings import bot_uuid_for
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain


class Session:
    def __init__(self, first):
        self.frames = [first]
        self.sent = []

    async def receive_payload(self):
        if not self.frames:
            raise EOFError('closed')
        return self.frames.pop(0)

    async def send_payload(self, payload):
        self.sent.append(payload)

    async def send(self, payload):
        self.sent.append(payload)


class Transport:
    def __init__(self, session):
        self.session = session

    async def handshake(self):
        return self.session


def make_context():
    return SimpleNamespace(workspace_uuid='workspace-1', account_uuid='account-1')


@pytest.mark.asyncio
async def test_ws_rejects_unauthorized_processor(monkeypatch):
    session = Session({'processor_uuid': 'processor-1', 'conversation_id': 'conversation-1', 'content': 'hi'})
    ap = SimpleNamespace()
    monkeypatch.setattr(harness_ws, 'can_use_processor', AsyncMock(return_value=False))
    await harness_ws.handle_ws(ap, Transport(session), make_context())
    assert session.sent == [{'type': 'error', 'code': 'processor_forbidden'}]


@pytest.mark.asyncio
async def test_ws_dispatches_and_replies_on_same_conversation(monkeypatch):
    session = Session({'processor_uuid': 'processor-1', 'conversation_id': 'conversation-1', 'content': 'hello'})
    adapter = HarnessAdapter.model_construct(config={}, logger=SimpleNamespace(), listeners={})

    async def reply_callback(event, _adapter):
        await _adapter.reply_message(event.to_legacy_event(), MessageChain([Plain(text='reply')]))

    callback = AsyncMock(side_effect=reply_callback)
    adapter.register_listener(platform_events.EBAEvent, callback)
    runtime_bot = SimpleNamespace(adapter=adapter)
    persistence = SimpleNamespace(
        execute_async=AsyncMock(
            return_value=SimpleNamespace(first=lambda: SimpleNamespace(user='Ada', normalized_email='ada@example.test'))
        )
    )
    platform_mgr = SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=runtime_bot))
    ap = SimpleNamespace(persistence_mgr=persistence, platform_mgr=platform_mgr)
    monkeypatch.setattr(harness_ws, 'can_use_processor', AsyncMock(return_value=True))

    with pytest.raises(EOFError, match='closed'):
        await harness_ws.handle_ws(ap, Transport(session), make_context())

    platform_mgr.get_bot_by_uuid.assert_awaited_once_with(make_context(), bot_uuid_for('workspace-1', 'processor-1'))
    callback.assert_awaited_once()
    event = callback.await_args.args[0]
    assert event.sender.id == 'account-1'
    assert event.chat_id == 'conversation-1'
    assert session.sent == [{'type': 'message', 'role': 'assistant', 'content': 'reply', 'final': True}]
    assert await adapter.connections.get('conversation-1') is None
