from contextlib import asynccontextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import quart
from pydantic import BaseModel

from langbot.pkg.api.application import ApplicationAPI, Input, Operation
from langbot.pkg.api.application.auxiliary import ImageOutput
from langbot.pkg.api.application.contracts import ApplicationAPIError, ApplicationAPIException
from langbot.pkg.api.authz import Permission, permissions_for_role
from langbot.pkg.api.context import PrincipalType
from langbot.pkg.api.http.controller.groups.operations import OperationsRouterGroup
from langbot.pkg.api.http.controller.groups.system import SYSTEM_CAPABILITY_OPERATIONS
from langbot.pkg.operation_trace.service import OPERATION_LEVEL_READ


pytestmark = pytest.mark.asyncio


class Payload(Input):
    count: int = 1


@pytest.fixture
def host(monkeypatch):
    @asynccontextmanager
    async def scope(workspace):
        yield

    async def handler(ap, context, payload):
        return {'workspace': context.workspace_uuid, 'count': payload.count}

    async def stream_handler(ap, context, payload):
        async def events():
            yield {'workspace': context.workspace_uuid, 'count': payload.count}
            if payload.count < 0:
                raise ApplicationAPIException(ApplicationAPIError('test_error', 'Test failure', 400))

        return events()

    monkeypatch.setattr('langbot.pkg.api.application.api.get_workspace_language', AsyncMock(return_value='en_US'))
    monkeypatch.setattr('langbot.pkg.api.http.controller.group.get_workspace_language', AsyncMock(return_value='en_US'))
    access = SimpleNamespace(
        workspace=SimpleNamespace(uuid='workspace-a'),
        membership=SimpleNamespace(uuid='member-a', role='developer', projection_revision=1),
        execution=SimpleNamespace(instance_uuid='instance-a', placement_generation=1),
    )
    identity = SimpleNamespace(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=1,
        api_key_uuid='key-a',
        permissions=permissions_for_role('developer'),
    )
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(tenant_scope=scope),
        workspace_service=SimpleNamespace(
            get_execution_binding=AsyncMock(return_value=SimpleNamespace(instance_uuid='instance-a')),
        ),
        user_service=SimpleNamespace(
            get_authenticated_account=AsyncMock(
                return_value=SimpleNamespace(uuid='account-a', user='test@example.com')
            ),
        ),
        workspace_collaboration_service=SimpleNamespace(resolve_account_workspace=AsyncMock(return_value=access)),
        apikey_service=SimpleNamespace(authenticate_api_key=AsyncMock(return_value=identity)),
        workspace_settings_service=SimpleNamespace(
            effective_level=AsyncMock(return_value=OPERATION_LEVEL_READ),
            record=AsyncMock(),
        ),
        logger=Mock(),
        identity=identity,
        access=access,
    )
    ap.application_api = ApplicationAPI(
        ap,
        operations=[
            Operation('agent.list', Permission.RESOURCE_VIEW, handler, Payload, dict),
            Operation('agent.create', Permission.RESOURCE_MANAGE, handler, Payload, dict, side_effect=True),
            Operation(
                'bot.list',
                Permission.RESOURCE_VIEW,
                handler,
                Payload,
                dict,
                principals=frozenset({PrincipalType.ACCOUNT}),
            ),
            Operation('agent.debug.stream', Permission.RUNTIME_OPERATE, stream_handler, Payload, dict, streaming=True),
        ],
    )
    return ap


async def client(host):
    app = quart.Quart(__name__)
    await OperationsRouterGroup(host, app).initialize()
    return app.test_client()


@pytest.mark.parametrize(
    'headers,expected',
    [
        ({'X-API-Key': 'test-key'}, {'agent.list', 'agent.create'}),
        ({'Authorization': 'Bearer test-token'}, {'agent.list', 'agent.create', 'bot.list'}),
    ],
)
async def test_catalog_filters_principals_and_exposure(host, headers, expected):
    http = await client(host)
    response = await http.get('/api/v1/operations', headers=headers)
    assert response.status_code == 200
    operations = (await response.get_json())['operations']
    assert {item['id'] for item in operations} == expected
    assert set(operations[0]) == {
        'id',
        'label',
        'summary',
        'description',
        'domain',
        'risk',
        'side_effect',
        'streaming',
        'permission',
        'version',
        'input_schema',
        'output_schema',
    }
    filtered = await http.get('/api/v1/operations?domain=agent&q=LIST', headers=headers)
    assert [item['id'] for item in (await filtered.get_json())['operations']] == ['agent.list']


@pytest.mark.parametrize('headers', [{'X-API-Key': 'test-key'}, {'Authorization': 'Bearer test-token'}])
async def test_catalog_and_description_hide_denied_operations(host, headers):
    host.identity.permissions = permissions_for_role('viewer')
    host.access.membership.role = 'viewer'
    http = await client(host)
    response = await http.get('/api/v1/operations', headers=headers)
    assert 'agent.create' not in {item['id'] for item in (await response.get_json())['operations']}
    for name in ['agent.create', 'agent.debug.stream', 'missing']:
        response = await http.get(f'/api/v1/operations/{name}', headers=headers)
        assert response.status_code == 404
    response = await http.get('/api/v1/operations/agent.list', headers=headers)
    assert (await response.get_json())['id'] == 'agent.list'


@pytest.mark.parametrize('body', [{}, {'workspace': 'other', 'workspace_uuid': 'other'}])
async def test_execute_uses_trusted_workspace(host, body):
    http = await client(host)
    response = await http.post('/api/v1/operations/agent.list', json=body, headers={'X-API-Key': 'test-key'})
    assert response.status_code == 200
    assert await response.get_json() == {'code': 0, 'msg': 'ok', 'data': {'workspace': 'workspace-a', 'count': 1}}
    assert host.workspace_service.get_execution_binding.await_args.args == ('workspace-a',)


async def test_empty_body(host):
    http = await client(host)
    response = await http.post('/api/v1/operations/agent.list', headers={'X-API-Key': 'test-key'})
    assert response.status_code == 200


async def test_malformed_json(host):
    http = await client(host)
    response = await http.post(
        '/api/v1/operations/agent.list', data='{', headers={'X-API-Key': 'test-key', 'Content-Type': 'application/json'}
    )
    assert response.status_code == 400
    assert (await response.get_json())['code'] == 'invalid_input'


async def test_authentication_required(host):
    http = await client(host)
    response = await http.get('/api/v1/operations')
    assert response.status_code == 401


async def test_principal_constraint_is_enforced_on_invocation(host):
    http = await client(host)
    response = await http.post('/api/v1/operations/bot.list', json={}, headers={'X-API-Key': 'test-key'})
    assert response.status_code == 401
    assert (await response.get_json())['code'] == 'invalid_authentication'
    response = await http.get('/api/v1/operations/bot.list', headers={'X-API-Key': 'test-key'})
    assert response.status_code == 404


@pytest.mark.parametrize('body', [[], None, {'count': 'wrong'}, {'unknown': True}])
async def test_invalid_input(host, body):
    import json

    http = await client(host)
    response = await http.post(
        '/api/v1/operations/agent.list',
        data=json.dumps(body),
        headers={'X-API-Key': 'test-key', 'Content-Type': 'application/json'},
    )
    assert response.status_code == 400
    assert (await response.get_json())['code'] == 'invalid_input'


@pytest.mark.parametrize(
    'path,status,code',
    [
        ('agent.create', 403, 'permission_denied'),
        ('missing', 404, 'unknown_operation'),
        ('agent.debug.stream', 400, 'invalid_execution_mode'),
        ('agent.list/stream', 400, 'invalid_execution_mode'),
    ],
)
async def test_execute_errors(host, path, status, code):
    host.identity.permissions = permissions_for_role('viewer')
    http = await client(host)
    response = await http.post(f'/api/v1/operations/{path}', json={}, headers={'X-API-Key': 'test-key'})
    assert response.status_code == status
    body = await response.get_json()
    assert body['code'] == code
    assert set(body) == {'code', 'msg', 'data'}


@pytest.mark.parametrize(
    'count,ending',
    [(1, 'event: done\ndata: {}\n\n'), (-1, 'event: error\ndata: {"code": "test_error", "msg": "Test failure"}\n\n')],
)
async def test_stream_events_and_errors(host, count, ending):
    http = await client(host)
    response = await http.post(
        '/api/v1/operations/agent.debug.stream/stream',
        json={'count': count, 'workspace': 'other'},
        headers={'X-API-Key': 'test-key'},
    )
    assert response.status_code == 200
    assert response.mimetype == 'text/event-stream'
    text = await response.get_data(as_text=True)
    assert text == f'data: {{"workspace": "workspace-a", "count": {count}}}\n\n{ending}'


async def test_stream_permission_error(host):
    host.identity.permissions = permissions_for_role('viewer')
    http = await client(host)
    response = await http.post(
        '/api/v1/operations/agent.debug.stream/stream', json={}, headers={'X-API-Key': 'test-key'}
    )
    text = await response.get_data(as_text=True)
    assert 'event: error\n' in text and 'permission_denied' in text
    assert 'event: done' not in text


async def test_capability_flags():
    assert {
        'operation.invoke',
        'operation.stream',
        'operation.binary_base64',
        'plugin.permissions.confirm_api_key',
    } <= set(SYSTEM_CAPABILITY_OPERATIONS)


async def test_nested_binary_output(host):
    class BinaryModel(BaseModel):
        content: bytes

    original = {'nested': [BinaryModel(content=b'\xfb\xff'), {'raw': bytearray(b'\x00\xff')}], 'tuple': (b'a',)}

    async def handler(ap, context, payload):
        return original

    host.application_api._operations['agent.list'] = replace(
        host.application_api._operations['agent.list'], handler=handler
    )
    http = await client(host)
    response = await http.post('/api/v1/operations/agent.list', json={}, headers={'X-API-Key': 'test-key'})
    assert response.status_code == 200
    assert (await response.get_json())['data'] == {'nested': [{'content': '+/8='}, {'raw': 'AP8='}], 'tuple': ['YQ==']}
    assert original['nested'][0].content == b'\xfb\xff'
    assert original['nested'][1]['raw'] == bytearray(b'\x00\xff')


async def test_binary_stream_event(host):
    async def handler(ap, context, payload):
        async def events():
            yield {'nested': [{'content': b'\xfb\xff', 'raw': bytearray(b'a')}]}

        return events()

    host.application_api._operations['agent.debug.stream'] = replace(
        host.application_api._operations['agent.debug.stream'], handler=handler
    )
    http = await client(host)
    response = await http.post(
        '/api/v1/operations/agent.debug.stream/stream', json={}, headers={'X-API-Key': 'test-key'}
    )
    assert response.status_code == 200
    assert await response.get_data(as_text=True) == (
        'data: {"nested": [{"content": "+/8=", "raw": "YQ=="}]}\n\nevent: done\ndata: {}\n\n'
    )


async def test_binary_output_schema(host):
    host.application_api._operations['agent.list'] = replace(
        host.application_api._operations['agent.list'], output_type=ImageOutput
    )
    http = await client(host)
    response = await http.get('/api/v1/operations/agent.list', headers={'X-API-Key': 'test-key'})
    properties = (await response.get_json())['output_schema']['properties']
    assert properties['content'] == {'title': 'Content', 'type': 'string', 'contentEncoding': 'base64'}
    assert 'contentEncoding' not in properties['media_type']
    internal = next(item for item in host.application_api.operation_catalog() if item['id'] == 'agent.list')
    assert internal['output_schema']['properties']['content']['format'] == 'binary'


@pytest.mark.parametrize('operation_id', ['agent.create', 'plugin.permissions.update'])
async def test_operation_audit_identifies_api_key(host, operation_id):
    host.application_api._operations[operation_id] = replace(
        host.application_api._operations['agent.create'],
        operation_id=operation_id,
    )
    http = await client(host)
    response = await http.post(f'/api/v1/operations/{operation_id}', json={}, headers={'X-API-Key': 'test-key'})
    assert response.status_code == 200
    record = host.workspace_settings_service.record.await_args
    assert record.kwargs['principal_type'] == 'api_key'
    assert record.kwargs['api_key_uuid'] == 'key-a'
    assert record.kwargs['route'] == operation_id
