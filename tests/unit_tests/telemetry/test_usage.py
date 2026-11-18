from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import asyncio

import pytest
import quart

from langbot.pkg.telemetry import usage
from langbot.pkg.telemetry import heartbeat
from langbot.pkg.api.http.controller.group import AuthType, RouterGroup
from langbot.pkg.api.context import ExecutionContext, PrincipalContext, PrincipalType


@pytest.fixture(autouse=True)
def reset_usage():
    usage._workspaces.clear()
    yield
    usage._workspaces.clear()


@pytest.fixture
def ap():
    return SimpleNamespace(instance_config=SimpleNamespace(data={'space': {}}))


def test_whitelist_and_normalization(ap):
    usage.inc(ap, 'ws', 'unknown', query='private')
    assert usage.take_batch('ws') is None
    usage.inc(
        ap,
        'ws',
        'kb.file.ingest',
        engine='author/' + 'x' * 80,
        parser='unexpected',
        outcome='failed',
        err='private error message',
        dur='<10s',
        query='private',
    )
    batch = usage.take_batch('ws')
    metric, dims, count = batch['c'][0]
    assert metric == 'kb.file.ingest'
    assert list(dims) == list(usage.SCHEMA[metric])
    assert len(dims['engine']) == 64
    assert dims['parser'] == dims['err'] == 'other'
    assert count == 1
    assert 'private' not in str(batch)
    usage.inc(ap, 'ws', 'kb.file.ingest', outcome='ok', err='ValueError')
    assert usage.take_batch('ws')['c'][1][1]['err'] == ''


def test_ack_preserves_inflight_increments_and_is_idempotent(ap):
    usage.inc(ap, 'ws', 'kb.create', engine='author/engine')
    sent = usage.take_batch('ws')
    usage.inc(ap, 'ws', 'kb.create', engine='author/engine')
    usage.ack('ws', sent)
    usage.ack('ws', sent)
    remaining = usage.take_batch('ws')
    assert remaining['c'][0][2] == 1
    assert remaining['batch_id'] != sent['batch_id']
    usage.ack('ws', remaining)
    assert usage.take_batch('ws') is None
    assert not usage._workspaces


def test_nack_retries_same_id_then_merges(ap):
    usage.inc(ap, 'ws', 'kb.create', engine='author/engine')
    sent = usage.take_batch('ws')
    usage.nack('ws', sent)
    assert usage.take_batch('ws') == sent
    usage.inc(ap, 'ws', 'kb.create', engine='author/engine')
    merged = usage.take_batch('ws')
    assert merged['batch_id'] != sent['batch_id']
    assert merged['since'] == sent['since']
    assert merged['c'][0][2] == 2


def test_limits(ap, monkeypatch):
    for index in range(257):
        usage.inc(ap, 'ws', 'kb.create', engine=f'author/engine{index}')
    assert len(usage.take_batch('ws')['c']) == 256
    usage.inc(ap, 'ws', 'kb.create', engine='author/engine0')
    assert usage.take_batch('ws')['c'][0][2] == 2
    monkeypatch.setattr(usage, 'MAX_WORKSPACES', 2)
    usage.inc(ap, 'second', 'kb.create')
    usage.inc(ap, 'third', 'kb.create')
    assert usage.take_batch('third') is None
    key = next(iter(usage._workspaces['ws'].counts))
    usage._workspaces['ws'].counts[key] = 1000001
    batch = usage.take_batch('ws')
    assert batch['c'][0][2] == 1000000
    usage.ack('ws', batch)
    assert usage.take_batch('ws')['c'][0][2] == 1


def test_disabled_and_bad_config_are_noop(ap):
    ap.instance_config.data['space']['disable_telemetry'] = True
    usage.inc(ap, 'ws', 'kb.create', engine='author/engine')
    usage.inc(None, 'ws', 'kb.create')
    assert usage.take_batch('ws') is None


@pytest.mark.parametrize('metric', ['alert.state', 'alert.settings.update', 'alert.incident', 'alert.delivery'])
def test_alert_schema_and_values(ap, metric):
    dims = {name: usage.ALERT_ENUMS[name][0] for name in usage.SCHEMA[metric]}
    for name in dims:
        for value in usage.ALERT_ENUMS[name]:
            valid = {**dims, name: value}
            assert usage.normalize(metric, valid) == tuple(valid.values())
            usage.inc(ap, 'ws', metric, **valid)
        for invalid in ('private@example.com', '', None, 1):
            bad = {**dims, name: invalid}
            if name == 'rule':
                assert usage.normalize(metric, bad)[0] == 'other'
            else:
                with pytest.raises(ValueError):
                    usage.normalize(metric, bad)
                usage.inc(ap, 'invalid', metric, **bad)
                assert usage.take_batch('invalid') is None
    entries = usage.take_batch('ws')['c']
    assert all(list(entry[1]) == list(usage.SCHEMA[metric]) for entry in entries)


def test_alert_outcome_is_metric_specific(ap):
    assert usage.ALERT_ENUMS == {
        'enabled': ('yes', 'no'),
        'channel': ('auto', 'instance', 'space', 'off'),
        'rule': ('pipeline_failures', 'model_failures', 'bot_offline', 'other'),
        'event': ('opened', 'resolved'),
        'notice': ('fired', 'reminder', 'resolved', 'test'),
        'via': ('email', 'space', 'webhook'),
        'outcome': ('ok', 'failed', 'rate_limited'),
    }
    assert usage.normalize('kb.migration.run', {'outcome': 'rate_limited'}) == ('other',)
    usage.inc(ap, 'ws', 'alert.delivery', notice='test', via='space', outcome='cancelled')
    assert usage.take_batch('ws') is None


@pytest.mark.parametrize('amount', [0, -1, None, 1.5, True, '3'])
def test_invalid_usage_amount_is_ignored(ap, amount):
    usage.inc(ap, 'ws', 'alert.incident', rule='bot_offline', event='resolved', amount=amount)
    assert usage.take_batch('ws') is None


def test_usage_amount_clamp_and_ack(ap):
    dims = {'rule': 'bot_offline', 'event': 'resolved'}
    usage.inc(ap, 'ws', 'alert.incident', amount=usage.MAX_COUNT + 1, **dims)
    batch = usage.take_batch('ws')
    assert batch['c'][0][2] == usage.MAX_COUNT
    usage.inc(ap, 'ws', 'alert.incident', amount=3, **dims)
    usage.ack('ws', batch)
    assert usage.take_batch('ws')['c'][0][2] == 3


@pytest.mark.parametrize(
    'principal,headers,client',
    [
        (PrincipalType.ACCOUNT, {'User-Agent': 'lbctl/1.2.3 (linux/amd64)'}, 'webui'),
        (PrincipalType.API_KEY, {'User-Agent': 'lbctl/1.2.3 (linux/amd64)'}, 'lbctl'),
        (PrincipalType.API_KEY, {'User-Agent': 'custom-client'}, 'api_other'),
        (None, {'X-API-Key': 'invalid', 'User-Agent': 'lbctl/1.2.3 (linux/amd64)'}, 'lbctl'),
    ],
)
def test_clients_and_invalid_command(ap, principal, headers, client):
    context = SimpleNamespace(workspace_uuid='ws', principal=SimpleNamespace(principal_type=principal))
    headers['X-LangBot-Client-Command'] = 'private command/query'
    usage.record_http(ap, context, headers, 'unknown-group', 'GET', 401)
    entries = usage.take_batch('ws')['c']
    assert entries[0][1] == {'group': 'other', 'method': 'GET', 'client': client, 'status': '4xx'}
    if client == 'lbctl':
        assert entries[1][1] == {'cmd': 'other', 'status': '4xx'}
        assert entries[2][1] == {'version': '1.2.3', 'os': 'linux'}
    else:
        assert len(entries) == 1


@pytest.mark.asyncio
async def test_route_authentication_failure_is_counted(ap):
    class Group(RouterGroup):
        name, path = 'usage_test', '/test'

        async def initialize(self):
            @self.route('', auth_type=AuthType.API_KEY)
            async def endpoint(request_context):
                return self.success()

    app = quart.Quart(__name__)
    ap._telemetry_default_workspace = 'default'
    group = Group(ap, app)
    await group.initialize()
    response = await app.test_client().get('/test')
    assert response.status_code == 401
    assert usage.take_batch('default')['c'][0][1]['status'] == '4xx'


@pytest.mark.asyncio
@pytest.mark.parametrize('failed', [False, True])
async def test_real_ingest_outcome(ap, failed):
    from tests.unit_tests.rag.test_file_storage import _make_kb, _upload_key, CONTEXT

    kb = _make_kb()
    kb.ap.instance_config = ap.instance_config
    kb._ingest_document = AsyncMock(
        return_value={
            'status': 'failed' if failed else 'completed',
            'error_message': 'private error',
            'document_id': 'document',
        }
    )
    file = SimpleNamespace(uuid='file', file_name=_upload_key('private.pdf'), extension='pdf', artifact_id=None)
    if failed:
        with pytest.raises(Exception, match='private error'):
            await kb._store_file_task(CONTEXT, file, Mock())
    else:
        await kb._store_file_task(CONTEXT, file, Mock())
    entries = usage.take_batch(CONTEXT.workspace_uuid)['c']
    ingestion = next(dims for metric, dims, _count in entries if metric == 'kb.file.ingest')
    assert ingestion['outcome'] == ('failed' if failed else 'ok')
    assert ingestion['err'] == ('Exception' if failed else '')
    assert ingestion['parser'] == 'builtin'
    assert 'private' not in str(entries)


@pytest.mark.asyncio
async def test_payload_and_cloud_no_new_sql(ap, monkeypatch):
    ap.persistence_mgr = SimpleNamespace(mode=SimpleNamespace(value='cloud_runtime'), execute_async=AsyncMock())
    ap.rag_mgr = SimpleNamespace(
        knowledge_bases={
            ('ws', 'kb'): SimpleNamespace(get_knowledge_engine_plugin_id=lambda: 'author/engine'),
            ('other', 'kb'): SimpleNamespace(get_knowledge_engine_plugin_id=lambda: 'private/other'),
        }
    )
    monkeypatch.setenv('LANGBOT_DEPLOY_SOURCE', 'lbctl')
    monkeypatch.setenv('LANGBOT_DEPLOY_TOOL_VERSION', '1.2.3')
    usage.inc(ap, 'ws', 'lbctl.client', version='1.2.3', os='linux')
    payload = await heartbeat.build_heartbeat_payload(ap, workspace_uuid='ws', workspace_resource={})
    features = payload['features']
    assert features['kb_engines'] == ['author/engine']
    assert features['kb_file_count'] == -1
    assert features['deploy_source'] == 'lbctl'
    assert features['deploy_tool_version'] == '1.2.3'
    assert features['lbctl_versions'] == ['1.2.3']
    assert features['usage']['v'] == 1
    ap.persistence_mgr.execute_async.assert_not_awaited()
    ap.instance_config.data['space']['disable_telemetry'] = True
    payload = await heartbeat.build_heartbeat_payload(ap, workspace_uuid='ws', workspace_resource={})
    assert 'usage' not in payload['features']


@pytest.mark.parametrize('value,expected', [('1', 30), ('60', 60), ('invalid', 86400)])
def test_interval(monkeypatch, value, expected):
    monkeypatch.setenv('LANGBOT_TELEMETRY_HEARTBEAT_SECONDS', value)
    assert heartbeat.heartbeat_interval(False) == expected


@pytest.mark.parametrize(
    'principal,pipeline,expected',
    [
        (PrincipalContext(PrincipalType.ACCOUNT), None, 'webui_test'),
        (PrincipalContext(PrincipalType.API_KEY), None, 'api'),
        (PrincipalContext(PrincipalType.PLUGIN), None, 'plugin'),
        (PrincipalContext(PrincipalType.PROCESSOR, processor_kind='agent'), None, 'agent'),
        (PrincipalContext(PrincipalType.ACCOUNT), 'pipeline', 'pipeline'),
    ],
)
def test_retrieval_origin(principal, pipeline, expected):
    context = ExecutionContext('instance', 'ws', 1, pipeline_uuid=pipeline, trigger_principal=principal)
    assert usage.retrieval_origin(context) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('accepted', [True, False])
async def test_heartbeat_acknowledges_only_success(ap, monkeypatch, accepted):
    usage.inc(ap, 'ws', 'kb.create')
    batch = usage.take_batch('ws')
    ap.persistence_mgr = SimpleNamespace(mode=SimpleNamespace(value='oss_compat'))
    ap.logger = Mock()

    async def send(payload):
        usage.inc(ap, 'ws', 'kb.create')
        return accepted

    ap.telemetry = SimpleNamespace(send=AsyncMock(side_effect=send))
    monkeypatch.setattr(
        heartbeat,
        'build_heartbeat_payloads',
        AsyncMock(
            return_value=[
                {
                    'workspace_uuid': 'ws',
                    'features': {'usage': batch},
                }
            ]
        ),
    )
    monkeypatch.setattr(heartbeat.asyncio, 'sleep', AsyncMock(side_effect=[None, asyncio.CancelledError()]))
    with pytest.raises(asyncio.CancelledError):
        await heartbeat.heartbeat_loop(ap)
    assert usage.take_batch('ws')['c'][0][2] == (1 if accepted else 2)


@pytest.mark.asyncio
@pytest.mark.parametrize('failed', [False, True])
async def test_share_submit_outcome_and_mode(ap, failed):
    app = quart.Quart(__name__)
    context = SimpleNamespace(workspace_uuid='ws')

    @usage.observe_share(ap, 'prompt')
    async def submit(request_context):
        if failed:
            raise ValueError('private prompt content')
        return quart.jsonify({'code': 0})

    async with app.test_request_context('/share', method='POST', json={'mode': 'update'}):
        if failed:
            with pytest.raises(ValueError):
                await submit(request_context=context)
        else:
            await submit(request_context=context)
    entry = usage.take_batch('ws')['c'][0]
    assert entry == [
        'ugc.share.submit',
        {
            'type': 'prompt',
            'mode': 'update',
            'outcome': 'failed' if failed else 'ok',
            'err': 'ValueError' if failed else '',
        },
        1,
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize('failed', [False, True])
async def test_community_mcp_install_outcome(ap, failed):
    class Installer:
        @usage.observe_install('mcp', 'market')
        async def install(self, context, mcp_data):
            if failed:
                raise ValueError('private configuration')

    installer = Installer()
    installer.ap = ap
    context = SimpleNamespace(workspace_uuid='ws')
    data = {'source': 'community', 'required_inputs': [{'name': 'PRIVATE_TOKEN'}]}
    if failed:
        with pytest.raises(ValueError):
            await installer.install(context, data)
    else:
        await installer.install(context, data)
    assert usage.take_batch('ws')['c'] == [
        [
            'ugc.install',
            {
                'type': 'mcp',
                'source': 'community',
                'outcome': 'failed' if failed else 'ok',
                'unfilled': 'yes',
            },
            1,
        ]
    ]


@pytest.mark.asyncio
async def test_upload_records_size_and_extension(ap):
    from tests.unit_tests.rag.test_file_storage import _make_kb, _upload_key, CONTEXT

    kb = _make_kb()
    kb.ap.instance_config = ap.instance_config

    def create_task(coroutine, **kwargs):
        coroutine.close()
        return SimpleNamespace(id=1, task=Mock())

    kb.ap.task_mgr.create_user_task.side_effect = create_task
    await kb.store_file(CONTEXT, _upload_key('private.PDF'))
    entry = usage.take_batch(CONTEXT.workspace_uuid)['c'][0]
    assert entry[0] == 'kb.file.upload'
    assert entry[1]['ext'] == 'pdf'
    assert entry[1]['size'] == '<1M'
    assert 'private' not in str(entry)


@pytest.mark.asyncio
@pytest.mark.parametrize('denied', [False, True])
async def test_mcp_tool_boundary(ap, monkeypatch, denied):
    from contextlib import asynccontextmanager
    from langbot.pkg.api.mcp import server as mcp_server

    @asynccontextmanager
    async def tenant_scope(workspace_uuid):
        assert workspace_uuid == 'ws'
        yield

    class Denied(Exception):
        status_code = 403

    ap.persistence_mgr = SimpleNamespace(tenant_scope=tenant_scope)
    server = mcp_server.LangBotMCPServer.__new__(mcp_server.LangBotMCPServer)
    server.ap = ap
    server.mcp = SimpleNamespace(tool=lambda **options: lambda function: function)
    monkeypatch.setattr(mcp_server, 'get_request_context', lambda: SimpleNamespace(workspace_uuid='ws'))
    monkeypatch.setattr(mcp_server, 'get_workspace_language', AsyncMock(return_value='en_US'))

    @server.tool()
    async def list_knowledge_bases():
        if denied:
            raise Denied()
        return '[]'

    if denied:
        with pytest.raises(Denied):
            await list_knowledge_bases()
    else:
        assert await list_knowledge_bases() == '[]'
    assert usage.take_batch('ws')['c'] == [
        [
            'api.call',
            {
                'group': 'mcp:knowledge',
                'method': 'POST',
                'client': 'mcp',
                'status': '4xx' if denied else '2xx',
            },
            1,
        ]
    ]
