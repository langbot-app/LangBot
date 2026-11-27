from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.harness import ws
from langbot.pkg.platform.adapters.harness.adapter import HarnessAdapter
from langbot.pkg.platform.adapters.harness.bindings import processor_bot_config
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
async def test_processor_bots_route_per_message_and_isolate_replies(monkeypatch):
    events = []

    async def dispatch(event, adapter, *, harness_route):
        events.append((event, harness_route))
        await adapter.reply_message(event.to_legacy_event(), MessageChain([Plain(text=str(event.sender.id))]))

    bots = {}
    for processor in ('agent-a', 'agent-b'):
        bot = object.__new__(RuntimeBot)
        bot.workspace_uuid = 'workspace'
        bot.bot_entity = SimpleNamespace(**processor_bot_config(bot.workspace_uuid, processor))
        bot.enable = True
        bot.adapter = HarnessAdapter.model_construct(config={}, logger=SimpleNamespace(), listeners={})
        bot.ap = SimpleNamespace(
            workspace_service=SimpleNamespace(
                get_execution_binding=AsyncMock(return_value=SimpleNamespace(instance_uuid='instance'))
            )
        )
        bot.execution_context = SimpleNamespace(instance_uuid='instance')
        bot.placement_generation = 1
        bot._handle_platform_event = dispatch
        bots[processor] = bot
    monkeypatch.setattr('langbot.pkg.platform.botmgr.get_workspace_language', AsyncMock(return_value='en_US'))
    policy = AsyncMock(side_effect=[True, True, False, True])
    monkeypatch.setattr(ws, 'can_use_processor', policy)
    lookup = AsyncMock(side_effect=lambda _, processor: bots[processor])
    ap = SimpleNamespace(
        bot_service=SimpleNamespace(ensure_harness_processor_bot=lookup),
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
            await ws.handle_ws(
                ap, socket, SimpleNamespace(workspace_uuid='workspace', account_uuid=account, auth_type='user-token')
            )

    assert policy.await_count == 4
    assert [call.args[1] for call in lookup.await_args_list] == ['agent-a', 'agent-b', 'agent-a']
    assert bots['agent-a'].bot_entity.uuid != bots['agent-b'].bot_entity.uuid
    assert [route['target_uuid'] for _, route in events] == ['agent-a', 'agent-b', 'agent-a']
    assert len({event.chat_id for event, _ in events}) == 3
    assert [(p['conversation_id'], p['processor_uuid'], p['content']) for p in first.sent[:2]] == [
        ('same', 'agent-a', 'alice'),
        ('same', 'agent-b', 'alice'),
    ]
    assert first.sent[2] == {'type': 'error', 'code': 'processor_forbidden'}
    assert [p['content'] for p in second.sent] == ['bob']
    with pytest.raises(RuntimeError, match='not connected'):
        await bots['agent-a'].adapter.reply_message(events[0][0].to_legacy_event(), MessageChain([Plain(text='late')]))


async def test_harness_oauth_read_only_scope_does_not_provision():
    ctx = SimpleNamespace(
        workspace_uuid='workspace', auth_type='harness-oauth', workspace=SimpleNamespace(permissions={'workspace.view'})
    )
    socket = Session('agent-a')
    with pytest.raises(EOFError):
        await ws.handle_ws(None, socket, ctx)
    assert socket.sent == [{'type': 'error', 'code': 'processor_forbidden'}]
