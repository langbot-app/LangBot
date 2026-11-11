from __future__ import annotations

import yaml

from langbot_plugin.utils.discover.engine import ComponentDiscoveryEngine


def _write_manifest(path, *, kind="Tool", name="demo") -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "v1",
                "kind": kind,
                "metadata": {
                    "name": name,
                    "label": {"en_US": name.title()},
                },
                "spec": {},
            }
        ),
        encoding="utf-8",
    )


def test_load_component_manifest_returns_none_for_non_component_yaml(tmp_path):
    path = tmp_path / "plain.yaml"
    path.write_text("name: plain\n", encoding="utf-8")

    engine = ComponentDiscoveryEngine()

    assert engine.load_component_manifest(str(path)) is None


def test_load_component_manifest_can_skip_registry_save(tmp_path):
    path = tmp_path / "tool.yaml"
    _write_manifest(path)
    engine = ComponentDiscoveryEngine()

    component = engine.load_component_manifest(str(path), owner="plugin", no_save=True)

    assert component is not None
    assert component.owner == "plugin"
    assert component.metadata.name == "demo"
    assert engine.get_components_by_kind("Tool") == []


def test_load_component_manifests_in_dir_respects_depth_and_file_extension(tmp_path):
    _write_manifest(tmp_path / "root.yaml", kind="Command", name="root")
    nested = tmp_path / "nested"
    nested.mkdir()
    _write_manifest(nested / "nested.yml", kind="Tool", name="nested")
    too_deep = nested / "too_deep"
    too_deep.mkdir()
    _write_manifest(too_deep / "ignored.yaml", kind="Page", name="ignored")
    (tmp_path / "README.md").write_text("ignore me", encoding="utf-8")

    engine = ComponentDiscoveryEngine()
    components = engine.load_component_manifests_in_dir(str(tmp_path), max_depth=2)

    assert {component.metadata.name for component in components} == {"root", "nested"}
    assert [
        component.metadata.name
        for component in engine.get_components_by_kind("Command")
    ] == ["root"]
    assert [
        component.metadata.name for component in engine.get_components_by_kind("Tool")
    ] == ["nested"]


def test_discover_blueprint_loads_templates_before_other_component_groups(tmp_path):
    template = tmp_path / "template.yaml"
    tool = tmp_path / "tool.yaml"
    blueprint = tmp_path / "blueprint.yaml"
    _write_manifest(template, kind="ComponentTemplate", name="base")
    _write_manifest(tool, kind="Tool", name="weather")
    blueprint.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "v1",
                "kind": "Blueprint",
                "metadata": {"name": "bp", "label": {"en_US": "Blueprint"}},
                "spec": {
                    "components": {
                        "ComponentTemplate": {"fromFiles": [str(template)]},
                        "Tool": {"fromFiles": [str(tool)]},
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    engine = ComponentDiscoveryEngine()
    blueprint_manifest, components = engine.discover_blueprint(str(blueprint))

    assert blueprint_manifest.kind == "Blueprint"
    assert list(components) == ["ComponentTemplate", "Tool"]
    assert components["ComponentTemplate"][0].metadata.name == "base"
    assert components["Tool"][0].metadata.name == "weather"


def test_find_components_filters_supplied_component_list(tmp_path):
    tool = tmp_path / "tool.yaml"
    command = tmp_path / "command.yaml"
    _write_manifest(tool, kind="Tool", name="weather")
    _write_manifest(command, kind="Command", name="weather_cmd")
    engine = ComponentDiscoveryEngine()
    components = engine.load_component_manifests_in_dir(str(tmp_path))

    assert [c.kind for c in engine.find_components("Tool", components)] == ["Tool"]


def test_component_registry_should_be_isolated_per_engine_instance(tmp_path):
    path = tmp_path / "tool.yaml"
    _write_manifest(path)

    first = ComponentDiscoveryEngine()
    second = ComponentDiscoveryEngine()
    first.load_component_manifest(str(path), no_save=False)

    assert second.get_components_by_kind("Tool") == []
