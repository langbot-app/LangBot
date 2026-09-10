"""Saved adapter IDs remain usable while public metadata exposes Omni IDs."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import yaml

from langbot.pkg.api.http.service.bot import BotService
from langbot.pkg.platform.adapter_names import OMNI_ADAPTER_NAMES, canonical_adapter_name
from langbot.pkg.platform.botmgr import PlatformManager


@pytest.mark.asyncio
@pytest.mark.parametrize('name', sorted(OMNI_ADAPTER_NAMES))
async def test_saved_adapter_ids_are_normalized_across_bot_api(name):
    saved = {'uuid': 'bot', 'adapter': f'{name}-eba', 'adapter_config': {}}
    component = SimpleNamespace(
        metadata=SimpleNamespace(name=f'{name}-omni'),
        spec={'config': [{'type': 'webhook-url'}]},
        to_plain_dict=lambda: {'metadata': {'name': f'{name}-omni'}},
    )
    result = SimpleNamespace(all=lambda: [saved], first=lambda: saved)
    application = SimpleNamespace(
        discover=SimpleNamespace(get_components_by_kind=lambda _: [component]),
        persistence_mgr=SimpleNamespace(
            execute_async=AsyncMock(return_value=result),
            serialize_model=Mock(side_effect=lambda _model, row, _masked: row.copy()),
        ),
    )
    service = BotService(application)
    assert (await service.get_bots('workspace'))[0]['adapter'] == f'{name}-omni'
    assert (await service.get_bot('workspace', 'bot'))['adapter'] == f'{name}-omni'
    assert service._adapter_declares_webhook_url(saved['adapter'])
    assert (await service._prepare_bot_data('workspace', saved, include_uuid=True))['adapter'] == f'{name}-omni'
    assert saved['adapter'] == f'{name}-eba'
    manager = PlatformManager(application)
    manager.adapter_components = [component]
    assert manager.get_available_adapter_manifest_by_name(saved['adapter']) is component
    assert manager.get_available_adapter_info_by_name(saved['adapter'])['metadata']['name'] == f'{name}-omni'


@pytest.mark.parametrize('name', ['telegram', 'custom-eba', 'my-telegram-eba', 'telegram-omni', 'websocket'])
def test_legacy_and_custom_adapter_ids_are_unchanged(name):
    assert canonical_adapter_name(name) == name


def test_discovered_manifests_expose_only_omni_names():
    root = Path(__file__).resolve().parents[3] / 'src/langbot/pkg/platform/adapters'
    for name in OMNI_ADAPTER_NAMES:
        metadata = yaml.safe_load((root / name / 'manifest.yaml').read_text())['metadata']
        assert metadata['name'] == f'{name}-omni'


@pytest.mark.asyncio
@pytest.mark.parametrize('disabled_name', ['telegram-eba', 'telegram-omni'])
async def test_old_disabled_adapter_config_still_hides_omni(disabled_name):
    component = SimpleNamespace(metadata=SimpleNamespace(name='telegram-omni'))
    application = SimpleNamespace(
        storage_mgr=SimpleNamespace(storage_provider=SimpleNamespace(delete_dir_recursive=AsyncMock())),
        instance_config=SimpleNamespace(data={'system': {'disabled_adapters': [disabled_name]}}),
        discover=SimpleNamespace(get_components_by_kind=lambda _: [component]),
        workspace_service=SimpleNamespace(get_execution_binding=AsyncMock(side_effect=ValueError('no workspace'))),
    )
    manager = PlatformManager(application)
    manager.load_bots_from_db = AsyncMock()
    await manager.initialize()
    assert manager.adapter_dict == {}
    assert manager.adapter_components == []
