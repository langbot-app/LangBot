"""
Unit tests for configuration loading and overrides.

Tests cover:
- Valid YAML config loading
- Valid JSON config loading
- Invalid YAML/JSON error behavior
- Missing config file behavior
- Template completion
"""

from __future__ import annotations

import pytest
import json

from langbot.pkg.config.impls.yaml import YAMLConfigFile
from langbot.pkg.config.impls.json import JSONConfigFile
from langbot.pkg.config.manager import ConfigManager


class TestYAMLConfigFile:
    """Tests for YAML config file handling."""

    @pytest.mark.asyncio
    async def test_valid_yaml_loads(self, tmp_path):
        """Valid YAML config should load correctly."""
        config_file = tmp_path / "test_config.yaml"

        # Write valid YAML
        config_file.write_text("""
name: test_app
version: 1.0
settings:
  debug: true
  port: 8080
""")

        yaml_file = YAMLConfigFile(
            str(config_file),
            template_data={'name': 'default', 'version': '0.1'},
        )

        result = await yaml_file.load(completion=False)

        assert result['name'] == 'test_app'
        assert result['version'] == 1.0
        assert result['settings']['debug'] is True
        assert result['settings']['port'] == 8080

    @pytest.mark.asyncio
    async def test_invalid_yaml_raises_error(self, tmp_path):
        """Invalid YAML should raise clear error."""
        config_file = tmp_path / "invalid.yaml"

        # Write invalid YAML (unclosed bracket)
        config_file.write_text("""
name: test
settings:
  - item1
  - item2
  - [unclosed
""")

        yaml_file = YAMLConfigFile(
            str(config_file),
            template_data={'name': 'default'},
        )

        with pytest.raises(Exception, match="Syntax error"):
            await yaml_file.load(completion=False)

    @pytest.mark.asyncio
    async def test_missing_config_creates_from_template(self, tmp_path):
        """Missing config file should be created from template."""
        config_file = tmp_path / "new_config.yaml"

        # File doesn't exist yet
        assert not config_file.exists()

        yaml_file = YAMLConfigFile(
            str(config_file),
            template_data={'name': 'new_app', 'version': '1.0'},
        )

        result = await yaml_file.load()

        assert config_file.exists()
        assert result['name'] == 'new_app'
        assert result['version'] == '1.0'

    @pytest.mark.asyncio
    async def test_template_completion(self, tmp_path):
        """Config should be completed with template defaults."""
        config_file = tmp_path / "partial.yaml"

        # Write partial config missing some template keys
        config_file.write_text("""
name: custom_name
""")

        yaml_file = YAMLConfigFile(
            str(config_file),
            template_data={'name': 'default_name', 'version': '2.0', 'debug': False},
        )

        result = await yaml_file.load(completion=True)

        # Existing key preserved
        assert result['name'] == 'custom_name'
        # Missing keys filled from template
        assert result['version'] == '2.0'
        assert result['debug'] is False

    @pytest.mark.asyncio
    async def test_yaml_save(self, tmp_path):
        """YAML config can be saved."""
        config_file = tmp_path / "save_test.yaml"

        yaml_file = YAMLConfigFile(
            str(config_file),
            template_data={'name': 'test'},
        )

        await yaml_file.save({'name': 'saved_app', 'new_key': 'new_value'})

        assert config_file.exists()
        content = config_file.read_text()
        assert 'saved_app' in content
        assert 'new_key' in content

    def test_yaml_save_sync(self, tmp_path):
        """YAML config can be saved synchronously."""
        config_file = tmp_path / "sync_save.yaml"

        yaml_file = YAMLConfigFile(
            str(config_file),
            template_data={'name': 'test'},
        )

        yaml_file.save_sync({'name': 'sync_saved'})

        assert config_file.exists()
        content = config_file.read_text()
        assert 'sync_saved' in content


class TestJSONConfigFile:
    """Tests for JSON config file handling."""

    @pytest.mark.asyncio
    async def test_valid_json_loads(self, tmp_path):
        """Valid JSON config should load correctly."""
        config_file = tmp_path / "test_config.json"

        # Write valid JSON
        config_file.write_text(json.dumps({
            'name': 'json_app',
            'version': '1.0',
            'settings': {'debug': True, 'port': 8080},
        }))

        json_file = JSONConfigFile(
            str(config_file),
            template_data={'name': 'default', 'version': '0.1'},
        )

        result = await json_file.load(completion=False)

        assert result['name'] == 'json_app'
        assert result['version'] == '1.0'
        assert result['settings']['debug'] is True

    @pytest.mark.asyncio
    async def test_invalid_json_raises_error(self, tmp_path):
        """Invalid JSON should raise clear error."""
        config_file = tmp_path / "invalid.json"

        # Write invalid JSON (missing closing brace)
        config_file.write_text('{"name": "test", "unclosed": ')

        json_file = JSONConfigFile(
            str(config_file),
            template_data={'name': 'default'},
        )

        with pytest.raises(Exception, match="Syntax error"):
            await json_file.load(completion=False)

    @pytest.mark.asyncio
    async def test_missing_json_creates_from_template(self, tmp_path):
        """Missing JSON file should be created from template."""
        config_file = tmp_path / "new_config.json"

        json_file = JSONConfigFile(
            str(config_file),
            template_data={'name': 'new_json_app', 'version': '1.0'},
        )

        result = await json_file.load()

        assert config_file.exists()
        assert result['name'] == 'new_json_app'

    @pytest.mark.asyncio
    async def test_json_save(self, tmp_path):
        """JSON config can be saved."""
        config_file = tmp_path / "save_test.json"

        json_file = JSONConfigFile(
            str(config_file),
            template_data={'name': 'test'},
        )

        await json_file.save({'name': 'saved_json', 'new_key': 'value'})

        assert config_file.exists()
        content = config_file.read_text()
        data = json.loads(content)
        assert data['name'] == 'saved_json'


class TestConfigManager:
    """Tests for ConfigManager."""

    @pytest.mark.asyncio
    async def test_config_manager_load(self, tmp_path):
        """ConfigManager loads config correctly."""
        config_file = tmp_path / "manager_test.yaml"
        config_file.write_text('name: managed_app\nversion: "1.0"\n')

        yaml_file = YAMLConfigFile(
            str(config_file),
            template_data={'name': 'default', 'version': '0.1'},
        )

        manager = ConfigManager(yaml_file)
        await manager.load_config()

        assert manager.data['name'] == 'managed_app'
        assert manager.data['version'] == '1.0'

    @pytest.mark.asyncio
    async def test_config_manager_dump(self, tmp_path):
        """ConfigManager can dump config."""
        config_file = tmp_path / "dump_test.yaml"

        yaml_file = YAMLConfigFile(
            str(config_file),
            template_data={'name': 'default'},
        )

        manager = ConfigManager(yaml_file)
        manager.data = {'name': 'dumped', 'new_field': 'value'}

        await manager.dump_config()

        content = config_file.read_text()
        assert 'dumped' in content

    def test_config_manager_dump_sync(self, tmp_path):
        """ConfigManager can dump config synchronously."""
        config_file = tmp_path / "sync_dump.yaml"

        yaml_file = YAMLConfigFile(
            str(config_file),
            template_data={'name': 'default'},
        )

        manager = ConfigManager(yaml_file)
        manager.data = {'name': 'sync_dumped'}

        manager.dump_config_sync()

        assert config_file.exists()


class TestConfigExists:
    """Tests for config file existence check."""

    def test_yaml_exists_true(self, tmp_path):
        """exists() returns True for existing file."""
        config_file = tmp_path / "exists.yaml"
        config_file.write_text('name: test')

        yaml_file = YAMLConfigFile(str(config_file), template_data={})
        assert yaml_file.exists() is True

    def test_yaml_exists_false(self, tmp_path):
        """exists() returns False for missing file."""
        config_file = tmp_path / "missing.yaml"

        yaml_file = YAMLConfigFile(str(config_file), template_data={})
        assert yaml_file.exists() is False

    def test_json_exists_true(self, tmp_path):
        """exists() returns True for existing JSON file."""
        config_file = tmp_path / "exists.json"
        config_file.write_text('{}')

        json_file = JSONConfigFile(str(config_file), template_data={})
        assert json_file.exists() is True

    def test_json_exists_false(self, tmp_path):
        """exists() returns False for missing JSON file."""
        config_file = tmp_path / "missing.json"

        json_file = JSONConfigFile(str(config_file), template_data={})
        assert json_file.exists() is False