"""Unit tests for bot command_settings validation in BotService."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.http.service.bot import BotService


def make_service(installed_plugins=None):
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(),
        platform_mgr=SimpleNamespace(),
    )
    if installed_plugins is not None:
        ap.plugin_connector = SimpleNamespace(
            list_plugins=AsyncMock(return_value=installed_plugins)
        )
    return BotService(ap)


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
        ({'plugins': 'not a list'}, 'must be a list'),
        ({'plugins': ['not a dict']}, 'must be an object'),
        ({'plugins': [{}]}, 'Plugin ID is required'),
        ({'plugins': [{'plugin_id': ''}]}, 'Plugin ID is required'),
        ({'plugins': [{'plugin_id': 'p1', 'enabled': 'yes'}]}, 'must be a boolean'),
        (
            {
                'plugins': [
                    {'plugin_id': 'p1', 'enabled': True},
                    {'plugin_id': 'p1', 'enabled': False},
                ]
            },
            'only be bound once',
        ),
    ],
)
@pytest.mark.asyncio
async def test_invalid_command_settings_are_rejected(settings, reason):
    service = make_service()
    with pytest.raises(ValueError, match=reason):
        await service._normalize_command_settings('ws-1', settings)


@pytest.mark.asyncio
async def test_uninstalled_plugin_is_rejected():
    """Plugin not installed in workspace must be rejected with ValueError."""
    service = make_service(
        installed_plugins=[
            {'plugin_id': 'author/installed_plugin'},
        ]
    )
    settings = {
        'enabled': True,
        'prefixes': ['/'],
        'plugins': [
            {'plugin_id': 'author/installed_plugin', 'enabled': True},
            {'plugin_id': 'other/not_installed', 'enabled': True},
        ],
    }
    with pytest.raises(ValueError, match="Plugin 'other/not_installed' is not installed in this workspace"):
        await service._normalize_command_settings('ws-1', settings)


@pytest.mark.asyncio
async def test_installed_plugin_validation_passes():
    """Installed plugin in workspace passes validation."""
    service = make_service(
        installed_plugins=[
            {
                'manifest': {
                    'manifest': {
                        'metadata': {'author': 'author', 'name': 'plugin1'},
                    }
                }
            },
        ]
    )
    settings = {
        'enabled': True,
        'prefixes': ['/'],
        'plugins': [
            {'plugin_id': 'author/plugin1', 'enabled': True},
        ],
    }
    normalized = await service._normalize_command_settings('ws-1', settings)
    assert normalized['plugins'] == [{'plugin_id': 'author/plugin1', 'enabled': True}]


@pytest.mark.asyncio
async def test_valid_command_settings_normalization():
    service = make_service()
    settings = {
        'enabled': True,
        'prefixes': ['/', '!', '/'],  # duplicate '/' should be deduplicated
        'plugins': [
            {'plugin_id': 'author/plugin1', 'enabled': True},
            {'plugin_id': 'author/plugin2', 'enabled': False},
        ],
    }
    normalized = await service._normalize_command_settings('ws-1', settings)
    assert normalized['enabled'] is True
    assert normalized['prefixes'] == ['/', '!']
    assert normalized['plugins'] == [
        {'plugin_id': 'author/plugin1', 'enabled': True},
        {'plugin_id': 'author/plugin2', 'enabled': False},
    ]


@pytest.mark.asyncio
async def test_prepare_bot_data_normalizes_command_settings():
    service = make_service()
    service._normalize_event_bindings = AsyncMock(return_value=[])
    service._normalize_plugin_processors = AsyncMock(return_value=[])

    bot_data = {
        'name': 'TestBot',
        'adapter': 'aiocqhttp',
        'command_settings': {
            'enabled': True,
            'prefixes': ['#'],
            'plugins': [{'plugin_id': 'my_plugin', 'enabled': True}],
        },
    }
    prepared = await service._prepare_bot_data('ws-1', bot_data, include_uuid=False)
    assert 'command_settings' in prepared
    assert prepared['command_settings']['prefixes'] == ['#']
    assert prepared['command_settings']['plugins'] == [
        {'plugin_id': 'my_plugin', 'enabled': True}
    ]
