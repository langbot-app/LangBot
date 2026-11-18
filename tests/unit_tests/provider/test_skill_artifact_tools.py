"""Run Skill content uses the authorized Artifact reader and structured SDK bridge."""

from __future__ import annotations

import asyncio
import base64
import io
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.context import ExecutionContext, PrincipalType
from langbot.pkg.provider.tools.loaders.skill import register_activated_skill
from langbot.pkg.provider.tools.loaders.skill_authoring import SkillToolLoader
from langbot_plugin.api.agent_tools.external_tools import AgentRunExternalTools


@pytest.fixture
def case():
    revision = 'sha256:' + '1' * 64
    query = SimpleNamespace(
        variables={},
        _agent_run_session={'run_id': 'run-a'},
        _execution_context=ExecutionContext('instance-a', 'workspace-a', 1),
    )
    register_activated_skill(query, {'name': 'demo', 'revision': revision})
    service = SimpleNamespace(
        create_run_skill_resource=AsyncMock(),
        read_run_skill_resource=AsyncMock(return_value=result(b'')),
    )
    service.create_run_skill_resource.side_effect = lambda *args, **kwargs: {
        'id': 'art_test',
        'size': len(service.read_run_skill_resource.return_value['content']),
    }
    loader = SkillToolLoader(
        SimpleNamespace(artifact_service=service, skill_repository=SimpleNamespace(database_backed=True))
    )
    return loader, query, service, revision


def _valid_pdf():
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def result(body, mime='text/plain'):
    return {'metadata': {'id': 'art_test', 'name': 'resource', 'mime_type': mime, 'size': len(body)}, 'content': body}


@pytest.mark.asyncio
async def test_run_text_compatibility_continuation_and_cached_reference(case):
    loader, query, service, revision = case
    service.read_run_skill_resource.return_value = result(b'abcdef')
    args = {'skill_name': 'demo', 'path': 'LICENSE', 'max_chars': 3}
    first = await loader.invoke_tool('read_skill_resource', args, query)
    second = await loader.invoke_tool('read_skill_resource', {**args, 'offset': 3}, query)
    assert first['content'] == 'abc' and first['next_offset'] == 3
    assert second['content'] == 'def' and second['next_offset'] is None
    assert first['revision'] == revision and first['artifact']['id'] == 'art_test'
    service.create_run_skill_resource.assert_awaited_once()
    context, name, frozen, path = service.create_run_skill_resource.call_args.args
    assert context.trigger_principal.principal_type == PrincipalType.PROCESSOR
    assert context.trigger_principal.run_id == 'run-a'
    assert (name, frozen, path) == ('demo', revision, 'LICENSE')
    assert service.read_run_skill_resource.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'mime,body,mode,kind',
    [
        ('image/png', b'\x89PNG\r\n\x1a\n\xff', 'auto', 'image'),
        ('application/pdf', _valid_pdf(), 'native', 'resource'),
    ],
)
async def test_run_binary_reaches_sdk_bridge_as_media(case, mime, body, mode, kind):
    loader, query, service, _ = case
    service.read_run_skill_resource.return_value = result(body, mime)
    contents = await loader.invoke_tool(
        'read_skill_resource',
        {
            'skill_name': 'demo',
            'path': 'asset',
            'mode': mode,
        },
        query,
    )
    assert isinstance(contents, list)
    bridge = object.__new__(AgentRunExternalTools)
    bridge.call_tool = AsyncMock(return_value=contents)
    response = await bridge.call_mcp_tool('call_tool', {})
    assert response['content'][1]['type'] == kind
    encoded = response['content'][1].get('data') or response['content'][1]['resource']['blob']
    assert base64.b64decode(encoded) == body
    assert encoded not in response['content'][0]['text']


@pytest.mark.asyncio
async def test_forged_revision_rejected_before_registration(case):
    loader, query, service, _ = case
    with pytest.raises(ValueError, match='match the activated'):
        await loader.invoke_tool(
            'read_skill_resource',
            {
                'skill_name': 'demo',
                'path': 'x',
                'revision': 'sha256:forged',
            },
            query,
        )
    service.create_run_skill_resource.assert_not_awaited()


@pytest.mark.asyncio
async def test_concurrent_return_budget_is_serialized(case):
    loader, query, service, _ = case
    service.read_run_skill_resource.return_value = result(b'x')
    args = {'skill_name': 'demo', 'path': 'x'}
    first = await loader.invoke_tool('read_skill_resource', args, query)
    returned_bytes = len(json.dumps(first, ensure_ascii=False).encode('utf-8'))
    query._skill_artifact_budgets['run-a']['returned_bytes'] = 1024 * 1024 - returned_bytes
    outcomes = await asyncio.gather(
        *[loader.invoke_tool('read_skill_resource', args, query) for _ in range(2)], return_exceptions=True
    )
    assert sum(isinstance(value, ValueError) for value in outcomes) == 1
    assert service.read_run_skill_resource.await_count == 2
    assert query.variables['_skill_resource_bytes_read'] == 1


@pytest.mark.asyncio
async def test_cached_reference_does_not_skip_service_authorization(case):
    loader, query, service, _ = case
    service.read_run_skill_resource.side_effect = [result(b'ok'), PermissionError('run ended')]
    args = {'skill_name': 'demo', 'path': 'x'}
    await loader.invoke_tool('read_skill_resource', args, query)
    with pytest.raises(PermissionError, match='run ended'):
        await loader.invoke_tool('read_skill_resource', args, query)
    assert service.create_run_skill_resource.await_count == 1
    assert service.read_run_skill_resource.await_count == 2


@pytest.mark.asyncio
async def test_filesystem_text_still_works_with_persisted_run_session(tmp_path):
    from tests.unit_tests.test_skill_repository import _repository, _CONTEXT

    repository = _repository(tmp_path)
    published = await repository.create_skill(_CONTEXT, {'name': 'demo', 'instructions': 'Legacy text'})
    snapshot = await repository.get_skill(_CONTEXT, 'demo', snapshot=True, revision=published['revision'])
    query = SimpleNamespace(variables={}, _execution_context=_CONTEXT, _agent_run_session={'run_id': 'live-run'})
    register_activated_skill(query, snapshot)
    service = SimpleNamespace(create_run_skill_resource=AsyncMock())
    loader = SkillToolLoader(SimpleNamespace(skill_repository=repository, artifact_service=service))
    result = await loader.invoke_tool('read_skill_resource', {'skill_name': 'demo', 'path': 'SKILL.md'}, query)
    assert 'Legacy text' in result['content']
    service.create_run_skill_resource.assert_not_awaited()


def test_list_schema_does_not_advertise_read_options():
    schema = SkillToolLoader(SimpleNamespace())._build_list_skill_resources_tool().parameters
    assert 'mode' not in schema['properties']


@pytest.mark.asyncio
async def test_large_text_can_be_read_to_end_without_recharging_source(case):
    loader, query, service, _ = case
    body = b'x' * (256 * 1024)
    service.read_run_skill_resource.return_value = result(body)
    offset = 0
    chunks = []
    while offset is not None:
        response = await loader.invoke_tool(
            'read_skill_resource',
            {'skill_name': 'demo', 'path': 'large.txt', 'offset': offset, 'max_chars': 8192},
            query,
        )
        chunks.append(response['content'])
        offset = response['next_offset']
    assert ''.join(chunks).encode() == body
    assert service.read_run_skill_resource.await_count == 32
    assert service.create_run_skill_resource.await_count == 1
    assert query.variables['_skill_resource_bytes_read'] == len(body)
    assert len(body) < query._skill_artifact_budgets['run-a']['returned_bytes'] < 1024 * 1024


@pytest.mark.asyncio
async def test_exhausted_source_budget_allows_continuation_not_a_new_source(case):
    loader, query, service, _ = case
    service.read_run_skill_resource.return_value = result(b'x' * (256 * 1024))
    service.create_run_skill_resource.side_effect = lambda context, name, revision, path, **kwargs: {
        'id': f'art_{path}',
        'size': 256 * 1024,
    }
    args = {'skill_name': 'demo', 'max_chars': 1}
    for path in ('first', 'second', 'third', 'fourth'):
        assert (await loader.invoke_tool('read_skill_resource', {**args, 'path': path}, query))['content'] == 'x'
    assert query._skill_artifact_budgets['run-a']['source_bytes'] == 1024 * 1024
    assert (await loader.invoke_tool('read_skill_resource', {**args, 'path': 'first', 'offset': 1}, query))[
        'content'
    ] == 'x'
    with pytest.raises(ValueError, match='reads exceed'):
        await loader.invoke_tool('read_skill_resource', {**args, 'path': 'new'}, query)
    assert service.create_run_skill_resource.await_count == 4
    assert query.variables['_skill_resource_bytes_read'] == 1024 * 1024


@pytest.mark.asyncio
async def test_source_failure_and_renderer_failure_have_distinct_accounting(case):
    loader, query, service, _ = case
    args = {'skill_name': 'demo', 'path': 'x'}
    registration = service.create_run_skill_resource.side_effect
    service.create_run_skill_resource.side_effect = OSError('registration read failed')
    with pytest.raises(OSError):
        await loader.invoke_tool('read_skill_resource', args, query)
    assert query._skill_artifact_budgets['run-a']['source_bytes'] == 0
    assert not query._skill_artifact_budgets['run-a']['materialized']
    service.create_run_skill_resource.side_effect = registration
    service.read_run_skill_resource.return_value = result(b'abc')
    with pytest.raises(ValueError, match='offset'):
        await loader.invoke_tool('read_skill_resource', {**args, 'offset': 100}, query)
    assert query._skill_artifact_budgets['run-a']['source_bytes'] == 3
    assert query._skill_artifact_budgets['run-a']['returned_bytes'] == 0
    assert (await loader.invoke_tool('read_skill_resource', args, query))['content'] == 'abc'
    assert query._skill_artifact_budgets['run-a']['source_bytes'] == 3


@pytest.mark.asyncio
async def test_returned_budget_charges_utf8_and_cannot_be_reset_by_variables(case):
    loader, query, service, _ = case
    service.read_run_skill_resource.return_value = result('文'.encode())
    args = {'skill_name': 'demo', 'path': 'x'}
    first = await loader.invoke_tool('read_skill_resource', args, query)
    returned_bytes = len(json.dumps(first, ensure_ascii=False).encode('utf-8'))
    assert query._skill_artifact_budgets['run-a']['returned_bytes'] == returned_bytes
    query.variables['_skill_resource_bytes_read'] = 0
    query._skill_artifact_budgets['run-a']['returned_bytes'] = 1024 * 1024 - returned_bytes + 1
    with pytest.raises(ValueError, match='returned content'):
        await loader.invoke_tool('read_skill_resource', args, query)
    assert query._skill_artifact_budgets['run-a']['returned_bytes'] == 1024 * 1024 - returned_bytes + 1
    assert query.variables['_skill_resource_bytes_read'] == 3


@pytest.mark.asyncio
async def test_repeated_output_exhausts_independent_return_budget(case):
    loader, query, service, _ = case
    body = b'x' * (256 * 1024)
    service.read_run_skill_resource.return_value = result(body)
    args = {'skill_name': 'demo', 'path': 'large.txt', 'max_chars': 16384}
    successes = 0
    with pytest.raises(ValueError, match='returned content'):
        for _ in range(65):
            response = await loader.invoke_tool('read_skill_resource', args, query)
            successes += 1
    size = len(json.dumps(response, ensure_ascii=False).encode('utf-8'))
    assert successes == (1024 * 1024) // size
    assert query._skill_artifact_budgets['run-a']['returned_bytes'] == successes * size
    assert query._skill_artifact_budgets['run-a']['source_bytes'] == len(body)


@pytest.mark.asyncio
async def test_reused_query_does_not_reuse_another_runs_budget_or_reference(case):
    loader, query, service, _ = case
    query.variables['_skill_resource_bytes_read'] = -1000000
    service.read_run_skill_resource.return_value = result(b'abc')
    args = {'skill_name': 'demo', 'path': 'x'}
    await loader.invoke_tool('read_skill_resource', args, query)
    assert query._skill_artifact_budgets['run-a']['source_bytes'] == 3
    query._skill_artifact_budgets['run-a']['returned_bytes'] = 1024 * 1024
    query._agent_run_session = {'run_id': 'run-b'}
    await loader.invoke_tool('read_skill_resource', args, query)
    assert query._skill_artifact_budgets['run-b']['source_bytes'] == 3
    assert query._skill_artifact_budgets['run-a']['returned_bytes'] == 1024 * 1024
    assert service.create_run_skill_resource.await_count == 2
    assert service.read_run_skill_resource.call_args.args[0].trigger_principal.run_id == 'run-b'


@pytest.mark.asyncio
async def test_cancelled_renderer_keeps_source_charge_but_not_output(case, monkeypatch):
    from langbot.pkg.storage import artifact_reader

    loader, query, service, _ = case
    service.read_run_skill_resource.return_value = result(b'abc')
    entered = asyncio.Event()
    original = artifact_reader.read_artifact_content

    async def suspended(*args, **kwargs):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(artifact_reader, 'read_artifact_content', suspended)
    args = {'skill_name': 'demo', 'path': 'x'}
    task = asyncio.create_task(loader.invoke_tool('read_skill_resource', args, query))
    await asyncio.wait_for(entered.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert query._skill_artifact_budgets['run-a']['source_bytes'] == 3
    assert query._skill_artifact_budgets['run-a']['returned_bytes'] == 0
    monkeypatch.setattr(artifact_reader, 'read_artifact_content', original)
    assert (await loader.invoke_tool('read_skill_resource', args, query))['content'] == 'abc'
    assert query._skill_artifact_budgets['run-a']['source_bytes'] == 3
    assert service.read_run_skill_resource.await_count == 2


@pytest.mark.asyncio
async def test_successful_registration_is_charged_even_if_followup_read_fails(case):
    loader, query, service, _ = case
    service.read_run_skill_resource.return_value = result(b'abc')
    service.read_run_skill_resource.side_effect = OSError('read after registration failed')
    args = {'skill_name': 'demo', 'path': 'x'}
    with pytest.raises(OSError):
        await loader.invoke_tool('read_skill_resource', args, query)
    assert query._skill_artifact_budgets['run-a']['source_bytes'] == 3
    assert query._skill_artifact_budgets['run-a']['returned_bytes'] == 0
    service.read_run_skill_resource.side_effect = None
    assert (await loader.invoke_tool('read_skill_resource', args, query))['content'] == 'abc'
    assert query._skill_artifact_budgets['run-a']['source_bytes'] == 3
    assert service.create_run_skill_resource.await_count == 1


@pytest.mark.asyncio
async def test_registration_receives_file_and_remaining_source_limits(case):
    loader, query, service, _ = case
    service.read_run_skill_resource.return_value = result(b'abc')
    args = {'skill_name': 'demo', 'path': 'first'}
    await loader.invoke_tool('read_skill_resource', args, query)
    assert service.create_run_skill_resource.call_args.kwargs['max_bytes'] == 256 * 1024
    query._skill_artifact_budgets['run-a']['source_bytes'] = 1024 * 1024 - 10
    await loader.invoke_tool('read_skill_resource', {**args, 'path': 'second'}, query)
    assert service.create_run_skill_resource.call_args.kwargs['max_bytes'] == 10
