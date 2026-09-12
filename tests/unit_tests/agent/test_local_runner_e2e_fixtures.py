"""Keep E2E fake resources compatible with the real Host contract."""

from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from langbot.pkg.agent.runner.descriptor import RunnerDescriptor
from langbot.pkg.agent.runner.resource_builder import AgentResourceBuilder
from langbot.pkg.api.http.context import ExecutionContext
from tests.e2e.test_local_runner_fake_provider import (
    E2E_KB_UUID,
    E2E_TOOL_NAME,
    LOCAL_RUNNER_ID,
    _FakeKnowledgeBase,
    _FakeRagManager,
    _FakeToolManager,
    _binding,
    _event,
)

CONTEXT = ExecutionContext(instance_uuid='instance-test', workspace_uuid='workspace-test', placement_generation=1)
SOURCE = {'source': 'native', 'source_id': None}


async def _resources(tool_mgr, rag_mgr, binding):
    descriptor = RunnerDescriptor(
        usages=['agent'],
        id=LOCAL_RUNNER_ID,
        source='plugin',
        label={'en_US': 'Local Agent'},
        plugin_author='langbot-team',
        plugin_name='LocalAgent',
        runner_name='default',
        capabilities={'tool_calling': True, 'knowledge_retrieval': True},
        permissions={'tools': ['detail', 'call'], 'knowledge_bases': ['list', 'retrieve']},
    )
    app = SimpleNamespace(logger=Mock(), skill_mgr=None, tool_mgr=tool_mgr, rag_mgr=rag_mgr)
    return await AgentResourceBuilder(app).build_resources_from_binding(
        CONTEXT,
        _event(event_id='evt', conversation_id='conv', text='test'),
        binding,
        descriptor,
    )


@pytest.mark.asyncio
async def test_fake_tool_is_projected_with_frozen_source_and_executed():
    manager = _FakeToolManager()
    resources = await _resources(
        manager, _FakeRagManager(_FakeKnowledgeBase()), _binding(allowed_tool_names=[E2E_TOOL_NAME])
    )
    assert len(resources['tools']) == 1
    tool = resources['tools'][0]
    assert tool['tool_name'] == E2E_TOOL_NAME
    assert {key: tool[key] for key in SOURCE} == SOURCE
    assert tool['parameters']['required'] == ['query']
    detail = await manager.get_tool_detail(CONTEXT, E2E_TOOL_NAME, source_ref=SOURCE)
    assert detail['parameters'] == tool['parameters']
    result = await manager.execute_func_call(
        name=E2E_TOOL_NAME,
        parameters={'query': 'alpha'},
        query=SimpleNamespace(workspace_uuid=CONTEXT.workspace_uuid),
        source_ref=SOURCE,
    )
    assert result['value'] == 'tool-result:alpha'
    assert manager.calls == [{'name': E2E_TOOL_NAME, 'parameters': {'query': 'alpha'}}]


@pytest.mark.asyncio
async def test_fake_kb_is_projected_and_retrieved_with_execution_context():
    kb = _FakeKnowledgeBase()
    manager = _FakeRagManager(kb)
    resources = await _resources(_FakeToolManager(), manager, _binding(allowed_kb_uuids=[E2E_KB_UUID]))
    assert [item['kb_id'] for item in resources['knowledge_bases']] == [E2E_KB_UUID]
    resolved = await manager.get_knowledge_base_by_uuid(CONTEXT, E2E_KB_UUID)
    entries = await resolved.retrieve(CONTEXT, 'test', settings={'top_k': 1, 'filters': {}})
    assert 'RAG_SENTINEL' in entries[0].content
    assert kb.retrieve_calls == [{'query_text': 'test', 'settings': {'top_k': 1, 'filters': {}}}]


def test_local_agent_package_excludes_alternate_virtualenvs(tmp_path, monkeypatch):
    import zipfile
    from tests.e2e import test_local_runner_fake_provider as fixtures

    source = tmp_path / 'source'
    source.mkdir()
    (source / 'manifest.yaml').write_text('metadata: {author: langbot-team, name: LocalAgent}')
    for name in ('.venv', '.venv311'):
        (source / name).mkdir()
        (source / name / 'not-plugin.py').write_text('pass')
    monkeypatch.setattr(fixtures, '_local_agent_repo', lambda: source)
    package = fixtures._package_local_agent_plugin(tmp_path / 'package')
    with zipfile.ZipFile(package) as archive:
        assert archive.namelist() == ['manifest.yaml']


@pytest.mark.asyncio
async def test_failed_local_agent_boot_shuts_down_before_restoring_transport(monkeypatch, tmp_path):
    import asyncio
    from unittest.mock import AsyncMock
    from langbot.pkg.core import boot
    from tests.e2e import test_local_runner_fake_provider as fixtures

    async def running():
        await asyncio.Event().wait()

    app = SimpleNamespace(
        run=running,
        shutdown=AsyncMock(),
        plugin_connector=SimpleNamespace(
            handler=SimpleNamespace(ping=AsyncMock()), _current_execution_context=AsyncMock(return_value=CONTEXT)
        ),
        runner_registry=SimpleNamespace(list_runners=AsyncMock(side_effect=ValueError('probe boot failure'))),
    )
    monkeypatch.setattr(boot, 'make_app', AsyncMock(return_value=app))
    try:
        with pytest.raises(ValueError, match='probe boot failure'):
            await fixtures._boot_local_agent_app(tmp_path)
        app.shutdown.assert_awaited_once()
        assert not any(task.get_name() == 'local-agent-e2e-app' for task in asyncio.all_tasks())
    finally:
        tasks = [task for task in asyncio.all_tasks() if task.get_name() == 'local-agent-e2e-app']
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
