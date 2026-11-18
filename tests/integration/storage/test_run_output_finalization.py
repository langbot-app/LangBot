"""Closing a run rolls back in-flight export and rejects queued or late file actions."""
# ruff: noqa: F811

import asyncio
import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from langbot_plugin.box.errors import BoxValidationError

from langbot.pkg.agent.runner import orchestrator as orchestrator_module
from langbot.pkg.agent.runner.orchestrator import AgentRunOrchestrator
from langbot.pkg.agent.runner.session_registry import get_session_registry
from langbot.pkg.box.runner import RunBoxBinding, RunnerBoxService
from langbot.pkg.entity.persistence.artifact import Artifact
from tests.integration.storage.test_artifacts import (
    artifact_replicas,  # noqa: F401 -- pytest fixture
    persistence_case,  # noqa: F401 -- fixture dependency
    replicas,  # noqa: F401 -- fixture dependency
)
from tests.utils.artifact_store import seed_run
from tests.unit_tests.agent.test_orchestrator_integration import (
    FakeApplication,
    FakePluginConnector,
    clean_agent_state,  # noqa: F401 -- isolated real run ledger
    make_descriptor,
    make_query,
)


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('cleanup_times_out', [False, True])
async def test_finalization_drains_export_and_rejects_queued_file_actions(
    artifact_replicas,
    clean_agent_state,
    monkeypatch,
    cleanup_times_out,
):
    if cleanup_times_out:
        await_cleanup = orchestrator_module._await_run_cleanup

        async def short_cleanup(*args, **kwargs):
            return await await_cleanup(*args, **kwargs, timeout=0.02)

        monkeypatch.setattr(orchestrator_module, '_await_run_cleanup', short_cleanup)
    case = artifact_replicas
    query = make_query()
    context = case.a.context
    for name in ('instance_uuid', 'workspace_uuid', 'placement_generation'):
        object.__setattr__(query, name, getattr(context, name))
    object.__setattr__(query, '_execution_context', context)
    staged = asyncio.Event()
    publish = asyncio.Event()
    jobs = []
    box = SimpleNamespace(
        ap=case.a.app,
        _ATTACHMENT_MAX_FILES=20,
        _ATTACHMENT_MAX_TOTAL_BYTES=50 * 1024 * 1024,
        collect_selected_files=AsyncMock(
            return_value=[
                {
                    'name': 'inflight.txt',
                    'type': 'File',
                    'base64': base64.b64encode(b'accepted before close').decode(),
                }
            ]
        ),
        clear_selected_files=AsyncMock(return_value=None),
    )
    api = RunnerBoxService(box)
    create = case.a.app.artifact_service.create_run_output

    async def stage_before_commit(*args):
        metadata = await create(*args)
        staged.set()
        await publish.wait()
        return metadata

    monkeypatch.setattr(case.a.app.artifact_service, 'create_run_output', stage_before_commit)

    class OutputConnector(FakePluginConnector):
        async def run_runner(self, **kwargs):
            self.contexts.append(kwargs['context'])
            run_id = kwargs['context']['run_id']
            await seed_run(case.a.app, context, run_id)
            object.__setattr__(query, '_box_binding', RunBoxBinding(run_id, 'finalizing-box', {}, run_id))
            jobs.append(asyncio.create_task(api.export_files(query, ['/workspace/inflight.txt'])))
            await staged.wait()
            jobs.append(asyncio.create_task(api.export_files(query, ['/workspace/queued.txt'])))
            await asyncio.sleep(0)
            yield {'type': 'run.completed', 'data': {'finish_reason': 'stop'}}

    connector = OutputConnector()
    application = FakeApplication(connector, clean_agent_state)
    application.artifact_service = case.a.app.artifact_service
    application.box_service.cleanup_run_files = AsyncMock()
    registry = SimpleNamespace(get=AsyncMock(return_value=make_descriptor()))
    orchestrator = AgentRunOrchestrator(application, registry)

    async def consume():
        return [result async for result in orchestrator.run_from_query(query)]

    async def wait_for_fence():
        while not getattr(query, '_run_files_closing', False):
            await asyncio.sleep(0)

    task = asyncio.create_task(consume())
    try:
        await asyncio.wait_for(staged.wait(), timeout=3)
        await asyncio.wait_for(wait_for_fence(), timeout=3)
        assert not task.done() and not jobs[0].done()
        if cleanup_times_out:
            await asyncio.wait_for(task, timeout=3)
            assert not hasattr(query, '_box_binding') and not jobs[0].done()
        publish.set()
        with pytest.raises(BoxValidationError, match='access has ended'):
            await asyncio.wait_for(jobs[0], timeout=3)
        with pytest.raises(BoxValidationError):
            await asyncio.wait_for(jobs[1], timeout=3)
        await asyncio.wait_for(task, timeout=3)
        run_id = connector.contexts[0]['run_id']
        async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            count = (
                await uow.execute(
                    sa.select(sa.func.count())
                    .select_from(Artifact)
                    .where(
                        Artifact.owner_type == 'run_output',
                        Artifact.owner_id == run_id,
                    )
                )
            ).scalar_one()
        assert count == 0
        box.collect_selected_files.assert_awaited_once()
        box.clear_selected_files.assert_not_awaited()
        if cleanup_times_out:
            application.box_service.cleanup_run_files.assert_not_awaited()
        else:
            application.box_service.cleanup_run_files.assert_awaited_once_with(query)
        assert not hasattr(query, '_box_binding')
        assert await get_session_registry().get(run_id) is None
    finally:
        publish.set()
        for job in [task, *jobs]:
            if not job.done():
                job.cancel()
        await asyncio.gather(task, *jobs, return_exceptions=True)
