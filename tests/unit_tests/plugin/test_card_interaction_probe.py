"""The local card probe uses event-processor tools and typed callbacks."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot_plugin.api.entities.builtin.platform.events import MessageReceivedEvent, PlatformSpecificEvent
from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain
from langbot_plugin.api.entities.builtin.runner.interaction import InteractionSubmission


PLUGIN_RUNNER = (
    Path(__file__).resolve().parents[3]
    / 'tests'
    / 'fixtures'
    / 'card-interaction-probe'
    / 'components'
    / 'runner'
    / 'default.py'
)
spec = importlib.util.spec_from_file_location('card_interaction_probe', PLUGIN_RUNNER)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CardInteractionProbe = module.CardInteractionProbe


@pytest.mark.asyncio
async def test_probe_sends_card_only_for_its_command():
    runner = CardInteractionProbe()
    await runner.initialize()
    call_tool = AsyncMock(return_value={'ok': True, 'interaction_id': 'card-1'})
    ctx = SimpleNamespace(
        platform_event=MessageReceivedEvent(message_chain=MessageChain([Plain(text='hello')])),
        call_tool=call_tool,
    )

    await runner.run(ctx)
    call_tool.assert_not_awaited()

    ctx.platform_event = MessageReceivedEvent(message_chain=MessageChain([Plain(text='/card-probe')]))
    await runner.run(ctx)
    call_tool.assert_awaited_once()
    name, parameters = call_tool.await_args.args
    assert name == 'present_interactive_card'
    assert [action['id'] for action in parameters['actions']] == ['approve', 'reject']


@pytest.mark.asyncio
async def test_probe_handles_typed_interaction_submission():
    runner = CardInteractionProbe()
    await runner.initialize()
    reply = AsyncMock()
    ctx = SimpleNamespace(
        platform_event=PlatformSpecificEvent(action='interaction.submitted'),
        input=SimpleNamespace(
            interaction=InteractionSubmission(interaction_id='card-1', action_id='approve', values={})
        ),
        reply=reply,
    )

    await runner.run(ctx)
    reply.assert_awaited_once_with('Card result: approve')
