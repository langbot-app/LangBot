"""Build the workspace Runner example using plugin-level permission declarations."""

from pathlib import Path
import zipfile

import pytest
import yaml
from langbot_plugin.cli.commands import buildplugin
from langbot_plugin.api.entities.builtin.runner.manifest import RunnerPermissions
from langbot_plugin.api.entities.permissions import PluginPermissions


def test_example_runner_manifest_and_build(tmp_path, monkeypatch):
    plugin_dir = Path(__file__).resolve().parents[3] / 'sdk/examples/workspace_runner_plugin'
    if not plugin_dir.exists():
        pytest.skip('Build test requires the in-tree SDK (sdk/)')
    manifest = yaml.safe_load((plugin_dir / 'manifest.yaml').read_text())
    permissions = PluginPermissions.model_validate(manifest['spec']['permissions'])
    assert set(permissions.workspace_operations) == {'bot.list', 'stats.basic'}
    component = yaml.safe_load((plugin_dir / 'components/runner/default.yaml').read_text())
    RunnerPermissions.model_validate(component['spec']['permissions'])
    assert set(component['spec']['usages']) == {'agent', 'event'}
    assert 'workspace_operations' not in RunnerPermissions.model_fields
    monkeypatch.chdir(plugin_dir)
    monkeypatch.setattr(buildplugin, 'cli_print', lambda *args, **kwargs: None)
    package = buildplugin.build_plugin_process(str(tmp_path / 'dist'))
    assert package is not None and package.endswith('.lbpkg')
    with zipfile.ZipFile(package) as archive:
        packed = yaml.safe_load(archive.read('manifest.yaml'))
        assert packed['spec']['permissions'] == manifest['spec']['permissions']
        assert 'components/runner/default.py' in archive.namelist()
