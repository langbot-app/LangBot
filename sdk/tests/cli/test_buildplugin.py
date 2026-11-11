from __future__ import annotations

import os
import zipfile

import yaml

from langbot_plugin.cli.commands import buildplugin


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
    (plugin_dir / "main.py").write_text("print('hello')\n", encoding="utf-8")
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
        assert ".env" not in names
        assert "ignored.txt" not in names
        assert "cache/data.txt" not in names


def test_build_plugin_process_returns_none_when_manifest_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(buildplugin, "cli_print", lambda *args, **kwargs: None)

    assert buildplugin.build_plugin_process(str(tmp_path / "dist")) is None
