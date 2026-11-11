"""Runner usage declarations are mandatory in packaged and debug components."""

from pathlib import Path

import pytest
import yaml

from langbot_plugin.api.definition.components.manifest import (
    ComponentManifest,
    InvalidRunnerManifest,
)
from langbot_plugin.cli.commands.buildplugin import build_plugin_process
from langbot_plugin.utils.discover.engine import ComponentDiscoveryEngine


@pytest.mark.parametrize(
    "spec",
    [
        {},
        {"usages": None},
        {"usages": []},
        {"usages": "agent"},
        {"usages": ["unknown"]},
        {"usages": ["event"]},
    ],
)
@pytest.mark.parametrize("lookup", ["fromFiles", "fromDirs"])
def test_build_rejects_invalid_runner_usage(tmp_path, monkeypatch, spec, lookup):
    monkeypatch.chdir(tmp_path)
    component = {
        "apiVersion": "langbot/v1",
        "kind": "Runner",
        "metadata": {"name": "demo", "label": {"en_US": "Demo"}},
        "spec": spec,
    }
    Path("components").mkdir()
    Path("components/demo.yaml").write_text(yaml.safe_dump(component))
    group = {
        lookup: ["components/demo.yaml"]
        if lookup == "fromFiles"
        else [{"path": "components"}]
    }
    plugin = {
        "apiVersion": "langbot/v1",
        "kind": "Plugin",
        "metadata": {
            "name": "demo",
            "author": "tester",
            "version": "0.1.0",
            "label": {"en_US": "Demo"},
        },
        "spec": {"components": {"Runner": group}},
    }
    Path("manifest.yaml").write_text(yaml.safe_dump(plugin))
    with pytest.raises(InvalidRunnerManifest, match="components/demo.yaml"):
        build_plugin_process(str(tmp_path / "dist"))
    assert not list((tmp_path / "dist").glob("*.lbpkg"))
    with pytest.raises(InvalidRunnerManifest):
        ComponentDiscoveryEngine().load_component_manifest("components/demo.yaml")


@pytest.mark.parametrize("usages", [["agent"], ["event"], ["agent", "event"]])
def test_runner_accepts_explicit_usages(usages):
    manifest = ComponentManifest(
        owner="tester",
        rel_path="runner.yaml",
        manifest={
            "kind": "Runner",
            "metadata": {"name": "demo", "label": {"en_US": "Demo"}},
            "spec": {"usages": usages, "events": ["*"]},
        },
    )
    assert manifest.spec["usages"] == usages
