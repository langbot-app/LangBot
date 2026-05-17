"""Tests for AgentResourceBuilder."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.agent.runner.descriptor import AgentRunnerDescriptor
from langbot.pkg.agent.runner.resource_builder import AgentResourceBuilder


RUNNER_ID = 'plugin:test/runner/default'


def make_descriptor(
    *,
    permissions: dict | None = None,
    config_schema: list[dict] | None = None,
) -> AgentRunnerDescriptor:
    return AgentRunnerDescriptor(
        id=RUNNER_ID,
        source='plugin',
        label={'en_US': 'Test Runner'},
        plugin_author='test',
        plugin_name='runner',
        runner_name='default',
        permissions=permissions or {'models': ['invoke', 'stream']},
        config_schema=config_schema or [],
    )


def make_model(model_type='llm', provider='test-provider'):
    return SimpleNamespace(
        model_entity=SimpleNamespace(model_type=model_type),
        provider_entity=SimpleNamespace(name=provider),
    )


def make_query(runner_config: dict, *, variables: dict | None = None, use_llm_model_uuid=None):
    return SimpleNamespace(
        pipeline_config={
            'ai': {
                'runner': {'id': RUNNER_ID},
                'runner_config': {RUNNER_ID: runner_config},
            },
        },
        variables=variables or {},
        use_llm_model_uuid=use_llm_model_uuid,
    )


@pytest.fixture
def app():
    mock_app = Mock()
    mock_app.logger = Mock()
    mock_app.model_mgr = Mock()
    mock_app.rag_mgr = Mock()
    mock_app.rag_mgr.get_knowledge_base_by_uuid = AsyncMock(return_value=None)
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

    resources = await AgentResourceBuilder(app).build_resources(query, descriptor)

    assert resources['models'] == [
        {'model_id': 'primary', 'model_type': 'llm', 'provider': 'test-provider'},
        {'model_id': 'fallback', 'model_type': 'llm', 'provider': 'test-provider'},
        {'model_id': 'aux', 'model_type': 'llm', 'provider': 'aux-provider'},
        {'model_id': 'rerank', 'model_type': 'rerank', 'provider': 'rerank-provider'},
    ]


@pytest.mark.asyncio
async def test_build_models_still_honors_manifest_permissions(app):
    """Config-selected models should not bypass runner manifest permissions."""
    app.model_mgr.get_model_by_uuid = AsyncMock(return_value=make_model())
    app.model_mgr.get_rerank_model_by_uuid = AsyncMock(return_value=make_model(model_type='rerank'))
    descriptor = make_descriptor(
        permissions={'models': []},
        config_schema=[
            {'name': 'model', 'type': 'model-fallback-selector'},
            {'name': 'rerank-model', 'type': 'rerank-model-selector'},
        ],
    )
    query = make_query({
        'model': {'primary': 'primary', 'fallbacks': ['fallback']},
        'rerank-model': 'rerank',
    })

    resources = await AgentResourceBuilder(app).build_resources(query, descriptor)

    assert resources['models'] == []
    app.model_mgr.get_model_by_uuid.assert_not_awaited()
    app.model_mgr.get_rerank_model_by_uuid.assert_not_awaited()


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

    resources = await AgentResourceBuilder(app).build_resources(query, descriptor)

    assert [model['model_id'] for model in resources['models']] == ['primary', 'fallback']
