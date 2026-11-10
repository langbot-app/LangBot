"""Command processor instances: per-plugin command configuration aligned with Runner config."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.service.agent import AgentService
from langbot.pkg.api.http.service.pipeline import PipelineService
from langbot.pkg.command import processor as command_processor


def manifest(owner: str, name: str, config=None):
    return SimpleNamespace(
        owner=owner,
        metadata=SimpleNamespace(
            name=name,
            label=SimpleNamespace(to_dict=lambda: {'en_US': name}),
            description=None,
        ),
        spec={'config': config} if config is not None else None,
    )


DRAW_SCHEMA = [
    {'name': 'style', 'type': 'string', 'default': 'plain'},
    {'name': 'api_key', 'type': 'string', 'required': True},
]


def make_service(manifests):
    async def list_commands(bound_plugins=None):
        if bound_plugins is None:
            return manifests
        return [item for item in manifests if item.owner in bound_plugins]

    ap = SimpleNamespace(
        plugin_connector=SimpleNamespace(list_commands=AsyncMock(side_effect=list_commands)),
        llm_model_service=SimpleNamespace(apply_default_model=AsyncMock(side_effect=lambda _c, _s, values: values)),
        pipeline_service=SimpleNamespace(_get_default_values_from_schema=PipelineService._get_default_values_from_schema),
        logger=SimpleNamespace(warning=Mock()),
    )
    return AgentService(ap)


@pytest.mark.asyncio
async def test_prepare_fills_defaults_per_command_and_keeps_instance_values():
    service = make_service(
        [manifest('author/painter', 'draw', DRAW_SCHEMA), manifest('author/painter', 'help')],
    )

    config, component_ref, patterns = await service._prepare_command_processor(
        'ws-1',
        {'plugin_id': 'author/painter', 'parameters': {'draw': {'api_key': 'k1'}}},
    )

    assert component_ref == 'plugin:author/painter'
    assert patterns == ['message.received']
    assert config == {
        'plugin': {'id': 'author/painter'},
        'command_config': {'draw': {'style': 'plain', 'api_key': 'k1'}, 'help': {}},
    }


@pytest.mark.asyncio
async def test_two_instances_of_one_plugin_keep_separate_configuration():
    service = make_service([manifest('author/painter', 'draw', DRAW_SCHEMA)])

    first, _, _ = await service._prepare_command_processor(
        'ws-1', {'plugin_id': 'author/painter', 'parameters': {'draw': {'api_key': 'a', 'style': 'anime'}}}
    )
    second, _, _ = await service._prepare_command_processor(
        'ws-1', {'plugin_id': 'author/painter', 'parameters': {'draw': {'api_key': 'b'}}}
    )

    assert first['command_config']['draw'] == {'style': 'anime', 'api_key': 'a'}
    assert second['command_config']['draw'] == {'style': 'plain', 'api_key': 'b'}


@pytest.mark.asyncio
async def test_required_command_parameter_is_enforced_after_draft():
    service = make_service([manifest('author/painter', 'draw', DRAW_SCHEMA)])

    with pytest.raises(ValueError, match='Required command parameter: draw.api_key'):
        await service._prepare_command_processor('ws-1', {'plugin_id': 'author/painter', 'parameters': {}})

    # A component-only draft keeps defaults so the detail form can be filled in later.
    config, _, _ = await service._prepare_command_processor('ws-1', {'plugin_id': 'author/painter'})
    assert config['command_config']['draw'] == {'style': 'plain'}


@pytest.mark.asyncio
async def test_legacy_plugin_without_config_schema_creates_usable_instance():
    """Plugins written before spec.config still get an instance with an empty config per command."""
    service = make_service([manifest('author/legacy', 'ping')])

    config, _, _ = await service._prepare_command_processor('ws-1', {'component_ref': 'plugin:author/legacy'})

    assert config['command_config'] == {'ping': {}}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'data',
    [
        {},
        {'component_ref': 'pipeline'},
        {'component_ref': 'plugin:author/painter/runner'},
        {'plugin_id': 'author/missing'},
    ],
)
async def test_invalid_plugin_selection_is_rejected(data):
    service = make_service([manifest('author/painter', 'draw', DRAW_SCHEMA)])

    with pytest.raises(ValueError, match='Select an installed plugin that provides commands'):
        await service._prepare_command_processor('ws-1', data)


@pytest.mark.asyncio
async def test_metadata_groups_commands_by_plugin_with_schemas():
    service = make_service(
        [manifest('author/painter', 'draw', DRAW_SCHEMA), manifest('author/legacy', 'ping')],
    )

    components = await service._list_command_processor_components('ws-1')

    assert components == [
        {
            'id': 'plugin:author/legacy',
            'plugin_id': 'author/legacy',
            'commands': [{'name': 'ping', 'label': {'en_US': 'ping'}, 'description': None, 'config_schema': []}],
        },
        {
            'id': 'plugin:author/painter',
            'plugin_id': 'author/painter',
            'commands': [
                {'name': 'draw', 'label': {'en_US': 'draw'}, 'description': None, 'config_schema': DRAW_SCHEMA}
            ],
        },
    ]


def test_merge_command_config_backfills_new_schema_fields():
    merged = command_processor.merge_command_config(
        [{'name': 'style', 'default': 'plain'}, {'name': 'size', 'default': 512}],
        {'style': 'anime'},
    )

    assert merged == {'style': 'anime', 'size': 512}


@pytest.mark.parametrize(
    'ref,expected',
    [
        ('plugin:author/name', 'author/name'),
        ('plugin:author/name/runner', None),
        ('plugin:author', None),
        ('author/name', None),
        (None, None),
    ],
)
def test_plugin_id_from_component_ref(ref, expected):
    assert command_processor.plugin_id_from_component_ref(ref) == expected


# ----- Runs and debugging ----------------------------------------------- #


def request_context(workspace='ws-1'):
    from langbot.pkg.api.http.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext

    return RequestContext(
        instance_uuid='instance-test',
        placement_generation=1,
        request_id='command-debug-test',
        auth_type='user_token',
        principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid='account-test'),
        workspace=WorkspaceContext(workspace, 'membership-test', 'owner', frozenset()),
    )


@pytest.fixture
async def run_engine(tmp_path):
    from sqlalchemy.ext.asyncio import create_async_engine

    from langbot.pkg.entity.persistence.base import Base

    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "runs.db"}')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


def debug_service(run_engine, returns, captured):
    from langbot_plugin.api.entities.builtin.command import context as command_context

    service = make_service([manifest('author/painter', 'draw', DRAW_SCHEMA)])
    agent = {
        'uuid': 'cmd-1',
        'kind': 'command_processor',
        'component_ref': 'plugin:author/painter',
        'config': {'command_config': {'draw': {'style': 'anime', 'api_key': 'k'}}},
    }
    service.get_agent = AsyncMock(side_effect=lambda _c, uuid: agent if uuid == 'cmd-1' else None)

    async def build_context(**kwargs):
        captured['build'] = kwargs
        return SimpleNamespace(privilege=1)

    async def execute_command(ctx, bound_plugins=None):
        captured['ctx'] = ctx
        captured['bound_plugins'] = bound_plugins
        for item in returns:
            yield command_context.CommandReturn(**item)

    service.ap.persistence_mgr = SimpleNamespace(get_db_engine=lambda: run_engine)
    service.ap.sess_mgr = SimpleNamespace(get_session_by_launcher=AsyncMock(return_value='session'))
    service.ap.cmd_mgr = SimpleNamespace(build_context=build_context, execute_command=execute_command)
    return service


@pytest.mark.asyncio
async def test_debug_runs_command_with_instance_config_admin_privilege_and_records_a_run(run_engine):
    captured = {}
    service = debug_service(run_engine, [{'text': 'drawing a cat'}], captured)
    context = request_context()

    result = await service.debug_agent(context, 'cmd-1', {'text': 'draw a cat'})

    assert result['status'] == 'completed'
    assert result['outputs'] == [{'text': 'drawing a cat'}]
    assert captured['build']['config'] == {'style': 'anime', 'api_key': 'k'}
    assert captured['build']['command_text'] == 'draw a cat'
    assert captured['ctx'].privilege == 2
    assert captured['bound_plugins'] == ['author/painter']

    runs = await service.get_processor_runs(context, 'cmd-1')
    assert [run['run_id'] for run in runs['items']] == [result['run_id']]
    run = runs['items'][0]
    assert run['status'] == 'completed'
    assert run['binding_id'] == 'command_processor:cmd-1'
    assert run['metadata']['command'] == 'draw'
    assert run['metadata']['source'] == 'debug'

    trace = await service.get_processor_run_events(context, 'cmd-1', result['run_id'])
    assert [(item['type'], item['data']) for item in trace['items']] == [
        ('command.output', {'text': 'drawing a cat'}),
    ]


@pytest.mark.asyncio
async def test_debug_command_error_marks_the_run_failed(run_engine):
    service = debug_service(run_engine, [{'error': 'boom'}], {})
    context = request_context()

    result = await service.debug_agent(context, 'cmd-1', {'text': 'draw'})

    assert result['status'] == 'failed'
    runs = await service.get_processor_runs(context, 'cmd-1')
    assert runs['items'][0]['status'] == 'failed'


@pytest.mark.asyncio
async def test_debug_rejects_commands_the_plugin_does_not_register(run_engine):
    service = debug_service(run_engine, [], {})
    with pytest.raises(ValueError, match='Command not found: paint'):
        await service.debug_agent(request_context(), 'cmd-1', {'text': 'paint'})
    with pytest.raises(ValueError, match='Command text is required'):
        await service.debug_agent(request_context(), 'cmd-1', {'text': '  '})


@pytest.mark.asyncio
async def test_command_runs_are_isolated_per_processor_and_workspace(run_engine):
    service = debug_service(run_engine, [{'text': 'ok'}], {})
    result = await service.debug_agent(request_context(), 'cmd-1', {'text': 'draw'})

    other = {'uuid': 'cmd-2', 'kind': 'command_processor', 'component_ref': 'plugin:author/painter'}
    service.get_agent = AsyncMock(return_value=other)
    assert (await service.get_processor_runs(request_context(), 'cmd-2'))['items'] == []
    with pytest.raises(ValueError, match='Processor run not found'):
        await service.get_processor_run_events(request_context(), 'cmd-2', result['run_id'])
