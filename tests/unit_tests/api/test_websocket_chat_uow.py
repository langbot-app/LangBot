from __future__ import annotations

import asyncio
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
from langbot.pkg.api.http.controller.groups.pipelines.websocket_chat import (
    create_scoped_duplex_tasks,
)
from langbot.pkg.api.http.controller.groups.pipelines.websocket_chat import wait_for_duplex_tasks
from langbot.pkg.utils.bounded_executor import current_blocking_work_scope


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


@pytest.mark.asyncio
async def test_duplex_websocket_tasks_cancel_blocked_peer_when_one_direction_ends() -> None:
    blocked = asyncio.Event()

    async def receive_forever() -> None:
        blocked.set()
        await asyncio.Future()

    async def send_finishes() -> None:
        await blocked.wait()

    receive_task = asyncio.create_task(receive_forever())
    send_task = asyncio.create_task(send_finishes())

    await asyncio.wait_for(
        wait_for_duplex_tasks(receive_task, send_task),
        timeout=1,
    )

    assert receive_task.cancelled()
    assert send_task.done()


@pytest.mark.asyncio
async def test_duplex_websocket_tasks_allow_terminal_send_to_drain() -> None:
    receive_finished = asyncio.Event()
    send_drained = asyncio.Event()

    async def receive_finishes() -> None:
        receive_finished.set()

    async def send_terminal_frame() -> None:
        await receive_finished.wait()
        await asyncio.sleep(0)
        send_drained.set()

    receive_task = asyncio.create_task(receive_finishes())
    send_task = asyncio.create_task(send_terminal_frame())

    await wait_for_duplex_tasks(receive_task, send_task)

    assert send_drained.is_set()
    assert send_task.done()
    assert not send_task.cancelled()


@pytest.mark.asyncio
async def test_duplex_websocket_tasks_share_trusted_workspace_budget() -> None:
    observed: list[tuple[str, str | None]] = []

    async def observe(direction: str) -> None:
        await asyncio.sleep(0)
        observed.append((direction, current_blocking_work_scope()))

    receive_task, send_task = create_scoped_duplex_tasks(
        observe('receive'),
        observe('send'),
        'workspace-a',
    )

    await asyncio.gather(receive_task, send_task)

    assert sorted(observed) == [
        ('receive', 'workspace-a'),
        ('send', 'workspace-a'),
    ]
    assert current_blocking_work_scope() is None
