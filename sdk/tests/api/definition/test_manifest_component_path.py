"""Component module resolution must stay inside the plugin directory.

``execution.python.path`` is plugin-authored manifest data, so it is untrusted.
These tests pin the resolver to the plugin directory and check that importing a
component no longer leaves the plugin directory on ``sys.path``.
"""

import sys
import textwrap

import pytest

from langbot_plugin.api.definition.components.manifest import ComponentManifest


@pytest.fixture(autouse=True)
def _clean_component_modules(tmp_path, monkeypatch):
    """Drop cached component modules so each test resolves its own plugin dir."""
    monkeypatch.chdir(tmp_path)
    before = {
        name
        for name in sys.modules
        if name == "components" or name.startswith("components.")
    }
    for name in before:
        sys.modules.pop(name, None)
    yield
    for name in [
        n for n in sys.modules if n == "components" or n.startswith("components.")
    ]:
        sys.modules.pop(name, None)


def _manifest(rel_path: str, python_path: str, attr: str = "Component"):
    return ComponentManifest(
        owner="plugin",
        manifest={
            "apiVersion": "v1",
            "kind": "Command",
            "metadata": {
                "name": "probe",
                "label": {"en_US": "probe"},
                "description": {"en_US": "probe"},
            },
            "spec": {},
            "execution": {"python": {"path": python_path, "attr": attr}},
        },
        rel_path=rel_path,
    )


def _plugin(tmp_path, files: dict[str, str]):
    for name, content in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(content))
    return tmp_path


@pytest.mark.parametrize(
    "declared",
    [
        "../outside.py",
        "../../etc/evil.py",
        "components/../../outside.py",
        "/etc/passwd.py",
        "C:/windows/evil.py",
        "c:evil.py",
        "",
    ],
)
def test_paths_outside_the_plugin_are_rejected(tmp_path, declared):
    plugin = _plugin(tmp_path, {"manifest.yaml": ""})
    manifest = _manifest(str(plugin / "manifest.yaml"), declared)
    with pytest.raises(ValueError):
        manifest.get_python_component_class()


def test_component_inside_the_plugin_is_imported(tmp_path, monkeypatch):
    plugin = _plugin(
        tmp_path,
        {
            "components/__init__.py": "",
            "components/inside_once.py": """
                class Component:
                    marker = "INSIDE"
            """,
        },
    )
    manifest = _manifest(str(plugin / "manifest.yaml"), "components/inside_once.py")

    component = manifest.get_python_component_class()

    assert component.marker == "INSIDE"


def test_import_does_not_leave_the_plugin_dir_on_sys_path(tmp_path, monkeypatch):
    """A leaked path would let one plugin shadow modules for later plugins."""
    plugin = _plugin(
        tmp_path,
        {
            "components/__init__.py": "",
            "components/leak_check.py": """
                class Component:
                    marker = "INSIDE"
            """,
        },
    )
    manifest = _manifest(str(plugin / "manifest.yaml"), "components/leak_check.py")
    before = list(sys.path)

    manifest.get_python_component_class()

    assert str(plugin) not in sys.path
    assert len(sys.path) == len(before)


def test_relative_path_without_py_suffix_works(tmp_path, monkeypatch):
    plugin = _plugin(
        tmp_path,
        {
            "components/__init__.py": "",
            "components/no_suffix_mod.py": """
                class Component:
                    marker = "NO_SUFFIX"
            """,
        },
    )
    manifest = _manifest(str(plugin / "manifest.yaml"), "components/no_suffix_mod")

    assert manifest.get_python_component_class().marker == "NO_SUFFIX"


def test_importing_a_missing_component_leaves_sys_path_clean(tmp_path, monkeypatch):
    plugin = _plugin(tmp_path, {"manifest.yaml": ""})
    manifest = _manifest(str(plugin / "manifest.yaml"), "components/missing.py")
    before = list(sys.path)

    with pytest.raises(ModuleNotFoundError):
        manifest.get_python_component_class()

    assert str(plugin) not in sys.path
    assert len(sys.path) == len(before)


@pytest.mark.parametrize("packages", [True, False])
def test_nested_component_preserves_package_and_relative_imports(tmp_path, packages):
    files = {
        "components/knowledge_engine/parser.py": 'VALUE = "parsed"',
        "components/knowledge_engine/engine.py": """
            from .parser import VALUE

            class Component:
                marker = VALUE

                def lazy_import(self):
                    from .parser import VALUE
                    return VALUE
        """,
    }
    if packages:
        files.update(
            {
                "components/__init__.py": "",
                "components/knowledge_engine/__init__.py": "",
            }
        )
    _plugin(tmp_path, files)
    manifest = _manifest("components/knowledge_engine/engine.yaml", "engine.py")
    before = list(sys.path)

    component = manifest.get_python_component_class()

    assert component.__module__ == "components.knowledge_engine.engine"
    assert component.marker == "parsed"
    assert component().lazy_import() == "parsed"
    assert sys.path == before


def test_manifest_outside_plugin_root_is_rejected(tmp_path):
    manifest = _manifest(str(tmp_path.parent / "outside.yaml"), "outside.py")
    with pytest.raises(ValueError, match="escapes the plugin directory"):
        manifest.get_python_component_class()
