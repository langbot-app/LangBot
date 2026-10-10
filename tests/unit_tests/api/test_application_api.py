from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.application import ApplicationAPI
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

    assert catalog['pipeline.list']['version'] == 'v1'
    assert catalog['pipeline.list']['scope'] == 'workspace'
    assert catalog['pipeline.extensions.update']['side_effect'] is True
