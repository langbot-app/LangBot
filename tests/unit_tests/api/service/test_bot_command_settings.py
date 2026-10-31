"""Unit tests for bot command_settings validation in BotService."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.http.service.bot import BotService


def make_service(processors=None):
    """``processors`` maps processor UUID to (kind, component_ref)."""
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(),
        platform_mgr=SimpleNamespace(),
    )
    service = BotService(ap)
    known = processors or {}

    async def get_agent_entity(_context, processor_uuid):
        if processor_uuid not in known:
            return None
        kind, component_ref = known[processor_uuid]
        return SimpleNamespace(uuid=processor_uuid, kind=kind, component_ref=component_ref)

    service._get_agent_entity = AsyncMock(side_effect=get_agent_entity)
    return service


PROCESSORS = {
    'cp-1': ('command_processor', 'plugin:author/plugin1'),
    'cp-2': ('command_processor', 'plugin:author/plugin2'),
    'cp-1b': ('command_processor', 'plugin:author/plugin1'),
    'ep-1': ('event_processor', 'plugin:author/plugin1/default'),
}


@pytest.mark.parametrize(
    'settings,reason',
    [
        ('not a dict', 'must be an object'),
        ({'enabled': 'not a bool'}, 'must be a boolean'),
        ({'prefixes': []}, 'must be a non-empty list'),
        ({'prefixes': 'not a list'}, 'must be a non-empty list'),
        ({'prefixes': ['']}, 'must be a non-empty string without whitespace'),
        ({'prefixes': ['/   ']}, 'must be a non-empty string without whitespace'),
        ({'prefixes': ['/ a']}, 'must be a non-empty string without whitespace'),
        ({'processors': 'not a list'}, 'must be a list'),
        ({'processors': ['not a dict']}, 'must be an object'),
        ({'processors': [{}]}, 'Command processor UUID is required'),
        ({'processors': [{'processor_uuid': ''}]}, 'Command processor UUID is required'),
        ({'processors': [{'processor_uuid': 'cp-1', 'enabled': 'yes'}]}, 'must be a boolean'),
        ({'processors': [{'processor_uuid': 'missing'}]}, 'Command processor not found'),
        ({'processors': [{'processor_uuid': 'ep-1'}]}, 'Command processor not found'),
        (
            {'processors': [{'processor_uuid': 'cp-1'}, {'processor_uuid': 'cp-1', 'enabled': False}]},
            'only be bound once',
        ),
        (
            {'processors': [{'processor_uuid': 'cp-1'}, {'processor_uuid': 'cp-1b'}]},
            'one command processor per plugin',
        ),
    ],
)
@pytest.mark.asyncio
async def test_invalid_command_settings_are_rejected(settings, reason):
    service = make_service(PROCESSORS)
    with pytest.raises(ValueError, match=reason):
        await service._normalize_command_settings('ws-1', settings)


@pytest.mark.asyncio
async def test_valid_command_settings_normalization():
    service = make_service(PROCESSORS)
    settings = {
        'enabled': True,
        'prefixes': ['/', '!', '/'],  # duplicate '/' should be deduplicated
        'processors': [
            {'processor_uuid': 'cp-2', 'enabled': True},
            {'processor_uuid': 'cp-1', 'enabled': False},
        ],
    }
    normalized = await service._normalize_command_settings('ws-1', settings)
    assert normalized['enabled'] is True
    assert normalized['prefixes'] == ['/', '!']
    # Order is priority and must be preserved.
    assert normalized['processors'] == [
        {'processor_uuid': 'cp-2', 'enabled': True},
        {'processor_uuid': 'cp-1', 'enabled': False},
    ]


@pytest.mark.asyncio
async def test_prepare_bot_data_normalizes_command_settings():
    service = make_service(PROCESSORS)
    service._normalize_event_bindings = AsyncMock(return_value=[])
    service._normalize_plugin_processors = AsyncMock(return_value=[])

    bot_data = {
        'name': 'TestBot',
        'adapter': 'aiocqhttp',
        'command_settings': {
            'enabled': True,
            'prefixes': ['#'],
            'processors': [{'processor_uuid': 'cp-1', 'enabled': True}],
        },
    }
    prepared = await service._prepare_bot_data('ws-1', bot_data, include_uuid=False)
    assert prepared['command_settings']['prefixes'] == ['#']
    assert prepared['command_settings']['processors'] == [{'processor_uuid': 'cp-1', 'enabled': True}]
