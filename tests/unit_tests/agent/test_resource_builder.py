"""Tests for AgentResourceBuilder."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.agent.runner.descriptor import AgentRunnerDescriptor
from langbot.pkg.agent.runner.binding_resolver import AgentBindingResolver
from langbot.pkg.agent.runner.query_entry_adapter import QueryEntryAdapter
from langbot.pkg.agent.runner.resource_builder import AgentResourceBuilder


RUNNER_ID = 'plugin:test/runner/default'
FULL_PERMISSIONS = {
    'models': ['invoke', 'stream', 'rerank'],
    'tools': ['detail', 'call'],
    'knowledge_bases': ['list', 'retrieve'],
    'history': ['page', 'search'],
    'events': ['get', 'page'],
    'storage': ['plugin', 'workspace'],
}


def make_descriptor(
    *,
    config_schema: list[dict] | None = None,
    capabilities: dict | None = None,
    permissions: dict | None = None,
) -> AgentRunnerDescriptor:
    return AgentRunnerDescriptor(
        id=RUNNER_ID,
        source='plugin',
        label={'en_US': 'Test Runner'},
        plugin_author='test',
        plugin_name='runner',
        runner_name='default',
        capabilities=capabilities or {},
        permissions=permissions if permissions is not None else FULL_PERMISSIONS,
        config_schema=config_schema or [],
    )


def make_model(model_type='llm', provider='test-provider'):
    return SimpleNamespace(
        model_entity=SimpleNamespace(model_type=model_type),
        provider_entity=SimpleNamespace(name=provider),
    )


def make_query(
    runner_config: dict,
    *,
    variables: dict | None = None,
    use_llm_model_uuid=None,
    use_funcs: list | None = None,
):
    return SimpleNamespace(
        query_id=1,
        bot_uuid='bot_001',
        launcher_type='person',
        launcher_id='launcher_001',
        sender_id='sender_001',
        message_event=None,
        message_chain=None,
        user_message=None,
        session=None,
        pipeline_config={
            'ai': {
                'runner': {'id': RUNNER_ID},
                'runner_config': {RUNNER_ID: runner_config},
            },
        },
        variables=variables or {},
        use_llm_model_uuid=use_llm_model_uuid,
        use_funcs=use_funcs or [],
        pipeline_uuid='pipeline_001',
    )


async def build_resources(app, query, descriptor):
    event = QueryEntryAdapter.query_to_event(query)
    agent_config = QueryEntryAdapter.config_to_agent_config(query, descriptor.id)
    binding = AgentBindingResolver().resolve_one(event, [agent_config])
    return await AgentResourceBuilder(app).build_resources_from_binding(
        event=event,
        binding=binding,
        descriptor=descriptor,
    )


@pytest.fixture
def app():
    mock_app = Mock()
    mock_app.logger = Mock()
    mock_app.model_mgr = Mock()
    mock_app.rag_mgr = Mock()
    mock_app.rag_mgr.get_knowledge_base_by_uuid = AsyncMock(return_value=None)
    mock_app.skill_mgr = None
    mock_app.tool_mgr = Mock()
    mock_app.tool_mgr.get_tool_schema = AsyncMock(return_value=(None, None))
    return mock_app


@pytest.mark.asyncio
async def test_build_models_authorizes_config_declared_llm_and_rerank_models(app):
    """DynamicForm model selectors should become run-scoped authorized models."""
    llm_models = {
        'primary': make_model(),
        'fallback': make_model(),
        'aux': make_model(provider='aux-provider'),
    }
    rerank_models = {
        'rerank': make_model(model_type='rerank', provider='rerank-provider'),
    }

    async def get_model_by_uuid(model_uuid):
        return llm_models.get(model_uuid)

    async def get_rerank_model_by_uuid(model_uuid):
        return rerank_models.get(model_uuid)

    app.model_mgr.get_model_by_uuid = AsyncMock(side_effect=get_model_by_uuid)
    app.model_mgr.get_rerank_model_by_uuid = AsyncMock(side_effect=get_rerank_model_by_uuid)
    descriptor = make_descriptor(
        config_schema=[
            {'name': 'model', 'type': 'model-fallback-selector'},
            {'name': 'aux-model', 'type': 'llm-model-selector'},
            {'name': 'rerank-model', 'type': 'rerank-model-selector'},
        ],
    )
    query = make_query({
        'model': {'primary': 'primary', 'fallbacks': ['fallback', 'primary']},
        'aux-model': 'aux',
        'rerank-model': 'rerank',
    })

    resources = await build_resources(app, query, descriptor)

    assert resources['models'] == [
        {'model_id': 'primary', 'model_type': 'llm', 'provider': 'test-provider', 'operations': ['invoke', 'stream']},
        {'model_id': 'fallback', 'model_type': 'llm', 'provider': 'test-provider', 'operations': ['invoke', 'stream']},
        {'model_id': 'aux', 'model_type': 'llm', 'provider': 'aux-provider', 'operations': ['invoke', 'stream']},
        {'model_id': 'rerank', 'model_type': 'rerank', 'provider': 'rerank-provider', 'operations': ['rerank']},
    ]


@pytest.mark.asyncio
async def test_build_models_from_config_without_manifest_acl(app):
    """Config-selected models are not projected without manifest model permissions."""
    app.model_mgr.get_model_by_uuid = AsyncMock(return_value=make_model())
    app.model_mgr.get_rerank_model_by_uuid = AsyncMock(return_value=make_model(model_type='rerank'))
    descriptor = make_descriptor(
        config_schema=[
            {'name': 'model', 'type': 'model-fallback-selector'},
            {'name': 'rerank-model', 'type': 'rerank-model-selector'},
        ],
        permissions={},
    )
    query = make_query({
        'model': {'primary': 'primary', 'fallbacks': ['fallback']},
        'rerank-model': 'rerank',
    })

    resources = await build_resources(app, query, descriptor)

    assert resources['models'] == []


@pytest.mark.asyncio
async def test_build_models_authorizes_rerank_and_llm_refs_from_config(app):
    """Config-selected model references are projected regardless of method granularity."""
    app.model_mgr.get_model_by_uuid = AsyncMock(return_value=make_model())
    app.model_mgr.get_rerank_model_by_uuid = AsyncMock(
        return_value=make_model(model_type='rerank', provider='rerank-provider')
    )
    descriptor = make_descriptor(
        config_schema=[
            {'name': 'model', 'type': 'llm-model-selector'},
            {'name': 'rerank-model', 'type': 'rerank-model-selector'},
        ],
    )
    query = make_query({
        'model': 'llm',
        'rerank-model': 'rerank',
    })

    resources = await build_resources(app, query, descriptor)

    assert resources['models'] == [
        {'model_id': 'llm', 'model_type': 'llm', 'provider': 'test-provider', 'operations': ['invoke', 'stream']},
        {'model_id': 'rerank', 'model_type': 'rerank', 'provider': 'rerank-provider', 'operations': ['rerank']},
    ]


@pytest.mark.asyncio
async def test_build_resources_accepts_dynamic_form_type_aliases(app):
    """Frontend DynamicForm aliases should resolve to runtime resource grants."""
    app.model_mgr.get_model_by_uuid = AsyncMock(return_value=make_model())

    async def get_kb(kb_uuid):
        return SimpleNamespace(
            uuid=kb_uuid,
            get_name=lambda: f'name-{kb_uuid}',
            knowledge_base_entity=SimpleNamespace(kb_type='default'),
        )

    app.rag_mgr.get_knowledge_base_by_uuid = AsyncMock(side_effect=get_kb)
    descriptor = make_descriptor(
        capabilities={'knowledge_retrieval': True},
        config_schema=[
            {'name': 'model', 'type': 'select-llm-model'},
            {'name': 'knowledge-bases', 'type': 'select-knowledge-bases'},
        ],
    )
    query = make_query({
        'model': 'llm_alias',
        'knowledge-bases': ['kb_alias'],
    })

    resources = await build_resources(app, query, descriptor)

    assert resources['models'] == [
        {'model_id': 'llm_alias', 'model_type': 'llm', 'provider': 'test-provider', 'operations': ['invoke', 'stream']},
    ]
    assert resources['knowledge_bases'] == [
        {'kb_id': 'kb_alias', 'kb_name': 'name-kb_alias', 'kb_type': 'default', 'operations': ['list', 'retrieve']},
    ]


@pytest.mark.asyncio
async def test_build_models_manifest_permission_narrows_binding(app):
    """Manifest model permissions narrower than binding should remove LLM grants."""
    app.model_mgr.get_model_by_uuid = AsyncMock(return_value=make_model())
    app.model_mgr.get_rerank_model_by_uuid = AsyncMock(
        return_value=make_model(model_type='rerank', provider='rerank-provider')
    )
    descriptor = make_descriptor(
        config_schema=[
            {'name': 'model', 'type': 'llm-model-selector'},
            {'name': 'rerank-model', 'type': 'rerank-model-selector'},
        ],
        permissions={
            **FULL_PERMISSIONS,
            'models': ['rerank'],
        },
    )
    query = make_query({
        'model': 'llm',
        'rerank-model': 'rerank',
    })

    resources = await build_resources(app, query, descriptor)

    assert resources['models'] == [
        {'model_id': 'rerank', 'model_type': 'rerank', 'provider': 'rerank-provider', 'operations': ['rerank']},
    ]


@pytest.mark.asyncio
async def test_build_models_deduplicates_query_and_config_models(app):
    """A model selected by both preproc and runner config should appear once."""
    app.model_mgr.get_model_by_uuid = AsyncMock(return_value=make_model())
    app.model_mgr.get_rerank_model_by_uuid = AsyncMock(return_value=None)
    descriptor = make_descriptor(
        config_schema=[
            {'name': 'model', 'type': 'model-fallback-selector'},
        ],
    )
    query = make_query(
        {'model': {'primary': 'primary', 'fallbacks': ['fallback']}},
        variables={'_fallback_model_uuids': ['fallback']},
        use_llm_model_uuid='primary',
    )

    resources = await build_resources(app, query, descriptor)

    assert [model['model_id'] for model in resources['models']] == ['primary', 'fallback']


@pytest.mark.asyncio
async def test_build_tools_authorizes_query_declared_tools(app):
    """Tools discovered by Pipeline preprocessing become run-scoped authorized
    resources, with full parameters schema prefilled by the host."""
    app.tool_mgr.get_tool_schema = AsyncMock(
        side_effect=lambda name: {
            'qa_plugin_echo': (
                'Echo test tool',
                {'type': 'object', 'properties': {'text': {'type': 'string'}}},
            ),
        }.get(name, (None, None))
    )
    descriptor = make_descriptor(
        capabilities={'tool_calling': True},
    )
    query = make_query(
        {},
        use_funcs=[
            {'name': 'qa_plugin_echo', 'description': 'Echo test tool'},
            SimpleNamespace(name='qa_mcp_echo'),
        ],
    )

    resources = await build_resources(app, query, descriptor)

    assert resources['tools'] == [
        {
            'tool_name': 'qa_plugin_echo',
            'tool_type': None,
            'description': 'Echo test tool',
            'operations': ['detail', 'call'],
            'parameters': {'type': 'object', 'properties': {'text': {'type': 'string'}}},
        },
        {
            'tool_name': 'qa_mcp_echo',
            'tool_type': None,
            'description': None,
            'operations': ['detail', 'call'],
            'parameters': None,
        },
    ]


@pytest.mark.asyncio
async def test_build_tools_manifest_permission_denies_binding_tools(app):
    """Binding tool grants should be removed when manifest does not request tools."""
    descriptor = make_descriptor(
        capabilities={'tool_calling': True},
        permissions={
            **FULL_PERMISSIONS,
            'tools': [],
        },
    )
    query = make_query(
        {},
        use_funcs=[
            {'name': 'qa_plugin_echo', 'description': 'Echo test tool'},
        ],
    )

    resources = await build_resources(app, query, descriptor)

    assert resources['tools'] == []


@pytest.mark.asyncio
async def test_build_knowledge_bases_unions_config_and_policy_grants(app):
    descriptor = make_descriptor(
        capabilities={'knowledge_retrieval': True},
        config_schema=[
            {'name': 'knowledge-bases', 'type': 'knowledge-base-multi-selector'},
        ],
    )
    query = make_query(
        {'knowledge-bases': ['kb_config']},
        variables={'_knowledge_base_uuids': ['kb_policy']},
    )

    async def get_kb(kb_uuid):
        return SimpleNamespace(
            uuid=kb_uuid,
            get_name=lambda: f'name-{kb_uuid}',
            knowledge_base_entity=SimpleNamespace(kb_type='default'),
        )

    app.rag_mgr.get_knowledge_base_by_uuid = AsyncMock(side_effect=get_kb)

    resources = await build_resources(app, query, descriptor)

    assert resources['knowledge_bases'] == [
        {'kb_id': 'kb_config', 'kb_name': 'name-kb_config', 'kb_type': 'default', 'operations': ['list', 'retrieve']},
        {'kb_id': 'kb_policy', 'kb_name': 'name-kb_policy', 'kb_type': 'default', 'operations': ['list', 'retrieve']},
    ]


@pytest.mark.asyncio
async def test_build_knowledge_bases_manifest_permission_denies_binding_kbs(app):
    descriptor = make_descriptor(
        capabilities={'knowledge_retrieval': True},
        permissions={
            **FULL_PERMISSIONS,
            'knowledge_bases': [],
        },
        config_schema=[
            {'name': 'knowledge-bases', 'type': 'knowledge-base-multi-selector'},
        ],
    )
    query = make_query(
        {'knowledge-bases': ['kb_config']},
        variables={'_knowledge_base_uuids': ['kb_policy']},
    )

    resources = await build_resources(app, query, descriptor)

    assert resources['knowledge_bases'] == []


@pytest.mark.asyncio
async def test_build_storage_intersects_manifest_and_binding_policy(app):
    descriptor = make_descriptor(
        permissions={
            **FULL_PERMISSIONS,
            'storage': ['plugin'],
        },
    )
    query = make_query({})

    resources = await build_resources(app, query, descriptor)

    assert resources['storage'] == {
        'plugin_storage': True,
        'workspace_storage': False,
    }
