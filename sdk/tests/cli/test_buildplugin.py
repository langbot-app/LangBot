from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import zipfile

import yaml
import pytest

from langbot_plugin.cli.commands import buildplugin
from langbot_plugin.utils.version_compat import check, parse_range


@pytest.mark.parametrize(
    ("bounds", "field", "value"),
    [
        ("{min: 4.10}", "min", "4.1"),
        ('{max: "4.x.5"}', "max", "4.x.5"),
        ('{min: "5", max: "4"}', "min", "'5' exceeds max '4'"),
    ],
)
def test_build_cli_invalid_range(tmp_path, bounds, field, value):
    manifest = f"apiVersion: v1\nkind: Plugin\nmetadata:\n  name: demo\n  label: {{en_US: Demo}}\n  compatibility:\n    langbot: {bounds}\nspec: {{components: {{}}}}\n"
    (tmp_path / "manifest.yaml").write_text(manifest)
    run = subprocess.run(
        [sys.executable, "-c", "from langbot_plugin.cli import main; main()", "build"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 1
    assert len(run.stderr.strip().splitlines()) == 1
    assert "Traceback" not in run.stderr
    assert f"metadata.compatibility.langbot.{field}:" in run.stderr
    assert value in run.stderr
    if bounds == "{min: 4.10}":
        assert "请用引号包住版本号" in run.stderr


@pytest.mark.parametrize("compat", [None, {"langbot": None}])
def test_build_null_compatibility_is_unspecified(tmp_path, monkeypatch, compat):
    metadata = {"name": "demo", "label": {"en_US": "Demo"}, "compatibility": compat}
    manifest = {
        "apiVersion": "v1",
        "kind": "Plugin",
        "metadata": metadata,
        "spec": {"components": {}},
    }
    (tmp_path / "manifest.yaml").write_text(yaml.safe_dump(manifest))
    monkeypatch.chdir(tmp_path)
    assert Path(buildplugin.build_plugin_process("dist")).is_file()
    assert parse_range(None) == (None, None)
    assert check(manifest, "4.12.0") == dict(
        status="unspecified", min=None, max=None, current="4.12.0"
    )


def test_parse_gitignore_ignores_comments_and_blank_lines(tmp_path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(
        "\n# cache\n.env\nbuild/\n*.pyc\n",
        encoding="utf-8",
    )

    assert buildplugin.parse_gitignore(str(gitignore)) == [".env", "build/", "*.pyc"]


def test_should_ignore_supports_directory_root_wildcard_and_exact_patterns():
    patterns = ["build/", "/dist", "*.pyc", "secret.txt"]

    assert buildplugin.should_ignore("build/output.txt", patterns) is True
    assert buildplugin.should_ignore("dist/plugin.zip", patterns) is True
    assert buildplugin.should_ignore("pkg/module.pyc", patterns) is True
    assert buildplugin.should_ignore("nested/secret.txt", patterns) is True
    assert buildplugin.should_ignore("src/main.py", patterns) is False


def test_build_plugin_process_packages_manifest_and_filters_ignored_files(
    tmp_path, monkeypatch
):
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    output_dir = tmp_path / "dist"
    (plugin_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "apiVersion": "v1",
                "kind": "Plugin",
                "metadata": {
                    "name": "demo",
                    "label": {"en_US": "Demo"},
                    "author": "tester",
                    "version": "0.1.0",
                },
                "spec": {"components": {}},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (plugin_dir / "main.py").write_bytes(b"print('hello')\n")
    (plugin_dir / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (plugin_dir / ".gitignore").write_text("ignored.txt\ncache/\n", encoding="utf-8")
    (plugin_dir / "ignored.txt").write_text("ignore", encoding="utf-8")
    cache_dir = plugin_dir / "cache"
    cache_dir.mkdir()
    (cache_dir / "data.txt").write_text("ignore", encoding="utf-8")
    monkeypatch.chdir(plugin_dir)
    monkeypatch.setattr(buildplugin, "cli_print", lambda *args, **kwargs: None)

    package_path = buildplugin.build_plugin_process(str(output_dir))

    assert package_path == os.path.join(str(output_dir), "tester-demo-0.1.0.lbpkg")
    with zipfile.ZipFile(package_path) as package:
        names = set(package.namelist())
        assert {"manifest.yaml", "main.py", ".gitignore"} <= names
        archived_manifest = yaml.safe_load(package.read("manifest.yaml"))
        source_manifest = yaml.safe_load((plugin_dir / "manifest.yaml").read_bytes())
        assert archived_manifest["metadata"] == source_manifest["metadata"]
        assert (
            archived_manifest["spec"]["components"]
            == source_manifest["spec"]["components"]
        )
        assert package.read("main.py") == b"print('hello')\n"
        assert ".env" not in names
        assert "ignored.txt" not in names
        assert "cache/data.txt" not in names


def test_build_plugin_process_returns_none_when_manifest_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(buildplugin, "cli_print", lambda *args, **kwargs: None)

    output_dir = tmp_path / "dist"
    assert buildplugin.build_plugin_process(str(output_dir)) is None
    assert not list(output_dir.glob("*.lbpkg"))
