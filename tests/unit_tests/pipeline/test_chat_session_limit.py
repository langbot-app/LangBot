from __future__ import annotations

import contextlib
from datetime import datetime, timedelta
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import sqlalchemy as sa
import yaml
from langbot_plugin.api.entities.builtin.provider import session as provider_session
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.agent.runner.context_reset import get_reset_generation
from langbot.pkg.agent.runner.persistent_state_store import PersistentStateStore
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.runner_state import RunnerState


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


async def _run_preprocessor(
    mock_app,
    sample_query,
    conversation,
    *,
    expire_time: int | None = 60,
    attach_session: bool = False,
):
    session = provider_session.Session(
        launcher_type=sample_query.launcher_type,
        launcher_id=sample_query.launcher_id,
        sender_id=sample_query.sender_id,
        bot_uuid=sample_query.bot_uuid,
    )
    if attach_session:
        session.using_conversation = conversation
        sample_query.session = session
    mock_app.sess_mgr.get_session = AsyncMock(return_value=session)
    mock_app.sess_mgr.get_conversation = AsyncMock(return_value=conversation)
    mock_app.plugin_connector.emit_event = AsyncMock(return_value=_prompt_preprocessing_context())

    runner = {'id': 'plugin:langbot-team/LocalAgent/default'}
    if expire_time is not None:
        runner['expire-time'] = expire_time
    sample_query.pipeline_config = {
        'ai': {
            'runner': runner,
            'runner_config': {
                'plugin:langbot-team/LocalAgent/default': {
                    'model': {'primary': '', 'fallbacks': []},
                    'prompt': [],
                },
            },
        },
        'trigger': {'misc': {'combine-quote-message': False}},
        'output': {'misc': {'exception-handling': 'show-hint'}},
    }

    result = await _preproc_module().PreProcessor(mock_app).process(sample_query, 'PreProcessor')
    return result, session


@pytest.mark.asyncio
async def test_preprocessor_expires_conversation_from_last_update_time(mock_app, sample_query):
    conversation = _conversation(
        created_at=datetime.now() - timedelta(seconds=10),
        updated_at=datetime.now() - timedelta(seconds=120),
    )

    result, _session = await _run_preprocessor(mock_app, sample_query, conversation)

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

    result, _session = await _run_preprocessor(mock_app, sample_query, conversation)

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
    # Safety settings moved to the bot message policy.
    safety_meta = yaml.safe_load((metadata_dir.parent / 'message-policy' / 'safety.yaml').read_text())

    ai_stage_names = [stage['name'] for stage in ai_meta['stages']]
    assert 'session-limit' not in ai_stage_names
    assert 'session-limit' not in [stage['name'] for stage in safety_meta['stages']]

    runner_stage = next(stage for stage in ai_meta['stages'] if stage['name'] == 'runner')
    expire_time = next(item for item in runner_stage['config'] if item['name'] == 'expire-time')
    assert 'Conversation expire time' in expire_time['label']['en_US']
    assert 'Session validity' not in expire_time['label']['en_US']


_SESSION_CONVERSATION_ID = 'person_12345'
_LEGACY_CONVERSATION_UUID = 'legacy-uuid'
_EXTERNAL_CONVERSATION_ID = 'remote-alice'


class _RunnerStatePersistence:
    def __init__(self, engine):
        self.engine = engine

    def get_db_engine(self):
        return self.engine

    @contextlib.asynccontextmanager
    async def tenant_uow(self, workspace):
        async with self.engine.begin() as conn:
            self.conn = conn
            yield

    async def execute_async(self, statement):
        return await self.conn.execute(statement)


async def _seed_external_conversation(engine, conversation_id: str, external_id: str) -> None:
    from unit_tests.agent.test_state_store import FakeBinding, FakeEventEnvelope, make_descriptor

    store = PersistentStateStore(engine)
    event = FakeEventEnvelope(
        workspace_id='test-workspace',
        bot_id='test-bot-uuid',
        conversation_id=conversation_id,
    )
    await store.apply_update_from_event(
        event,
        FakeBinding(),
        make_descriptor(),
        'conversation',
        'external.conversation_id',
        external_id,
        None,
    )


async def _external_conversation_id(engine, conversation_id: str):
    from unit_tests.agent.test_state_store import FakeBinding, FakeEventEnvelope, make_descriptor

    store = PersistentStateStore(engine)
    event = FakeEventEnvelope(
        workspace_id='test-workspace',
        bot_id='test-bot-uuid',
        conversation_id=conversation_id,
    )
    snapshot = await store.build_snapshot_from_event(event, FakeBinding(), make_descriptor())
    return snapshot['conversation'].get('external.conversation_id')


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('expire_time', 'idle_seconds', 'clears_runner_state'),
    [
        (60, 120, True),
        (0, 120, False),
        (None, 120, False),
        (60, 30, False),
    ],
)
async def test_preprocessor_expire_resets_seeded_runner_state(
    mock_app,
    sample_query,
    tmp_path,
    expire_time,
    idle_seconds,
    clears_runner_state,
):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "runner-state.db"}')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed_external_conversation(engine, _SESSION_CONVERSATION_ID, _EXTERNAL_CONVERSATION_ID)
    await _seed_external_conversation(engine, _LEGACY_CONVERSATION_UUID, 'legacy-remote')
    mock_app.persistence_mgr = _RunnerStatePersistence(engine)

    conversation = _conversation(
        created_at=datetime.now() - timedelta(seconds=idle_seconds + 10),
        updated_at=datetime.now() - timedelta(seconds=idle_seconds),
    )
    conversation.uuid = _LEGACY_CONVERSATION_UUID

    try:
        result, session = await _run_preprocessor(
            mock_app,
            sample_query,
            conversation,
            expire_time=expire_time,
            attach_session=True,
        )
        looked_up = await _external_conversation_id(engine, _SESSION_CONVERSATION_ID)
        legacy = await _external_conversation_id(engine, _LEGACY_CONVERSATION_UUID)
        generation = await get_reset_generation(
            engine,
            'test-workspace',
            'test-bot-uuid',
            _SESSION_CONVERSATION_ID,
        )
        async with engine.connect() as conn:
            remaining_external_rows = (
                await conn.execute(
                    sa.select(RunnerState.state_key).where(
                        RunnerState.workspace_id == 'test-workspace',
                        RunnerState.bot_id == 'test-bot-uuid',
                        RunnerState.conversation_id == _SESSION_CONVERSATION_ID,
                        RunnerState.scope == 'conversation',
                        RunnerState.state_key == 'external.conversation_id',
                    )
                )
            ).all()
    finally:
        await engine.dispose()

    assert result.result_type == _entities_module().ResultType.CONTINUE
    assert legacy == 'legacy-remote'
    if clears_runner_state:
        assert looked_up is None
        assert remaining_external_rows == []
        assert isinstance(generation, str) and generation
        assert session._context_generation == generation
        assert session.using_conversation is None
        assert result.new_query.session.using_conversation is None
        assert conversation.uuid is None
    else:
        assert looked_up == _EXTERNAL_CONVERSATION_ID
        assert remaining_external_rows == [('external.conversation_id',)]
        assert generation is None
        assert getattr(session, '_context_generation', None) is None
        assert session.using_conversation is conversation
        assert conversation.uuid == _LEGACY_CONVERSATION_UUID
