from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import quart
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.controller import group
from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode


pytestmark = pytest.mark.asyncio


async def test_authenticated_route_does_not_hold_database_session_during_external_wait():
    entered = asyncio.Event()
    release = asyncio.Event()
    observations: list[bool] = []
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    persistence = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    persistence.db = SimpleNamespace(get_engine=lambda: engine)

    class BlockingRouter(group.RouterGroup):
        name = 'blocking-route-test'
        path = '/blocking-route-test'

        async def initialize(self) -> None:
            @self.route('', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
            async def _():
                observations.append(persistence.current_session() is None)
                entered.set()
                await release.wait()
                observations.append(persistence.current_session() is None)
                return self.success(data={})

    account = SimpleNamespace(uuid='account-a', user='owner@example.com')
    access = SimpleNamespace(
        execution=SimpleNamespace(instance_uuid='instance-a', placement_generation=1),
        workspace=SimpleNamespace(uuid='workspace-a'),
        membership=SimpleNamespace(uuid='membership-a', role='owner', projection_revision=1),
    )
    application = SimpleNamespace(
        persistence_mgr=persistence,
        deployment=SimpleNamespace(multi_workspace_enabled=False),
        user_service=SimpleNamespace(get_authenticated_account=AsyncMock(return_value=account)),
        workspace_collaboration_service=SimpleNamespace(resolve_account_workspace=AsyncMock(return_value=access)),
        logger=Mock(),
    )
    quart_app = quart.Quart(__name__)
    await BlockingRouter(application, quart_app).initialize()
    client = quart_app.test_client()

    request = asyncio.create_task(
        client.get(
            '/blocking-route-test',
            headers={'Authorization': 'Bearer token', 'X-Workspace-Id': 'workspace-a'},
        )
    )
    try:
        await entered.wait()
        assert observations == [True]
        release.set()
        response = await request
        assert response.status_code == 200
        assert observations == [True, True]
    finally:
        release.set()
        if not request.done():
            await request
        await engine.dispose()
