import importlib
import importlib.util
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
import quart

from langbot.pkg.api.http.context import RequestContext, WorkspaceContext, PrincipalContext, PrincipalType
from langbot.pkg.api.http.authz import permissions_for_role


@pytest.mark.asyncio
async def test_manual_routes_user_token_permissions_and_strict_request():
    path = 'langbot.pkg.api.http.controller.groups.pipelines.migration'
    assert importlib.util.find_spec(path), 'manual migration routes missing'
    cls = importlib.import_module(path).PipelineMigrationRouterGroup
    from langbot.pkg.api.http.service.pipeline_migration import MigrationError

    app = quart.Quart(__name__)
    router = cls(NS(persistence_mgr=NS()), app)
    router._authenticate_support_admin = AsyncMock(return_value=None)
    router._authenticate_account = AsyncMock(return_value=(NS(uuid='account'), 'test@example.invalid'))
    viewer = RequestContext(
        'instance',
        1,
        'request',
        'user_token',
        PrincipalContext(PrincipalType.ACCOUNT, account_uuid='account'),
        WorkspaceContext('workspace', 'membership', 'viewer', permissions_for_role('viewer')),
    )
    router._resolve_account_context = AsyncMock(return_value=viewer)
    await router.initialize()
    router.service = NS(
        preview=AsyncMock(return_value={'items': [], 'total': 0}), execute=AsyncMock(return_value={'task_id': 1})
    )
    client = app.test_client()
    base = '/api/v1/pipelines/_/migration'
    assert (await client.get(base + '/preview')).status_code == 401
    assert (await client.get(base + '/preview', headers={'X-API-Key': 'synthetic'})).status_code == 401
    headers = {'Authorization': 'Bearer synthetic'}
    assert (await client.get(base + '/preview', headers=headers)).status_code == 200
    assert (await client.post(base + '/execute', headers=headers, json={})).status_code == 403
    router.service.execute.assert_not_awaited()
    manager = RequestContext(
        'instance',
        1,
        'request',
        'user_token',
        viewer.principal,
        WorkspaceContext('workspace', 'membership', 'developer', permissions_for_role('developer')),
    )
    router._resolve_account_context.return_value = manager
    router.service.execute.side_effect = MigrationError('confirmation_required', 400)
    response = await client.post(base + '/execute', headers=headers, json={'confirmed': 'true'})
    assert response.status_code == 400
    assert 'confirmation_required' in await response.get_data(as_text=True)
    router.service.execute.side_effect = None
    response = await client.post(base + '/execute', headers=headers, json={'confirmed': True, 'items': []})
    assert (await response.get_json())['data']['task_id'] == 1
