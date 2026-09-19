"""Execute real Core boundaries with content canaries and early failures."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from langbot.pkg.telemetry import diagnostics as d
from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.agent.runner.orchestrator import AgentRunOrchestrator
from langbot.pkg.agent.runner.reply_stream import ReplyStreamSession, ReplyStreamRequest


def make_ap():
    ap = SimpleNamespace(instance_config=SimpleNamespace(data={'space': {'url': 'https://example.invalid'}}))
    ap.persistence_mgr = SimpleNamespace(get_db_engine=lambda: None)
    ap.diagnostics = d.DiagnosticsManager(ap, version='4.11.0b2', instance_id='instance-test')
    return ap


@pytest.mark.asyncio
@pytest.mark.parametrize('processor', ['pipeline', 'agent', 'event_processor'])
async def test_real_orchestrator_prepare_failure(processor):
    ap = make_ap()
    registry = SimpleNamespace(get=AsyncMock(side_effect=ValueError('CANARY private runner URL')))
    orchestrator = AgentRunOrchestrator(ap, registry)
    context = ExecutionContext(instance_uuid='instance-test', workspace_uuid=str(uuid4()), placement_generation=1)
    event = SimpleNamespace(workspace_id=context.workspace_uuid, event_type='message.received')
    binding = SimpleNamespace(runner_id='CANARY', processor_type=processor)
    with pytest.raises(ValueError, match='CANARY'):
        await anext(orchestrator.run(event, binding, adapter_context={'_execution_context': context}))
    records = ap.diagnostics.pending
    assert [r['outcome'] for r in records] == ['started', 'failed']
    assert records[-1]['stage'] == 'prepare'
    assert records[-1]['workspace_uuid'] == context.workspace_uuid
    assert records[-1]['processor_type'] == processor
    assert 'CANARY' not in json.dumps(records)


@pytest.mark.asyncio
async def test_real_reply_stream_mock_is_not_platform_success():
    ap = make_ap()
    event = SimpleNamespace(
        delivery=SimpleNamespace(reply_target={}, surface='webui', platform_capabilities={'debug_mock': True})
    )
    session = ReplyStreamSession(event)
    # Real runtime supplies the manager at construction from the orchestrator.
    session.diagnostics = ap.diagnostics
    result = await session.apply(ReplyStreamRequest(stream_id=uuid4(), operation='finish', text='CANARY user reply'))
    assert result['mock'] is True and result['text'] == 'CANARY user reply'
    assert ap.diagnostics.pending[-1]['source'] == 'webui_debug'
    assert ap.diagnostics.pending[-1]['attributes']['synthetic'] is True
    assert 'CANARY' not in json.dumps(ap.diagnostics.pending)


@pytest.mark.asyncio
async def test_real_bot_route_projects_status_not_reason():
    from langbot.pkg.platform.botmgr import RuntimeBot

    ap = make_ap()
    bot = object.__new__(RuntimeBot)
    bot.ap = ap
    bot.logger = SimpleNamespace(info=AsyncMock())
    await bot._record_event_route_trace(
        event_type='message.received',
        status='not_matched',
        text='CANARY secret',
        reason='CANARY',
        failure_code='route_not_found',
    )
    records = ap.diagnostics.pending
    assert records[-1]['outcome'] == 'skipped'
    assert records[-1]['reason_code'] == 'route_not_found'
    assert 'CANARY' not in json.dumps(records)


@pytest.mark.asyncio
async def test_real_telegram_conversion_failure_before_bot_manager(monkeypatch):
    from langbot.pkg.platform.adapters.telegram.adapter import TelegramAdapter
    from langbot.pkg.platform.adapters.telegram.event_converter import TelegramEventConverter

    ap = make_ap()
    context = ExecutionContext(instance_uuid='instance-test', workspace_uuid=str(uuid4()), placement_generation=1)
    from langbot.pkg.platform.logger import EventLogger

    logger = EventLogger('test', ap, context, 'test')
    logger.error = AsyncMock()
    logger.warning = AsyncMock()
    adapter = TelegramAdapter({'token': '123456:ABCDEFGHIJKLMNOPQRSTUVWXYZ_123456789'}, logger)
    adapter.listeners = {}
    monkeypatch.setattr(
        TelegramEventConverter, '_convert_message', AsyncMock(side_effect=ValueError('CANARY conversion'))
    )
    update = SimpleNamespace(
        message=SimpleNamespace(from_user=SimpleNamespace(is_bot=False), text='CANARY text'),
        edited_message=None,
        chat_member=None,
        my_chat_member=None,
        callback_query=None,
        message_reaction=None,
    )
    callback = adapter.application.handlers[0][0].callback
    await callback(update, None)
    records = [e for e in ap.diagnostics.pending if e['stage'] == 'convert' and e['outcome'] == 'failed']
    assert records and records[-1]['adapter'] == 'telegram-omni'
    assert records[-1]['workspace_uuid'] == context.workspace_uuid
    assert 'CANARY' not in json.dumps(ap.diagnostics.pending)


@pytest.mark.asyncio
async def test_real_interaction_ack_skip_and_failure():
    from langbot.pkg.agent.runner.interaction_manager import InteractionManager

    ap = make_ap()
    interactions = InteractionManager(ap, store=SimpleNamespace(record_delivery_success=AsyncMock()))
    await interactions.acknowledge_submission({}, SimpleNamespace(get_supported_apis=lambda: []))
    assert ap.diagnostics.pending[-1]['outcome'] == 'skipped'
    ap.diagnostics.pending.clear()
    ap.logger = SimpleNamespace(warning=lambda *a: None)
    adapter = SimpleNamespace(
        get_supported_apis=lambda: ['interaction.acknowledge'],
        call_platform_api=AsyncMock(side_effect=ValueError('CANARY ack')),
    )
    await interactions.acknowledge_submission({'delivery_result': {'secret': 'CANARY'}}, adapter)
    assert ap.diagnostics.pending[-1]['outcome'] == 'failed'
    assert 'CANARY' not in json.dumps(ap.diagnostics.pending)


def test_actual_adapter_capability_snapshot():
    from langbot.pkg.platform.adapters.telegram.adapter import TelegramAdapter
    from langbot.pkg.telemetry.diagnostic_catalog import snapshot_bot

    ap = make_ap()
    context = ExecutionContext(instance_uuid='instance-test', workspace_uuid=str(uuid4()), placement_generation=1)
    adapter = TelegramAdapter.model_construct(config={}, listeners={})
    snapshot_bot(SimpleNamespace(ap=ap, adapter=adapter, execution_context=context))
    records = ap.diagnostics.pending
    assert records and all(e['kind'] == 'capability' for e in records)
    api_rows = [e for e in records if e['attributes']['capability_type'] == 'api']
    assert any(e['operation'] == 'send_message' and e['attributes']['supported'] for e in api_rows)
    assert all(e['workspace_uuid'] == context.workspace_uuid for e in records)
