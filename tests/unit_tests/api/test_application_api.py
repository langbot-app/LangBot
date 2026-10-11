import inspect
import typing
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.application import (
    APPLICATION_API_VERSION,
    ApplicationAPI,
    ApplicationAPIException,
    ApplicationSurface,
    PipelineListInput,
    PipelineExtensionsUpdateInput,
    KnowledgeBaseListInput,
    KnowledgeBaseGetInput,
    KnowledgeEngineListInput,
    KnowledgeEngineSchemaInput,
)
from langbot.pkg.api.http.authz import Permission, PermissionDeniedError


def _context(*permissions: str):
    return SimpleNamespace(
        workspace=SimpleNamespace(permissions=frozenset(permissions)),
    )


@pytest.mark.asyncio
async def test_list_pipelines_delegates_with_workspace_authorization():
    service = SimpleNamespace(get_pipelines=AsyncMock(return_value=[{'uuid': 'p1'}]))
    api = ApplicationAPI(SimpleNamespace(pipeline_service=service))
    context = _context(Permission.RESOURCE_VIEW.value)

    result = await api.list_pipelines(context, 'updated_at', 'ASC')

    assert result == [{'uuid': 'p1'}]
    service.get_pipelines.assert_awaited_once_with(
        context,
        'updated_at',
        'ASC',
        include_secret=False,
    )


@pytest.mark.asyncio
async def test_pipeline_operation_rejects_missing_permission():
    service = SimpleNamespace(get_pipeline=AsyncMock())
    api = ApplicationAPI(SimpleNamespace(pipeline_service=service))
    context = _context()

    with pytest.raises(PermissionDeniedError):
        await api.get_pipeline(context, 'p1')

    service.get_pipeline.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_requires_typed_input_and_enforces_surface():
    service = SimpleNamespace(get_pipelines=AsyncMock(return_value=[]))
    api = ApplicationAPI(SimpleNamespace(pipeline_service=service))
    context = _context(Permission.RESOURCE_VIEW.value)

    with pytest.raises(ApplicationAPIException) as invalid:
        await api.execute('pipeline.list', context, {'sort_by': 'created_at'})
    assert invalid.value.error.code == 'invalid_input'

    with pytest.raises(ApplicationAPIException) as denied:
        await api.execute(
            'pipeline.extensions.update',
            context,
            PipelineExtensionsUpdateInput('p1', []),
            surface=ApplicationSurface.ASSISTANT,
        )
    assert denied.value.error.code == 'surface_not_allowed'


@pytest.mark.asyncio
async def test_execute_validates_service_output_contract():
    service = SimpleNamespace(get_pipelines=AsyncMock(return_value={'not': 'a list'}))
    api = ApplicationAPI(SimpleNamespace(pipeline_service=service))

    with pytest.raises(ApplicationAPIException) as failure:
        await api.execute('pipeline.list', _context(Permission.RESOURCE_VIEW.value), PipelineListInput())
    assert failure.value.error.code == 'invalid_output'


def test_catalog_is_versioned_and_workspace_scoped():
    catalog = {item['id']: item for item in ApplicationAPI.operation_catalog()}

    assert len(catalog) == 8
    assert catalog['pipeline.list']['version'] == APPLICATION_API_VERSION
    assert catalog['pipeline.list']['scope'] == 'workspace'
    assert catalog['pipeline.extensions.update']['side_effect'] is True
    assert catalog['pipeline.list']['input_type'] == 'PipelineListInput'
    assert catalog['pipeline.list']['output_type'] == 'PipelineListOutput'
    assert catalog['pipeline.extensions.update']['error_type'] == 'ApplicationAPIError'
    assert catalog['knowledge.engine.list']['version'] == APPLICATION_API_VERSION
    assert catalog['knowledge.engine.schema.get']['input_type'] == 'KnowledgeEngineSchemaInput'
    assert catalog['knowledge.base.list']['output_type'] == 'KnowledgeBaseListOutput'
    assert catalog['knowledge.base.get']['output_type'] == 'KnowledgeBaseGetOutput'
    assert set(catalog['knowledge.engine.list']['allowed_surfaces']) == {
        ApplicationSurface.HTTP.value,
        ApplicationSurface.MCP.value,
        ApplicationSurface.ASSISTANT.value,
    }
    assert set(catalog['pipeline.get']['allowed_surfaces']) == {
        ApplicationSurface.HTTP.value,
        ApplicationSurface.MCP.value,
        ApplicationSurface.ASSISTANT.value,
        ApplicationSurface.CLI.value,
    }


def test_update_pipeline_extensions_has_explicit_typed_parameters():
    signature = inspect.signature(ApplicationAPI.update_pipeline_extensions)
    assert all(parameter.kind is not inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values())
    assert typing.get_type_hints(ApplicationAPI.update_pipeline_extensions)['input'] is PipelineExtensionsUpdateInput


def test_application_api_is_part_of_minimal_application_graph():
    service = SimpleNamespace(
        get_pipelines=AsyncMock(return_value=[]),
        get_pipeline=AsyncMock(return_value=None),
        get_pipeline_extensions=AsyncMock(return_value={}),
        update_pipeline_extensions=AsyncMock(),
    )
    graph = SimpleNamespace(pipeline_service=service)
    graph.application_api = ApplicationAPI(graph)

    assert graph.application_api.ap is graph
    assert {item['id'] for item in graph.application_api.operation_catalog()} == {
        'pipeline.list',
        'pipeline.get',
        'pipeline.extensions.get',
        'pipeline.extensions.update',
        'knowledge.base.list',
        'knowledge.base.get',
        'knowledge.engine.list',
        'knowledge.engine.schema.get',
    }


@pytest.mark.asyncio
async def test_knowledge_read_operations_delegate_with_typed_outputs():
    service = SimpleNamespace(
        get_knowledge_bases=AsyncMock(return_value=[{'uuid': 'kb-1'}]),
        get_knowledge_base=AsyncMock(return_value={'uuid': 'kb-1'}),
        list_knowledge_engines=AsyncMock(return_value=[{'plugin_id': 'author/engine'}]),
        get_engine_creation_schema=AsyncMock(return_value=[{'name': 'url'}]),
    )
    api = ApplicationAPI(SimpleNamespace(knowledge_service=service))
    context = _context(Permission.RESOURCE_VIEW.value)

    listed = await api.execute('knowledge.base.list', context, KnowledgeBaseListInput())
    fetched = await api.execute(
        'knowledge.base.get', context, KnowledgeBaseGetInput('kb-1'), surface=ApplicationSurface.ASSISTANT
    )
    engines = await api.execute('knowledge.engine.list', context, KnowledgeEngineListInput())
    schema = await api.execute(
        'knowledge.engine.schema.get',
        context,
        KnowledgeEngineSchemaInput('author/engine', 'creation'),
    )

    assert listed.bases == [{'uuid': 'kb-1'}]
    assert fetched.base == {'uuid': 'kb-1'}
    assert engines.engines == [{'plugin_id': 'author/engine'}]
    assert schema.schema == [{'name': 'url'}]
    service.get_knowledge_bases.assert_awaited_once_with(context)
    service.get_knowledge_base.assert_awaited_once_with(context, 'kb-1', include_secret=False)
    service.list_knowledge_engines.assert_awaited_once_with(context)
    service.get_engine_creation_schema.assert_awaited_once_with(context, 'author/engine')
