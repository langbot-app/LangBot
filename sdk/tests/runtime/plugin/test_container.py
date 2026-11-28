from __future__ import annotations

from langbot_plugin.api.definition.components.base import NoneComponent
from langbot_plugin.api.definition.components.manifest import ComponentManifest
from langbot_plugin.api.definition.plugin import NonePlugin
from langbot_plugin.runtime.plugin.container import (
    ComponentContainer,
    PluginContainer,
    RuntimeContainerStatus,
)


def _manifest(kind: str = "Plugin", name: str = "demo") -> ComponentManifest:
    return ComponentManifest(
        owner="tester",
        manifest={
            "apiVersion": "v1",
            "kind": kind,
            "metadata": {
                "name": name,
                "label": {"en_US": name.title()},
                "author": "tester",
                "version": "1.0.0",
            },
            "spec": {"components": {}},
        },
        rel_path="manifest.yaml",
    )


def test_component_container_dump_excludes_runtime_instance():
    container = ComponentContainer(
        manifest=_manifest(kind="Tool", name="weather"),
        component_instance=NoneComponent(),
        component_config={"enabled": True},
    )

    dumped = container.model_dump()

    assert dumped["component_instance"] is None
    assert dumped["component_config"] == {"enabled": True}
    assert dumped["manifest"]["manifest"]["kind"] == "Tool"


def test_component_container_roundtrip_uses_none_component_placeholder():
    original = ComponentContainer(
        manifest=_manifest(kind="Command", name="hello"),
        component_instance=NoneComponent(),
        component_config={"prefix": "/"},
    )

    restored = ComponentContainer.from_dict(original.model_dump())

    assert isinstance(restored.component_instance, NoneComponent)
    assert restored.component_config == {"prefix": "/"}
    assert restored.manifest.kind == "Command"


def test_plugin_container_dump_excludes_plugin_instance_and_serializes_status():
    component = ComponentContainer(
        manifest=_manifest(kind="Tool", name="weather"),
        component_instance=NoneComponent(),
        component_config={},
    )
    container = PluginContainer(
        debug=True,
        install_source="local",
        install_info={"path": "."},
        manifest=_manifest(),
        plugin_instance=NonePlugin(),
        enabled=True,
        priority=10,
        plugin_config={"token": "x"},
        status=RuntimeContainerStatus.INITIALIZED,
        components=[component],
    )

    dumped = container.model_dump()

    assert dumped["plugin_instance"] is None
    assert dumped["status"] == "initialized"
    assert dumped["components"][0]["component_instance"] is None


def test_plugin_container_roundtrip_uses_none_plugin_placeholder():
    container = PluginContainer(
        debug=False,
        install_source="marketplace",
        install_info={"id": "tester/demo"},
        manifest=_manifest(),
        plugin_instance=NonePlugin(),
        enabled=False,
        priority=0,
        plugin_config={},
        status=RuntimeContainerStatus.MOUNTED,
        components=[],
    )

    restored = PluginContainer.from_dict(container.model_dump())

    assert isinstance(restored.plugin_instance, NonePlugin)
    assert restored.status is RuntimeContainerStatus.MOUNTED
    assert restored.enabled is False
    assert restored.components == []


def test_plugin_container_roundtrip_should_preserve_install_metadata():
    container = PluginContainer(
        debug=False,
        install_source="marketplace",
        install_info={"id": "tester/demo"},
        manifest=_manifest(),
        plugin_instance=NonePlugin(),
        enabled=True,
        priority=0,
        plugin_config={},
        status=RuntimeContainerStatus.MOUNTED,
        components=[],
    )

    restored = PluginContainer.from_dict(container.model_dump())

    assert restored.install_source == "marketplace"
    assert restored.install_info == {"id": "tester/demo"}
