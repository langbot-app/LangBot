"""The Chat handler must not emit the legacy per-query telemetry payload.

Per-execution telemetry is produced by the trace that owns the Pipeline lane;
the handler only annotates that trace with execution-scoped record fields.
"""

from __future__ import annotations

import types
from importlib import import_module
from unittest.mock import AsyncMock, Mock

import langbot_plugin.api.entities.builtin.provider.session as provider_session


def get_modules():
    # Import the application package first: the handler package is wired into
    # it during initialization, so importing the handler directly would re-enter
    # the partially initialized pipeline package.
    import_module('langbot.pkg.core.app')
    return (
        import_module('langbot.pkg.pipeline.process.handlers.chat'),
        import_module('langbot.pkg.telemetry.trace'),
    )


class FakeEvent:
    """Stand-in for the plugin event models, which need a real Query."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.event_name = 'person_normal_message_received'


class FakeEventContext:
    event = types.SimpleNamespace(user_message_alter=None)

    def is_prevented_default(self) -> bool:
        return False


async def empty_run_from_query(query):
    if False:  # pragma: no cover - async generator with no results
        yield


def build_ap():
    ap = Mock()
    ap.logger = Mock()
    ap.plugin_connector = Mock()
    ap.plugin_connector.emit_event = AsyncMock(return_value=FakeEventContext())
    ap.agent_run_orchestrator = Mock()
    ap.agent_run_orchestrator.try_claim_steering_from_query = AsyncMock(return_value=False)
    ap.agent_run_orchestrator.run_from_query = empty_run_from_query
    ap.agent_run_orchestrator.resolve_runner_id_for_telemetry = Mock(return_value='runner-1')
    ap.survey = Mock()
    ap.survey.trigger_event = AsyncMock()
    ap.survey.record_bot_response_success = AsyncMock()
    ap.telemetry = Mock()
    ap.telemetry.start_send_task = AsyncMock()
    ap.telemetry.send = AsyncMock()
    return ap


def build_query():
    query = Mock()
    query.query_id = 7
    query.query_uuid = 'exec-uuid'
    query.launcher_type = provider_session.LauncherTypes.PERSON
    query.launcher_id = 'user-1'
    query.sender_id = 'user-1'
    query.message_chain = 'hello'
    query.message_event = object()
    query.variables = {'_pipeline_bound_plugins': ['plugin:a']}
    query.pipeline_config = {'ai': {}, 'output': {'misc': {}}}
    query.session = Mock(using_conversation=object())
    query.use_llm_model_uuid = None
    query.adapter = Mock()
    query.adapter.is_stream_output_supported = AsyncMock(return_value=False)
    query.resp_messages = []
    return query


async def test_normal_query_sends_no_legacy_payload_and_annotates_the_trace(monkeypatch):
    chat, trace_mod = get_modules()
    monkeypatch.setattr(chat.events, 'PersonNormalMessageReceived', FakeEvent)
    monkeypatch.setattr(chat.events, 'GroupNormalMessageReceived', FakeEvent)

    ap = build_ap()
    handler = chat.ChatMessageHandler(ap)
    query = build_query()

    binding = trace_mod.bind('exec-uuid')
    try:
        async for _ in handler.handle(query):
            pass
    finally:
        trace_mod.unbind_root(binding)

    # The legacy `event_type='query'` emitter is gone.
    ap.telemetry.start_send_task.assert_not_called()
    ap.telemetry.send.assert_not_called()
    # The survey trigger and its milestone bookkeeping still fire.
    ap.survey.trigger_event.assert_awaited_once_with('first_bot_response_success')
    ap.survey.record_bot_response_success.assert_awaited_once()
    # Execution-scoped fields are attached to the owning trace instead.
    assert binding.state.runner == 'runner-1'
    assert binding.state.runner_category == 'unknown'
    assert binding.state.pipeline_plugins == ['plugin:a']
    assert binding.state.model_name == ''
