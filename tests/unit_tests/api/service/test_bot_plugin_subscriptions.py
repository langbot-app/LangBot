"""Validate subscription identity, workspace boundaries and persisted updates."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.http.service.bot import BotService
from langbot.pkg.agent.runner.errors import RunnerNotFoundError


def make_service(agent=None):
    service = BotService(
        SimpleNamespace(
            runner_registry=SimpleNamespace(
                get=AsyncMock(
                    return_value=SimpleNamespace(
                        usages=['event'],
                        supported_event_patterns=['group.member_joined'],
                    )
                )
            )
        )
    )
    service._get_agent_entity = AsyncMock(return_value=agent)
    return service


async def test_prepare_accepts_configured_instance_and_preserves_input():
    service = make_service(SimpleNamespace(kind='event_processor', component_ref='plugin:test/runner/default'))
    payload = {'plugin_processors': [{'processor_uuid': 'processor', 'enabled': True, 'events': ['*']}]}
    result = await service._prepare_bot_data('workspace', payload, include_uuid=False)
    assert result == {'plugin_processors': [{'processor_uuid': 'processor', 'enabled': True}]}
    assert payload['plugin_processors'][0]['events'] == ['*']
    service._get_agent_entity.assert_awaited_once_with('workspace', 'processor')
    service.ap.runner_registry.get.assert_awaited_once_with('workspace', 'plugin:test/runner/default')


@pytest.mark.parametrize(
    'items,reason',
    [
        ({}, 'must be an array'),
        ([None], 'must be an object'),
        ([{}], 'UUID is required'),
        ([{'processor_uuid': 'p', 'enabled': 'false'}], 'must be a boolean'),
        ([{'processor_uuid': 'p'}, {'processor_uuid': 'p'}], 'only be bound once'),
    ],
)
async def test_invalid_bindings_are_rejected(items, reason):
    service = make_service(SimpleNamespace(kind='event_processor', component_ref='runner'))
    with pytest.raises(ValueError, match=reason):
        await service._normalize_plugin_processors('workspace', items)


@pytest.mark.parametrize('agent', [None, SimpleNamespace(kind='agent')])
async def test_missing_cross_workspace_or_wrong_kind_is_rejected(agent):
    service = make_service(agent)
    with pytest.raises(ValueError, match='not found'):
        await service._normalize_plugin_processors('workspace', [{'processor_uuid': 'p'}])


async def test_can_disable_binding_when_plugin_is_unavailable():
    service = make_service(SimpleNamespace(kind='event_processor', component_ref='missing'))
    service.ap.runner_registry.get.side_effect = ValueError('not installed')
    assert await service._normalize_plugin_processors('workspace', [{'processor_uuid': 'p', 'enabled': False}]) == [
        {'processor_uuid': 'p', 'enabled': False},
    ]
    service.ap.runner_registry.get.assert_not_called()


async def test_enabling_unavailable_runner_has_actionable_validation_error():
    service = make_service(SimpleNamespace(kind='event_processor', component_ref='missing'))
    service.ap.runner_registry.get.side_effect = RunnerNotFoundError('missing')
    with pytest.raises(ValueError, match='Runner component is unavailable'):
        await service._normalize_plugin_processors('workspace', [{'processor_uuid': 'p'}])
