import contextlib
import datetime
import json
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.service.monitoring import MonitoringService
from langbot.pkg.agent.runner.context_reset import get_reset_generation
from langbot.pkg.agent.runner.transcript_store import TranscriptStore
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.monitoring import MonitoringSession
from langbot.pkg.entity.persistence.runner_state import RunnerState
from langbot.pkg.entity.persistence.agent_run import AgentRun
from langbot.pkg.entity.persistence.transcript import Transcript


class Persistence:
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


@pytest.fixture
async def context_service(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "reset.db"}')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            sa.insert(MonitoringSession).values(
                workspace_uuid='w',
                bot_id='b',
                session_id='person_u',
                bot_name='Bot',
                pipeline_id='p',
                pipeline_name='Pipeline',
                start_time=datetime.datetime.utcnow(),
                last_activity=datetime.datetime.utcnow(),
            )
        )
        for workspace, bot, conversation, scope in [
            ('w', 'b', 'person_u', 'conversation'),
            ('w', 'b2', 'person_u', 'conversation'),
            ('w2', 'b', 'person_u', 'conversation'),
            ('w', 'b', 'person_other', 'conversation'),
            ('w', 'b', 'person_u', 'actor'),
        ]:
            await conn.execute(
                sa.insert(RunnerState).values(
                    workspace_id=workspace,
                    bot_id=bot,
                    conversation_id=conversation,
                    scope=scope,
                    scope_key=f'{workspace}:{bot}:{conversation}:{scope}',
                    state_key='checkpoint',
                    runner_id='runner',
                    binding_identity='binding',
                    value_json=json.dumps('old'),
                )
            )
    yield MonitoringService(SimpleNamespace(persistence_mgr=Persistence(engine))), engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_reset_preserves_logs_and_isolates_context(context_service):
    service, engine = context_service
    store = TranscriptStore(engine)
    for bot in ['b', 'b2']:
        await store.append_transcript(None, 'event', 'person_u', 'user', bot_id=bot, workspace_id='w', content='old')
    await service.reset_session_context('w', 'b', 'person_u')
    assert await get_reset_generation(engine, 'w', 'b', 'person_u')
    async with engine.connect() as conn:
        assert (await conn.execute(sa.select(sa.func.count()).select_from(Transcript))).scalar() == 2
        assert (await conn.execute(sa.select(sa.func.count()).select_from(MonitoringSession))).scalar() == 1
        assert (
            await conn.execute(
                sa.select(sa.func.count()).select_from(RunnerState).where(RunnerState.runner_id == 'runner')
            )
        ).scalar() == 4
    page = await store.page_transcript('person_u', bot_id='b', workspace_id='w')
    assert not page[0]
    assert (await store.page_transcript('person_u', bot_id='b2', workspace_id='w'))[0]
    await store.append_transcript(None, 'new', 'person_u', 'user', bot_id='b', workspace_id='w', content='fresh')
    assert len((await store.page_transcript('person_u', bot_id='b', workspace_id='w'))[0]) == 1
    await service.reset_session_context('w', 'b', 'person_u')
    assert not (await store.page_transcript('person_u', bot_id='b', workspace_id='w'))[0]


@pytest.mark.asyncio
async def test_reset_refuses_wrong_scope_and_running_tasks(context_service):
    service, engine = context_service
    for workspace, bot in [('other', 'b'), ('w', 'other')]:
        with pytest.raises(LookupError):
            await service.reset_session_context(workspace, bot, 'person_u')
    async with engine.begin() as conn:
        await conn.execute(
            sa.insert(AgentRun).values(
                run_id='run',
                event_id='evt',
                agent_id='agent',
                binding_id='binding',
                runner_id='runner',
                workspace_id='w',
                bot_id='b',
                conversation_id='person_u',
                status='running',
            )
        )
    with pytest.raises(RuntimeError):
        await service.reset_session_context('w', 'b', 'person_u')
    assert await get_reset_generation(engine, 'w', 'b', 'person_u') is None


@pytest.mark.asyncio
async def test_reset_starts_new_external_runner_conversation(context_service):
    from unit_tests.agent.test_state_store import FakeBinding, FakeEventEnvelope, make_descriptor
    from langbot.pkg.agent.runner.persistent_state_store import PersistentStateStore

    service, engine = context_service
    store = PersistentStateStore(engine)
    event = FakeEventEnvelope(workspace_id='w', bot_id='b', conversation_id='person_u')
    binding = FakeBinding()
    descriptor = make_descriptor()
    await store.apply_update_from_event(
        event, binding, descriptor, 'conversation', 'external.conversation_id', 'remote-old', None
    )
    assert (await store.build_snapshot_from_event(event, binding, descriptor))['conversation'][
        'external.conversation_id'
    ] == 'remote-old'
    await service.reset_session_context('w', 'b', 'person_u')
    snapshot = await store.build_snapshot_from_event(event, binding, descriptor)
    assert snapshot['conversation']['external.conversation_id'] == await get_reset_generation(
        engine, 'w', 'b', 'person_u'
    )
