"""MCP management keys keep their write contract without resource-view scope."""

from types import SimpleNamespace

import pytest
import quart
import sqlalchemy as sa

from langbot.pkg.api.http.controller.groups.resources.mcp import MCPRouterGroup
from langbot.pkg.api.http.service.mcp import MCPService
from langbot.pkg.entity.persistence.mcp import MCPServer
from tests.integration.api.test_application_foundation import context, foundation  # noqa: F401


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
async def mcp_write_api(foundation):  # noqa: F811
    api, ap, engine = foundation
    ap.application_api = api
    ap.tool_mgr = SimpleNamespace(
        mcp_tool_loader=SimpleNamespace(get_session=lambda *_: None, has_session=lambda *_: False)
    )
    ap.mcp_service = MCPService(ap)
    keys = {}
    for name, scopes in [('manager', ['resource.manage']), ('empty', [])]:
        keys[name] = (await ap.apikey_service.create_api_key(context(), name, scopes=scopes))['key']
    async with engine.begin() as connection:
        await connection.execute(
            sa.insert(MCPServer),
            [
                {
                    'uuid': identity,
                    'workspace_uuid': workspace,
                    'name': name,
                    'mode': 'remote',
                    'enable': False,
                    'readme': 'before',
                    'extra_args': {'api_key': 'old-secret'},
                }
                for identity, workspace, name in [
                    ('owned-a', 'workspace-a', 'owned'),
                    ('owned-b', 'workspace-b', 'owned'),
                    ('foreign-b', 'workspace-b', 'foreign'),
                ]
            ],
        )
    app = quart.Quart(__name__)
    audit_changes = []

    @app.after_request
    async def capture_audit(response):
        audit_changes.append(getattr(quart.g, 'operation_log_changes', []))
        return response

    await MCPRouterGroup(ap, app).initialize()
    return app.test_client(), engine, keys, audit_changes


async def test_manage_only_key_updates_and_deletes_without_read_access(mcp_write_api):
    client, engine, keys, audit_changes = mcp_write_api
    headers = {'X-API-Key': keys['manager'], 'X-Workspace-Id': 'workspace-b'}
    endpoint = '/api/v1/mcp/servers/owned'
    assert (await client.get(endpoint, headers=headers)).status_code == 403
    response = await client.put(
        endpoint, headers=headers, json={'readme': 'after', 'extra_args': {'api_key': 'new-secret'}}
    )
    assert response.status_code == 200
    assert await response.get_json() == {'code': 0, 'msg': 'ok', 'data': None}
    assert {'field': 'readme', 'before': 'before', 'after': 'after'} in audit_changes[-1]
    assert 'old-secret' not in str(audit_changes[-1]) and 'new-secret' not in str(audit_changes[-1])
    async with engine.connect() as connection:
        rows = (await connection.execute(sa.select(MCPServer))).mappings().all()
        assert next(row for row in rows if row['uuid'] == 'owned-a')['extra_args'] == {'api_key': 'new-secret'}
        assert all(row['readme'] == 'before' for row in rows if row['workspace_uuid'] == 'workspace-b')
    assert (await client.delete(endpoint, headers=headers)).status_code == 200
    async with engine.connect() as connection:
        assert set(await connection.scalars(sa.select(MCPServer.uuid))) == {'owned-b', 'foreign-b'}
    assert (await client.get(endpoint, headers=headers)).status_code == 403


@pytest.mark.parametrize('method', ['put', 'delete'])
async def test_write_scopes_and_foreign_names_fail_without_mutation(mcp_write_api, method):
    client, engine, keys, _ = mcp_write_api
    request = getattr(client, method)
    kwargs = {'json': {'readme': 'stolen'}} if method == 'put' else {}
    assert (
        await request('/api/v1/mcp/servers/owned', headers={'X-API-Key': keys['empty']}, **kwargs)
    ).status_code == 403
    for name in ('foreign', 'missing'):
        response = await request(
            '/api/v1/mcp/servers/' + name,
            headers={'X-API-Key': keys['manager'], 'X-Workspace-Id': 'workspace-b'},
            **kwargs,
        )
        assert response.status_code == 404
        assert await response.get_json() == {'code': -1, 'msg': 'Server not found'}
    async with engine.connect() as connection:
        rows = (await connection.execute(sa.select(MCPServer))).mappings().all()
        assert len(rows) == 3
        assert all(row['readme'] == 'before' for row in rows)
