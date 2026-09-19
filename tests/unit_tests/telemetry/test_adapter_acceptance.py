"""Adapter acceptance boundaries and strict Beta-only production."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langbot_plugin.api.entities.builtin.platform.events import MessageReceivedEvent
from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain, Image

from langbot.pkg.telemetry import diagnostics as d
from langbot.pkg.telemetry import adapter_diagnostics as adapter
from langbot.pkg.telemetry.diagnostic_catalog import snapshot_bot, catalog


def make_manager(version='4.11.0b2', **config):
    ap = SimpleNamespace(instance_config=SimpleNamespace(data={'space': {'url': 'https://example.invalid', **config}}))
    ap.diagnostics = d.DiagnosticsManager(ap, version=version, instance_id='instance-test', capacity=2048)
    return ap.diagnostics


def boundary(fn, operation='send_message', kind='api'):
    fn.__module__ = 'langbot.pkg.platform.adapters.telegram.adapter'
    return d.observe(kind, operation, source='platform', stage='convert' if kind == 'event' else 'accepted')(fn)


def evidence(m):
    return [e for e in m.pending if e['attributes'].get('adapter_evidence') and e['outcome'] != 'started']


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'version,config',
    [
        ('4.11.0', {}),
        ('4.11.0a1', {}),
        ('4.11.0rc1', {}),
        ('4.11.0.dev1', {}),
        ('4.11.0b2+local', {}),
        ('invalid', {}),
        ('4.11.0b2', {'disable_telemetry': True}),
        ('4.11.0b2', {'disable_beta_diagnostics': True}),
    ],
)
async def test_disabled_adapter_produces_nothing(version, config, monkeypatch):
    m = make_manager(version, **config)

    def forbidden(*args, **kwargs):
        raise AssertionError('disabled producer projected adapter metadata')

    monkeypatch.setattr(adapter, 'boundary_fields', forbidden)

    async def call(self):
        return 42

    assert await boundary(call)(SimpleNamespace(ap=m.ap)) == 42
    snapshot_bot(SimpleNamespace(ap=m.ap), listener_registered=True)
    d.adapter_event_received(SimpleNamespace(ap=m.ap), MessageReceivedEvent())
    assert not m.pending
    assert m.counters['generated'] == 0
    await m.flush_once()
    assert m.counters['acked'] == 0


@pytest.mark.asyncio
async def test_nested_api_counted_once_and_only_finite_scenario():
    m = make_manager()
    owner = SimpleNamespace(ap=m.ap)

    async def leaf(self, message, target_type):
        return {'ok': True, 'private_result': 'SECRET_CANARY'}

    third = boundary(leaf)

    async def middle(self, message, target_type):
        return await third(self, message, target_type)

    second = boundary(middle)

    async def outer(self, message, target_type):
        return await second(self, message, target_type)

    await boundary(outer)(
        owner, MessageChain([Plain(text='SECRET_CANARY'), Image(url='https://secret.invalid')]), 'person'
    )
    rows = evidence(m)
    assert len(rows) == 1
    assert rows[0]['attributes'] == {'adapter_evidence': True, 'chat_type': 'person', 'content_type': 'mixed'}
    assert len(m.pending) == 6
    assert 'SECRET_CANARY' not in json.dumps(list(m.pending))
    assert '_adapter_api_active' not in json.dumps(list(m.pending))


@pytest.mark.asyncio
async def test_api_specific_interaction_unknown_and_failure():
    m = make_manager()

    async def call(self, action, params):
        return {'ok': False, 'description': 'SECRET_CANARY'}

    call = boundary(call, 'call_platform_api')
    actions = catalog()['telegram']['specific_apis']
    assert actions
    action = actions[0].removeprefix('platform_api.')
    for name in (action, 'interaction.request', 'SECRET_CANARY'):
        await call(SimpleNamespace(ap=m.ap), name, {'token': 'SECRET_CANARY'})
    rows = evidence(m)
    assert [r['operation'] for r in rows] == [actions[0], 'interaction.request']
    assert all(r['outcome'] == 'failed' for r in rows)
    assert 'SECRET_CANARY' not in json.dumps(list(m.pending))


@pytest.mark.asyncio
async def test_conversion_count_and_private_message_scenario():
    m = make_manager()

    async def convert(self, event):
        return event

    call = boundary(convert, 'platform.target2yiri', 'event')
    event = await call(
        SimpleNamespace(ap=m.ap), MessageReceivedEvent(message_chain=MessageChain([Plain(text='SECRET_CANARY')]))
    )
    assert not evidence(m)
    d.adapter_event_received(SimpleNamespace(ap=m.ap), event)
    await call(SimpleNamespace(ap=m.ap), None)
    await call(SimpleNamespace(ap=m.ap), {'legacy': 'SECRET_CANARY'})
    rows = evidence(m)
    assert len(rows) == 1
    assert rows[0]['platform_event_type'] == 'message.received'
    assert rows[0]['attributes']['chat_type'] == 'person'
    assert rows[0]['attributes']['content_type'] == 'text'
    assert 'SECRET_CANARY' not in json.dumps(list(m.pending))


def test_registered_snapshot_includes_specific_apis_without_claiming_connection():
    m = make_manager()
    entry = catalog()['telegram']
    cls = type(
        'Adapter',
        (),
        {
            '__module__': 'langbot.pkg.platform.adapters.telegram.adapter',
            'get_supported_events': lambda self: entry['events'],
            'get_supported_apis': lambda self: entry['apis'],
        },
    )
    snapshot_bot(
        SimpleNamespace(ap=m.ap, adapter=cls(), execution_context=SimpleNamespace(workspace_uuid=str(uuid4()))),
        listener_registered=True,
    )
    rows = list(m.pending)
    assert rows
    assert all('available' not in r['attributes'] for r in rows)
    assert all(r['attributes']['listener_registered'] for r in rows if r['attributes']['capability_type'] == 'event')
    names = {r['attributes']['capability_name'] for r in rows}
    assert set(entry['specific_apis']) <= names


@pytest.mark.asyncio
async def test_real_dispatch_success_precedes_listener_failure():
    from unittest.mock import AsyncMock
    from langbot.pkg.platform.adapters.telegram.adapter import TelegramAdapter
    from langbot_plugin.api.entities.builtin.platform.events import EBAEvent

    m = make_manager()
    owner = SimpleNamespace(ap=m.ap, listeners={EBAEvent: AsyncMock(side_effect=ValueError('SECRET_CANARY'))})
    with pytest.raises(ValueError):
        await TelegramAdapter._dispatch_eba_event(owner, MessageReceivedEvent())
    rows = evidence(m)
    assert len(rows) == 1 and rows[0]['outcome'] == 'succeeded'
    assert rows[0]['operation'] == 'platform.adapter_event'


def test_event_dispatch_does_not_borrow_another_workspace_trace():
    from langbot.pkg.api.http.context import ExecutionContext

    m = make_manager()
    workspace = str(uuid4())
    owner = SimpleNamespace(
        ap=m.ap,
        execution_context=ExecutionContext(
            instance_uuid=m.instance_id, workspace_uuid=workspace, placement_generation=1
        ),
    )
    with d.Span(m, 'event', 'platform.receive', {'workspace_uuid': str(uuid4()), 'source': 'webui_debug'}).activate():
        d.adapter_event_received(owner, MessageReceivedEvent())
    row = evidence(m)[0]
    assert row['workspace_uuid'] == workspace
    assert not row.get('parent_span_id')
    assert row['source'] == 'platform'
    assert not row['attributes'].get('synthetic')


def test_every_adapter_records_native_and_interaction_dispatch():
    import ast
    from pathlib import Path

    base = Path(__file__).resolve().parents[3] / 'src/langbot/pkg/platform/adapters'
    for directory in catalog():
        tree = ast.parse((base / directory / 'adapter.py').read_text(encoding='utf-8'))
        dispatch = next(
            n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == '_dispatch_eba_event'
        )
        assert any(
            isinstance(n, ast.Call) and ast.unparse(n.func) == 'diagnostics.adapter_event_received'
            for n in ast.walk(dispatch)
        ), directory
