"""Run Skill content uses the authorized Artifact reader and structured SDK bridge."""

from __future__ import annotations

import asyncio
import base64
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
        create_run_skill_resource=AsyncMock(return_value={'id': 'art_test'}),
        read_run_skill_resource=AsyncMock(),
    )
    loader = SkillToolLoader(
        SimpleNamespace(artifact_service=service, skill_repository=SimpleNamespace(database_backed=True))
    )
    return loader, query, service, revision


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
        ('application/pdf', b'%PDF-1.4\nexample', 'native', 'resource'),
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
async def test_concurrent_budget_is_serialized_and_read_is_reauthorized(case):
    loader, query, service, _ = case
    service.read_run_skill_resource.return_value = result(b'x')
    query.variables['_skill_resource_bytes_read'] = 1024 * 1024 - 1
    args = {'skill_name': 'demo', 'path': 'x'}
    outcomes = await asyncio.gather(
        *[loader.invoke_tool('read_skill_resource', args, query) for _ in range(2)], return_exceptions=True
    )
    assert sum(isinstance(value, ValueError) for value in outcomes) == 1
    assert service.read_run_skill_resource.await_count == 1


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
