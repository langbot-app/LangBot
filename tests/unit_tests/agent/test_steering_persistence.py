"""Steering publication stays behind its durable source event."""

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.agent.runner.event_log_store import EventLogStore
from langbot.pkg.agent.runner.orchestrator import AgentRunOrchestrator
from langbot.pkg.agent.runner.session_registry import get_session_registry
from langbot.pkg.entity.persistence.base import Base
from tests.unit_tests.agent.conftest import make_resources
from tests.unit_tests.agent.test_orchestrator_integration import (
    FakeApplication,
    FakePluginConnector,
    FakeRegistry,
    TEST_CONTEXT,
    make_descriptor,
    make_query,
)
from tests.unit_tests.agent.test_run_recovery import secured_host


@pytest.fixture
async def ingress(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "steering.sqlite"}')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    descriptor = make_descriptor()
    descriptor.capabilities.steering = True
    ap = FakeApplication(FakePluginConnector(), engine)
    orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
    query = make_query()
    plan = orchestrator.query_bridge.build_plan(query)
    registry = get_session_registry()
    await registry.register(
        run_id='pending-steering-run',
        runner_id=descriptor.id,
        plugin_identity=descriptor.get_plugin_id(),
        query_id=1,
        resources=make_resources(),
        available_apis={'steering_pull': True, 'steering_ack': True},
        conversation_id=plan.event.conversation_id,
        bot_id=plan.event.bot_id,
        workspace_id=plan.event.workspace_id,
        thread_id=plan.event.thread_id,
        binding_id=plan.binding.binding_id,
    )
    orchestrator.interaction_manager.waiting_run_ids = lambda: {'pending-steering-run'}
    host, binding = secured_host(ap, workspace_id=plan.event.workspace_id, plugin_identity=descriptor.get_plugin_id())

    async def invoke(entrypoint, *, suffix=''):
        incoming_query = query
        incoming_plan = plan
        if suffix:
            incoming_query = make_query()
            incoming_query.message_chain[0].id += suffix
            incoming_plan = orchestrator.query_bridge.build_plan(incoming_query)
        if entrypoint == 'query':
            return await orchestrator.try_claim_steering_from_query(incoming_query)
        return await orchestrator.try_claim_steering_from_event(
            incoming_plan.event, incoming_plan.binding, TEST_CONTEXT
        )

    async def pull(claim):
        token = host._current_action_context.set(binding)
        try:
            response = await host.actions['steering_pull']({'run_id': 'pending-steering-run', 'claim': claim})
            assert response.code == 0, response.message
            return response.data['items']
        finally:
            host._current_action_context.reset(token)

    try:
        yield SimpleNamespace(
            orchestrator=orchestrator,
            invoke=invoke,
            pull=pull,
            registry=registry,
            store=EventLogStore(engine),
            event=plan.event,
        )
    finally:
        await registry.unregister('pending-steering-run')
        await engine.dispose()


def pause_source_write(ingress, monkeypatch):
    entered = asyncio.Event()
    release = asyncio.Event()
    write = ingress.orchestrator.journal.write_event_log

    async def paused(**kwargs):
        if kwargs['event'].event_id == ingress.event.event_id:
            entered.set()
            await release.wait()
        return await write(**kwargs)

    monkeypatch.setattr(ingress.orchestrator.journal, 'write_event_log', paused)
    return entered, release


@pytest.mark.asyncio
@pytest.mark.parametrize('entrypoint', ['query', 'event'])
@pytest.mark.parametrize('claim', [False, True])
async def test_pull_waits_for_persisted_source(ingress, monkeypatch, entrypoint, claim):
    entered, release = pause_source_write(ingress, monkeypatch)
    task = asyncio.create_task(ingress.invoke(entrypoint))
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
        assert await ingress.pull(claim) == []
        assert len((await ingress.registry.get('pending-steering-run'))['steering_queue']) == 1
    finally:
        release.set()
    assert await task is True
    items = await ingress.pull(claim)
    assert [item['event']['event_id'] for item in items] == [ingress.event.event_id]
    assert '_steering_pending' not in items[0]
    source = await ingress.store.get_event(ingress.event.event_id)
    assert source['metadata']['steering']['status'] == ('claimed' if claim else 'injected')
    assert await ingress.pull(claim) == []


@pytest.mark.asyncio
@pytest.mark.parametrize('entrypoint', ['query', 'event'])
@pytest.mark.parametrize('claim', [False, True])
async def test_later_persisted_input_cannot_overtake_pending_input(ingress, monkeypatch, entrypoint, claim):
    entered, release = pause_source_write(ingress, monkeypatch)
    first = asyncio.create_task(ingress.invoke(entrypoint))
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
        assert await ingress.invoke(entrypoint, suffix='-second') is True
        queue = (await ingress.registry.get('pending-steering-run'))['steering_queue']
        expected_ids = [item['event']['event_id'] for item in queue]
        assert len(expected_ids) == 2 and expected_ids[0] != expected_ids[1]
        assert await ingress.pull(claim) == []
    finally:
        release.set()
    assert await first is True
    assert [item['event']['event_id'] for item in await ingress.pull(claim)] == expected_ids


@pytest.mark.asyncio
@pytest.mark.parametrize('entrypoint', ['query', 'event'])
async def test_source_write_failure_removes_unpublished_input(ingress, monkeypatch, entrypoint):
    async def fail(**kwargs):
        raise RuntimeError('source database unavailable')

    monkeypatch.setattr(ingress.orchestrator.journal, 'write_event_log', fail)
    with pytest.raises(RuntimeError, match='source database unavailable'):
        await ingress.invoke(entrypoint)
    assert (await ingress.registry.get('pending-steering-run'))['steering_queue'] == []
    assert await ingress.store.get_event(ingress.event.event_id) is None


@pytest.mark.asyncio
@pytest.mark.parametrize('entrypoint', ['query', 'event'])
async def test_cancel_before_publication_does_not_block_later_input(ingress, monkeypatch, entrypoint):
    entered = asyncio.Event()
    complete = ingress.registry.complete_steering_enqueue

    async def paused(run_id, event_id, *, persisted):
        if persisted and event_id == ingress.event.event_id:
            entered.set()
            await asyncio.Event().wait()
        return await complete(run_id, event_id, persisted=persisted)

    monkeypatch.setattr(ingress.registry, 'complete_steering_enqueue', paused)
    task = asyncio.create_task(ingress.invoke(entrypoint))
    await asyncio.wait_for(entered.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (await ingress.registry.get('pending-steering-run'))['steering_queue'] == []
    source = await ingress.store.get_event(ingress.event.event_id)
    assert source['metadata']['steering']['status'] == 'queued'
    assert await ingress.invoke(entrypoint, suffix='-second') is True
    items = await ingress.pull(True)
    assert len(items) == 1 and items[0]['event']['event_id'] != ingress.event.event_id


@pytest.mark.asyncio
@pytest.mark.parametrize('entrypoint', ['query', 'event'])
async def test_run_ending_during_persistence_does_not_absorb_input(ingress, monkeypatch, entrypoint):
    entered, release = pause_source_write(ingress, monkeypatch)
    task = asyncio.create_task(ingress.invoke(entrypoint))
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
        await ingress.registry.unregister('pending-steering-run')
    finally:
        release.set()
    assert await task is False
    source = await ingress.store.get_event(ingress.event.event_id)
    assert source['metadata']['steering']['status'] == 'dropped'
    assert await ingress.registry.get('pending-steering-run') is None
