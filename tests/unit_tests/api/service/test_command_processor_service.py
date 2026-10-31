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
