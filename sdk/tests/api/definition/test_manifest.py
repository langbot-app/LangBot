from __future__ import annotations

import os
import sys
import textwrap

import pytest

from langbot_plugin.api.definition.components.manifest import (
    ComponentManifest,
    Execution,
    I18nString,
    Metadata,
    PythonExecution,
)


def _manifest(kind: str = "Tool") -> dict:
    return {
        "apiVersion": "v1",
        "kind": kind,
        "metadata": {
            "name": "weather",
            "label": {"en_US": "Weather", "zh_Hans": "天气"},
            "author": "tester",
            "version": "1.0.0",
        },
        "spec": {"description": "lookup weather"},
        "execution": {"python": {"path": "./weather.py", "attr": "WeatherTool"}},
    }


def test_i18n_string_to_dict_omits_missing_locales():
    text = I18nString(en_US="Hello", zh_Hans="你好")
    assert text.to_dict() == {"en_US": "Hello", "zh_Hans": "你好"}


def test_metadata_fills_optional_description_and_icon_defaults():
    metadata = Metadata(name="demo", label={"en_US": "Demo"})
    assert metadata.description is not None
    assert metadata.description.to_dict() == {"en_US": ""}
    assert metadata.icon == ""


def test_python_execution_strips_current_directory_prefix():
    execution = PythonExecution(path="./components/weather.py", attr="Weather")
    assert execution.path == "components/weather.py"


def test_execution_accepts_only_the_certified_shared_runtime_profile():
    shared = Execution(
        python={"path": "main.py", "attr": "Plugin"},
        sharedRuntime="shared-runtime-v1",
        componentModel="stateless-v1",
    )
    dedicated = Execution(python={"path": "main.py", "attr": "Plugin"})

    assert shared.shared_runtime == "shared-runtime-v1"
    assert shared.component_model == "stateless-v1"
    assert dedicated.shared_runtime is None
    with pytest.raises(ValueError):
        Execution(
            python={"path": "main.py", "attr": "Plugin"},
            sharedRuntime="other-profile",
        )
    with pytest.raises(ValueError):
        Execution(
            python={"path": "main.py", "attr": "Plugin"},
            sharedRuntime=None,
        )
    legacy_shared = Execution(
        python={"path": "main.py", "attr": "Plugin"},
        sharedRuntime="shared-runtime-v1",
    )
    assert legacy_shared.component_model is None


def test_component_manifest_properties_and_plain_dict():
    component = ComponentManifest(
        owner="plugin",
        manifest=_manifest(),
        rel_path="components/weather.yaml",
    )

    assert component.kind == "Tool"
    assert component.metadata.name == "weather"
    assert component.spec == {"description": "lookup weather"}
    assert component.icon_rel_path is None
    assert component.to_plain_dict() == {
        "name": "weather",
        "label": {"en_US": "Weather", "zh_Hans": "天气"},
        "description": {"en_US": ""},
        "icon": "",
        "spec": {"description": "lookup weather"},
    }


def test_component_manifest_icon_path_is_relative_to_manifest_directory():
    manifest = _manifest()
    manifest["metadata"]["icon"] = "assets/icon.svg"
    component = ComponentManifest(
        owner="plugin",
        manifest=manifest,
        rel_path="components/weather.yaml",
    )

    assert component.icon_rel_path == os.path.join("components", "assets/icon.svg")


def test_component_manifest_detection_requires_core_fields():
    assert ComponentManifest.is_component_manifest(_manifest()) is True
    assert ComponentManifest.is_component_manifest({"kind": "Tool"}) is False


def test_component_manifest_imports_python_component_class(tmp_path, monkeypatch):
    component_dir = tmp_path / "components"
    component_dir.mkdir()
    (component_dir / "__init__.py").write_text("", encoding="utf-8")
    (component_dir / "weather.py").write_text(
        textwrap.dedent(
            """
            class WeatherTool:
                pass
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    component = ComponentManifest(
        owner="plugin",
        manifest=_manifest(),
        rel_path="components/weather.yaml",
    )
    try:
        component_cls = component.get_python_component_class()
        assert component_cls.__name__ == "WeatherTool"
    finally:
        while str(tmp_path) in sys.path:
            sys.path.remove(str(tmp_path))


def test_component_manifest_without_execution_cannot_resolve_class():
    manifest = _manifest()
    del manifest["execution"]
    component = ComponentManifest(
        owner="plugin",
        manifest=manifest,
        rel_path="components/weather.yaml",
    )

    with pytest.raises(ValueError, match="Execution is not set"):
        component.get_python_component_class()
