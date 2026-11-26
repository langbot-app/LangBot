import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.discover.engine import ComponentDiscoveryEngine
from langbot.pkg.platform.adapters.harness.adapter import HarnessAdapter
from langbot.pkg.platform.adapters.harness.event_converter import build_event
from langbot_plugin.api.entities.builtin.platform import events as platform_events


def test_harness_manifest_discovery_exposes_only_message_received():
    component = ComponentDiscoveryEngine(None).load_component_manifest(
        'pkg/platform/adapters/harness/manifest.yaml', no_save=True
    )
    assert component is not None
    assert component.metadata.name == 'harness-omni'
    assert component.spec['supported_events'] == ['message.received']
    assert component.execution.python.attr == 'HarnessAdapter'
    assert component.get_python_component_class() is HarnessAdapter


def test_event_keeps_harness_conversation_in_legacy_source_metadata():
    event = build_event(
        {'conversation_id': 'conversation-123', 'content': 'hello'},
        {'account_uuid': 'account-456', 'display_name': 'Ada Lovelace', 'email': 'ada@example.test'},
    )
    legacy_event = event.to_legacy_event()
    assert event.type == 'message.received'
    assert event.chat_id == 'conversation-123'
    assert event.sender.id == 'account-456'
    assert event.sender.nickname == 'Ada Lovelace'
    assert legacy_event.source_platform_object == {'harness_conversation_id': 'conversation-123'}


def test_get_launcher_id_reads_legacy_source_platform_object():
    adapter = HarnessAdapter.model_construct(config={}, logger=SimpleNamespace(), listeners={})
    event = SimpleNamespace(source_platform_object={'harness_conversation_id': 'conversation-123'})
    assert adapter.get_launcher_id(event) == 'conversation-123'
    assert adapter.get_launcher_id(SimpleNamespace(source_platform_object=None)) is None


@pytest.mark.asyncio
async def test_lifecycle_waits_until_kill_and_ingress_dispatches_eba_only():
    adapter = HarnessAdapter.model_construct(config={}, logger=SimpleNamespace(), listeners={})
    assert adapter.get_supported_events() == ['message.received']
    callback = AsyncMock()
    adapter.register_listener(platform_events.EBAEvent, callback)
    run_task = asyncio.create_task(adapter.run_async())
    await adapter.ingest_frame(
        {'conversation_id': 'conv', 'content': 'hi'},
        {'account_uuid': 'account', 'display_name': 'Person'},
    )
    callback.assert_awaited_once()
    assert isinstance(callback.await_args.args[0], platform_events.MessageReceivedEvent)
    await adapter.kill()
    await run_task
