from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.harness import ws
from langbot.pkg.platform.adapters.harness.adapter import HarnessAdapter
from langbot.pkg.platform.adapters.harness.bindings import workspace_bot_config, workspace_bot_uuid
from langbot.pkg.platform.botmgr import RuntimeBot
from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain


class Session:
    def __init__(self, *processors):
        self.frames = iter(dict(processor_uuid=p, conversation_id='same', content='hi') for p in processors)
        self.sent = []

    async def receive_payload(self):
        frame = next(self.frames, None)
        if frame is None:
            raise EOFError
        return frame

    async def send_payload(self, payload):
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_shared_bot_routes_per_message_and_isolates_replies(monkeypatch):
    bot = object.__new__(RuntimeBot)
    bot.workspace_uuid = 'workspace'
    bot.bot_entity = SimpleNamespace(**workspace_bot_config(bot.workspace_uuid))
    bot.enable = True
    bot.adapter = HarnessAdapter.model_construct(config={}, logger=SimpleNamespace(), listeners={})
    bot.ap = SimpleNamespace()
    bot.ap.workspace_service = SimpleNamespace(
        get_execution_binding=AsyncMock(return_value=SimpleNamespace(instance_uuid='instance'))
    )
    bot.execution_context = SimpleNamespace(instance_uuid='instance')
    bot.placement_generation = 1
    events = []

    async def dispatch(event, adapter, *, harness_route):
        events.append((event, harness_route))
        await adapter.reply_message(event.to_legacy_event(), MessageChain([Plain(text=str(event.sender.id))]))

    bot._handle_platform_event = dispatch
    monkeypatch.setattr('langbot.pkg.platform.botmgr.get_workspace_language', AsyncMock(return_value='en_US'))
    policy = AsyncMock(side_effect=[True, True, False, True])
    monkeypatch.setattr(ws, 'can_use_processor', policy)
    lookup = AsyncMock(return_value=bot)
    ap = SimpleNamespace(
        platform_mgr=SimpleNamespace(get_bot_by_uuid=lookup),
        persistence_mgr=SimpleNamespace(
            execute_async=AsyncMock(
                return_value=SimpleNamespace(
                    first=lambda: SimpleNamespace(user='Member', normalized_email='member@example.test')
                )
            )
        ),
    )
    first, second = Session('agent-a', 'agent-b', 'agent-a'), Session('agent-a')
    for account, socket in [('alice', first), ('bob', second)]:
        with pytest.raises(EOFError):
            await ws.handle_ws(ap, socket, SimpleNamespace(workspace_uuid='workspace', account_uuid=account))

    assert policy.await_count == 4
    assert {call.args[1] for call in lookup.await_args_list} == {workspace_bot_uuid('workspace')}
    assert [route['target_uuid'] for _, route in events] == ['agent-a', 'agent-b', 'agent-a']
    assert len({event.chat_id for event, _ in events}) == 3
    assert [(p['conversation_id'], p['processor_uuid'], p['content']) for p in first.sent[:2]] == [
        ('same', 'agent-a', 'alice'),
        ('same', 'agent-b', 'alice'),
    ]
    assert first.sent[2] == {'type': 'error', 'code': 'processor_forbidden'}
    assert [p['content'] for p in second.sent] == ['bob']
    with pytest.raises(RuntimeError, match='not connected'):
        await bot.adapter.reply_message(events[0][0].to_legacy_event(), MessageChain([Plain(text='late')]))
