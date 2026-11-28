from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from langbot_plugin.cli.commands import buildplugin
from langbot_plugin.cli.utils.page_components import discover_plugin_components
from langbot_plugin.utils.packaging import load_plugin_manifest

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
EXAMPLE_DIRS = sorted(
    [
        p
        for p in EXAMPLES_DIR.iterdir()
        if p.is_dir() and (p / "manifest.yaml").is_file()
    ],
    key=lambda p: p.name,
)


def test_examples_directory_contains_plugins():
    assert EXAMPLES_DIR.is_dir(), f"examples directory not found at {EXAMPLES_DIR}"
    assert len(EXAMPLE_DIRS) >= 1, f"No example plugins found in {EXAMPLES_DIR}"


@pytest.mark.parametrize("example_dir", EXAMPLE_DIRS, ids=lambda p: p.name)
def test_example_plugin_manifest_discovery(
    example_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(example_dir)
    discovery_engine, plugin_manifest = load_plugin_manifest(str(example_dir))
    components = discover_plugin_components(plugin_manifest, discovery_engine)
    assert len(components) >= 1


@pytest.mark.parametrize("example_dir", EXAMPLE_DIRS, ids=lambda p: p.name)
def test_example_plugin_build(
    example_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(example_dir)
    monkeypatch.setattr(buildplugin, "cli_print", lambda *args, **kwargs: None)

    dist_dir = tmp_path / "dist"
    package_path = buildplugin.build_plugin_process(str(dist_dir))

    assert package_path is not None
    assert package_path.endswith(".lbpkg")
    assert Path(package_path).is_file()

    with zipfile.ZipFile(package_path) as package:
        names = set(package.namelist())
        assert "manifest.yaml" in names
        assert "main.py" in names
