from __future__ import annotations

from datetime import datetime, timedelta
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import yaml

import langbot_plugin.api.entities.builtin.provider.message as provider_message


def _chat_module():
    # Import pipelinemgr first so pipeline stages are registered without tripping the
    # process.handler <-> core.app circular import during isolated test collection.
    import_module('langbot.pkg.pipeline.pipelinemgr')
    return import_module('langbot.pkg.pipeline.process.handlers.chat')


def _entities_module():
    return import_module('langbot.pkg.pipeline.entities')


def _runner_module():
    _chat_module()
    return import_module('langbot.pkg.provider.runner')


class DummyRunner:
    name = 'local-agent'

    def __init__(self, ap, pipeline_config):
        self.ap = ap
        self.pipeline_config = pipeline_config

    async def run(self, query):
        yield provider_message.Message(role='assistant', content='ok')


def _event_context():
    ctx = Mock()
    ctx.is_prevented_default.return_value = False
    ctx.event.reply_message_chain = None
    ctx.event.user_message_alter = None
    return ctx


def _conversation(created_at: datetime):
    return SimpleNamespace(
        uuid='existing-conversation-uuid',
        create_time=created_at,
        messages=[],
    )


@pytest.mark.asyncio
async def test_chat_handler_expires_conversation_from_ai_session_limit(monkeypatch, mock_app, sample_query):
    monkeypatch.setattr(_runner_module(), 'preregistered_runners', [DummyRunner])
    mock_app.plugin_connector.emit_event = AsyncMock(return_value=_event_context())

    conversation = _conversation(datetime.now() - timedelta(seconds=120))
    sample_query.session = SimpleNamespace(using_conversation=conversation)
    sample_query.user_message = provider_message.Message(role='user', content='hello')
    sample_query.pipeline_config = {
        'ai': {
            'runner': {'runner': 'local-agent'},
            'session-limit': {'expire-time': 60},
        },
        'output': {'misc': {'exception-handling': 'show-hint'}},
    }

    results = [result async for result in _chat_module().ChatMessageHandler(mock_app).handle(sample_query)]

    assert results
    assert results[0].result_type == _entities_module().ResultType.CONTINUE
    assert conversation.uuid is None


@pytest.mark.asyncio
async def test_chat_handler_ignores_safety_session_limit(monkeypatch, mock_app, sample_query):
    monkeypatch.setattr(_runner_module(), 'preregistered_runners', [DummyRunner])
    mock_app.plugin_connector.emit_event = AsyncMock(return_value=_event_context())

    conversation = _conversation(datetime.now() - timedelta(seconds=120))
    sample_query.session = SimpleNamespace(using_conversation=conversation)
    sample_query.user_message = provider_message.Message(role='user', content='hello')
    sample_query.pipeline_config = {
        'ai': {'runner': {'runner': 'local-agent'}},
        'safety': {'session-limit': {'expire-time': 60}},
        'output': {'misc': {'exception-handling': 'show-hint'}},
    }

    results = [result async for result in _chat_module().ChatMessageHandler(mock_app).handle(sample_query)]

    assert results
    assert results[0].result_type == _entities_module().ResultType.CONTINUE
    assert conversation.uuid == 'existing-conversation-uuid'


def test_session_limit_metadata_lives_under_ai_not_safety():
    metadata_dir = Path('src/langbot/templates/metadata/pipeline')

    ai_meta = yaml.safe_load((metadata_dir / 'ai.yaml').read_text())
    safety_meta = yaml.safe_load((metadata_dir / 'safety.yaml').read_text())

    assert 'session-limit' in [stage['name'] for stage in ai_meta['stages']]
    assert 'session-limit' not in [stage['name'] for stage in safety_meta['stages']]
