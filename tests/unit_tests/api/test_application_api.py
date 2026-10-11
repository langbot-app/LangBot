import inspect
import typing
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.application import (
    APPLICATION_API_VERSION,
    ApplicationAPI,
    ApplicationSurface,
    PipelineExtensionsUpdateInput,
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


def test_catalog_is_versioned_and_workspace_scoped():
    catalog = {item['id']: item for item in ApplicationAPI.operation_catalog()}

    assert len(catalog) == 4
    assert catalog['pipeline.list']['version'] == APPLICATION_API_VERSION
    assert catalog['pipeline.list']['scope'] == 'workspace'
    assert catalog['pipeline.extensions.update']['side_effect'] is True
    assert catalog['pipeline.list']['input_type'] == 'PipelineListInput'
    assert catalog['pipeline.list']['output_type'] == 'PipelineListOutput'
    assert catalog['pipeline.extensions.update']['error_type'] == 'ApplicationAPIError'
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
    }
