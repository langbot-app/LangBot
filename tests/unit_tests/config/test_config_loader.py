"""Check equivalent user-facing load and persistence behavior across config formats."""

from __future__ import annotations

import json

import pytest
import yaml

from langbot.pkg.config.impls.json import JSONConfigFile
from langbot.pkg.config.impls.yaml import YAMLConfigFile
from langbot.pkg.config.manager import ConfigManager


@pytest.fixture(params=['yaml', 'json'])
def config_format(request, tmp_path):
    if request.param == 'json':
        return tmp_path / 'config.json', JSONConfigFile, json.dumps, json.loads, '{"unclosed":'
    return tmp_path / 'config.yaml', YAMLConfigFile, yaml.safe_dump, yaml.safe_load, 'unclosed: ['


async def test_load_preserves_user_values_and_only_completes_missing_keys_in_memory(config_format):
    path, config_type, encode, _, _ = config_format
    user_data = {'name': 'custom', 'enabled': False, 'limit': 0, 'settings': {'port': 8080}}
    original = encode(user_data)
    path.write_text(original, encoding='utf-8')
    config = config_type(
        str(path),
        template_data={
            'name': 'default',
            'enabled': True,
            'limit': 10,
            'settings': {'port': 5000},
            'fallback': 'added',
        },
    )

    assert config.exists()
    assert await config.load(completion=False) == user_data
    assert await config.load(completion=True) == {**user_data, 'fallback': 'added'}
    assert path.read_text(encoding='utf-8') == original


async def test_invalid_config_reports_the_source_and_leaves_it_unchanged(config_format):
    path, config_type, _, _, malformed = config_format
    path.write_text(malformed, encoding='utf-8')
    config = config_type(str(path), template_data={'name': 'default'})

    with pytest.raises(Exception, match='Syntax error') as raised:
        await config.load(completion=False)

    assert str(path) in str(raised.value)
    assert path.read_text(encoding='utf-8') == malformed


async def test_first_load_materializes_the_template_on_disk(config_format):
    path, config_type, _, decode, _ = config_format
    template = {'name': '默认配置', 'settings': {'debug': False}}
    config = config_type(str(path), template_data=template)

    assert not config.exists()
    assert await config.load() == template
    assert config.exists()
    assert decode(path.read_text(encoding='utf-8')) == template


@pytest.mark.parametrize('sync', [False, True], ids=['async', 'sync'])
async def test_manager_load_save_round_trip(config_format, sync):
    path, config_type, encode, decode, _ = config_format
    initial = {'name': 'managed', 'legacy': 'remove me'}
    path.write_text(encode(initial), encoding='utf-8')
    manager = ConfigManager(config_type(str(path), template_data={}))
    await manager.load_config()
    assert manager.data == initial

    replacement = {'name': '新配置', 'settings': {'enabled': False, 'port': 8080}}
    manager.data = replacement
    if sync:
        manager.dump_config_sync()
    else:
        await manager.dump_config()

    assert decode(path.read_text(encoding='utf-8')) == replacement
    fresh = ConfigManager(config_type(str(path), template_data={}))
    await fresh.load_config()
    assert fresh.data == replacement
