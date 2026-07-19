from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.context import (
    PrincipalContext,
    PrincipalType,
    RequestContext,
    WorkspaceContext,
)
from langbot.pkg.api.http.controller.groups.pipelines.websocket_chat import WebSocketChatRouterGroup


@pytest.mark.asyncio
async def test_websocket_pipeline_lookup_opens_workspace_uow_after_auth_scope_closed() -> None:
    workspace_uuid = 'workspace-a'
    scopes: list[str] = []
    in_scope = False

    @asynccontextmanager
    async def tenant_uow(selected_workspace_uuid: str):
        nonlocal in_scope
        assert not in_scope
        in_scope = True
        scopes.append(selected_workspace_uuid)
        try:
            yield
        finally:
            in_scope = False

    async def get_pipeline(_context, _pipeline_uuid):
        assert in_scope
        return {'uuid': 'pipeline-a'}

    adapter = Mock()
    router = object.__new__(WebSocketChatRouterGroup)
    router.ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(
            mode=SimpleNamespace(value='cloud_runtime'),
            tenant_uow=tenant_uow,
        ),
        pipeline_service=SimpleNamespace(get_pipeline=AsyncMock(side_effect=get_pipeline)),
        platform_mgr=SimpleNamespace(get_websocket_proxy_bot=AsyncMock(return_value=SimpleNamespace(adapter=adapter))),
    )
    request_context = RequestContext(
        instance_uuid='instance-a',
        placement_generation=1,
        request_id='request-a',
        auth_type='user_token',
        principal=PrincipalContext(
            principal_type=PrincipalType.ACCOUNT,
            account_uuid='account-a',
        ),
        workspace=WorkspaceContext(
            workspace_uuid=workspace_uuid,
            membership_uuid='membership-a',
            role='owner',
            permissions=frozenset(),
        ),
    )

    result = await router._get_scoped_adapter(request_context, 'pipeline-a')

    assert result is adapter
    assert scopes == [workspace_uuid]
