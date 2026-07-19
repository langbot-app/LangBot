from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.api.http.controller.groups.knowledge.migration import KnowledgeMigrationRouterGroup
from langbot.pkg.workspace.errors import WorkspaceInvariantError, WorkspaceNotFoundError


CONTEXT = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid='workspace-a',
    placement_generation=3,
)


@pytest.mark.asyncio
async def test_background_migration_propagates_generation_change_before_runtime_call():
    connector = SimpleNamespace(
        require_workspace_context=AsyncMock(side_effect=[CONTEXT, WorkspaceNotFoundError('Plugin resource not found')]),
        list_knowledge_engines=AsyncMock(return_value=[]),
    )
    router = object.__new__(KnowledgeMigrationRouterGroup)
    router.ap = SimpleNamespace(
        plugin_connector=connector,
        workspace_service=SimpleNamespace(
            get_local_execution_binding=AsyncMock(return_value=CONTEXT),
        ),
        logger=Mock(),
    )
    router._table_exists = AsyncMock(return_value=False)
    router._set_migration_flag = AsyncMock()
    task_context = SimpleNamespace(trace=Mock())

    with pytest.raises(WorkspaceNotFoundError, match='Plugin resource not found'):
        await router._execute_rag_migration(
            CONTEXT,
            task_context,
            install_plugin=False,
        )

    assert connector.require_workspace_context.await_count == 2
    connector.list_knowledge_engines.assert_not_awaited()
    router._set_migration_flag.assert_not_awaited()


@pytest.mark.asyncio
async def test_cloud_migration_is_rejected_before_legacy_table_access():
    router = object.__new__(KnowledgeMigrationRouterGroup)
    router.ap = SimpleNamespace(
        workspace_service=SimpleNamespace(
            get_local_execution_binding=AsyncMock(side_effect=WorkspaceInvariantError('not an OSS local workspace')),
        ),
        plugin_connector=SimpleNamespace(require_workspace_context=AsyncMock()),
        logger=Mock(),
    )
    router._table_exists = AsyncMock()
    router._set_migration_flag = AsyncMock()
    task_context = SimpleNamespace(trace=Mock())

    with pytest.raises(WorkspaceNotFoundError, match='migration is unavailable'):
        await router._execute_rag_migration(CONTEXT, task_context, install_plugin=False)

    router._table_exists.assert_not_awaited()
    router.ap.plugin_connector.require_workspace_context.assert_not_awaited()
    router._set_migration_flag.assert_not_awaited()
