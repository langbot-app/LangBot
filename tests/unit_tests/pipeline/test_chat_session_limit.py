from __future__ import annotations

from datetime import datetime, timedelta
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import yaml


def _preproc_module():
    # Import pipelinemgr first so pipeline stages are registered without tripping
    # the stage <-> core.app circular import during isolated test collection.
    import_module('langbot.pkg.pipeline.pipelinemgr')
    return import_module('langbot.pkg.pipeline.preproc.preproc')


def _entities_module():
    return import_module('langbot.pkg.pipeline.entities')


def _conversation(created_at: datetime, updated_at: datetime | None = None):
    prompt = Mock()
    prompt.messages = []
    prompt.copy = Mock(return_value=Mock(messages=[]))

    return SimpleNamespace(
        uuid='existing-conversation-uuid',
        create_time=created_at,
        update_time=updated_at,
        prompt=prompt,
        messages=[],
    )


def _prompt_preprocessing_context(default_prompt=None, prompt=None):
    ctx = Mock()
    ctx.event.default_prompt = default_prompt or []
    ctx.event.prompt = prompt or []
    return ctx


async def _run_preprocessor(mock_app, sample_query, conversation):
    session = SimpleNamespace(launcher_type=sample_query.launcher_type, launcher_id=sample_query.launcher_id)
    mock_app.sess_mgr.get_session = AsyncMock(return_value=session)
    mock_app.sess_mgr.get_conversation = AsyncMock(return_value=conversation)
    mock_app.plugin_connector.emit_event = AsyncMock(return_value=_prompt_preprocessing_context())

    sample_query.pipeline_config = {
        'ai': {
            'runner': {'runner': 'local-agent', 'expire-time': 60},
            'local-agent': {'model': {'primary': '', 'fallbacks': []}, 'prompt': []},
        },
        'trigger': {'misc': {'combine-quote-message': False}},
        'output': {'misc': {'exception-handling': 'show-hint'}},
    }

    return await _preproc_module().PreProcessor(mock_app).process(sample_query, 'PreProcessor')


@pytest.mark.asyncio
async def test_preprocessor_expires_conversation_from_last_update_time(mock_app, sample_query):
    conversation = _conversation(
        created_at=datetime.now() - timedelta(seconds=10),
        updated_at=datetime.now() - timedelta(seconds=120),
    )

    result = await _run_preprocessor(mock_app, sample_query, conversation)

    assert result.result_type == _entities_module().ResultType.CONTINUE
    assert conversation.uuid is None
    assert conversation.update_time > datetime.now() - timedelta(seconds=5)
    assert result.new_query.variables['conversation_id'] is None


@pytest.mark.asyncio
async def test_preprocessor_keeps_conversation_when_last_update_is_not_expired(mock_app, sample_query):
    conversation = _conversation(
        created_at=datetime.now() - timedelta(seconds=120),
        updated_at=datetime.now() - timedelta(seconds=30),
    )

    result = await _run_preprocessor(mock_app, sample_query, conversation)

    assert result.result_type == _entities_module().ResultType.CONTINUE
    assert conversation.uuid == 'existing-conversation-uuid'
    assert conversation.update_time > datetime.now() - timedelta(seconds=5)
    assert result.new_query.variables['conversation_id'] == 'existing-conversation-uuid'


def test_expire_time_metadata_lives_under_ai_runner_not_safety():
    # Use path relative to test file location for portability
    # test file: tests/unit_tests/pipeline/test_chat_session_limit.py
    # project root: 4 levels up
    project_root = Path(__file__).parent.parent.parent.parent
    metadata_dir = project_root / 'src' / 'langbot' / 'templates' / 'metadata' / 'pipeline'

    ai_meta = yaml.safe_load((metadata_dir / 'ai.yaml').read_text())
    safety_meta = yaml.safe_load((metadata_dir / 'safety.yaml').read_text())

    ai_stage_names = [stage['name'] for stage in ai_meta['stages']]
    assert 'session-limit' not in ai_stage_names
    assert 'session-limit' not in [stage['name'] for stage in safety_meta['stages']]

    runner_stage = next(stage for stage in ai_meta['stages'] if stage['name'] == 'runner')
    expire_time = next(item for item in runner_stage['config'] if item['name'] == 'expire-time')
    assert 'Conversation expire time' in expire_time['label']['en_US']
    assert 'Session validity' not in expire_time['label']['en_US']
