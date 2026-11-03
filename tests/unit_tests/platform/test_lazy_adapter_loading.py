"""Adapter metadata stays available without importing unused platform SDKs."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.entity.errors.platform import AdapterNotFoundError
from langbot.pkg.platform.botmgr import PlatformManager


def component(name, loader):
    return SimpleNamespace(
        metadata=SimpleNamespace(name=name),
        get_python_component_class=loader,
        to_plain_dict=lambda: {'name': name},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('disabled', [False, True])
async def test_initialize_lists_unused_adapters_without_importing_them(disabled):
    loader = Mock(side_effect=ModuleNotFoundError('SDK is not installed'))
    app = SimpleNamespace(
        storage_mgr=SimpleNamespace(storage_provider=SimpleNamespace(delete_dir_recursive=AsyncMock())),
        instance_config=SimpleNamespace(data={'system': {'disabled_adapters': ['lark-eba'] if disabled else []}}),
        discover=SimpleNamespace(get_components_by_kind=lambda _: [component('lark-omni', loader)]),
        workspace_service=SimpleNamespace(get_execution_binding=AsyncMock(side_effect=ValueError('no workspace'))),
    )
    manager = PlatformManager(app)
    manager.load_bots_from_db = AsyncMock()
    await manager.initialize()
    if disabled:
        assert manager.get_available_adapters_info() == []
        with pytest.raises(AdapterNotFoundError):
            manager._get_adapter_class('lark-eba')
    else:
        assert manager.get_available_adapters_info() == [{'name': 'lark-omni'}]
        assert manager.get_available_adapter_info_by_name('lark-eba') == {'name': 'lark-omni'}
    assert manager.adapter_dict == {}
    loader.assert_not_called()


@pytest.mark.parametrize('name', ['missing', 'lark-eba'])
def test_missing_or_disabled_adapter_cannot_be_loaded(name):
    manager = PlatformManager(SimpleNamespace())
    with pytest.raises(AdapterNotFoundError):
        manager._get_adapter_class(name)
    assert manager.adapter_dict == {}


def test_first_use_normalizes_alias_and_caches_only_successful_import():
    adapter = type('Adapter', (), {})
    loader = Mock(side_effect=[ModuleNotFoundError('missing SDK'), adapter])
    manager = PlatformManager(SimpleNamespace())
    manager.adapter_components = [component('lark-omni', loader)]
    with pytest.raises(ModuleNotFoundError, match='missing SDK'):
        manager._get_adapter_class('lark-eba')
    assert manager.adapter_dict == {}
    assert manager._get_adapter_class('lark-eba') is adapter
    assert manager._get_adapter_class('lark-omni') is adapter
    assert loader.call_count == 2
