from __future__ import annotations

import ntpath
import subprocess

import yaml

from langbot_plugin.cli.commands import initplugin


def test_get_lbp_path_uses_platform_specific_script_location(monkeypatch):
    monkeypatch.setattr(initplugin.sys, "executable", "/opt/python/bin/python")
    monkeypatch.setattr(initplugin.platform, "system", lambda: "Linux")
    assert initplugin.get_lbp_path() == "/opt/python/bin/lbp"

    monkeypatch.setattr(initplugin.sys, "executable", r"C:\Python\python.exe")
    monkeypatch.setattr(initplugin.platform, "system", lambda: "Windows")
    assert initplugin.get_lbp_path() == ntpath.join(r"C:\Python", "Scripts", "lbp.exe")

    monkeypatch.setattr(
        initplugin.sys,
        "executable",
        r"C:\workspace\.venv\Scripts\python.exe",
    )
    assert initplugin.get_lbp_path() == ntpath.join(
        r"C:\workspace\.venv\Scripts", "lbp.exe"
    )


def test_is_git_available_returns_false_when_git_missing(monkeypatch):
    def raise_missing(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(initplugin.subprocess, "run", raise_missing)

    assert initplugin.is_git_available() is False


def test_init_git_repo_invokes_git_init(monkeypatch):
    calls = []
    prints = []
    monkeypatch.setattr(
        initplugin.subprocess,
        "run",
        lambda cmd, **kwargs: calls.append((cmd, kwargs)),
    )
    monkeypatch.setattr(initplugin, "cli_print", lambda *args: prints.append(args))

    initplugin.init_git_repo("plugin")

    assert calls[0][0] == ["git", "init"]
    assert calls[0][1]["cwd"] == "plugin"
    assert prints == [("git_repo_initialized", "plugin")]


def test_init_git_repo_reports_git_warning(monkeypatch):
    error = subprocess.CalledProcessError(1, ["git"], stderr=b"boom")
    prints = []
    monkeypatch.setattr(
        initplugin.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(error),
    )
    monkeypatch.setattr(initplugin, "cli_print", lambda *args: prints.append(args))

    initplugin.init_git_repo("plugin")

    assert prints == [("git_init_warning", b"boom")]


def test_init_plugin_process_generates_plugin_scaffold(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        initplugin,
        "input_form_values",
        lambda fields: {
            "plugin_author": "tester",
            "plugin_description": "Demo plugin",
        },
    )
    monkeypatch.setattr(initplugin, "is_git_available", lambda: False)
    monkeypatch.setattr(initplugin, "cli_print", lambda *args: None)
    monkeypatch.setattr(initplugin, "get_lbp_path", lambda: "/usr/bin/lbp")

    initplugin.init_plugin_process("demo-plugin")

    plugin_dir = tmp_path / "demo-plugin"
    assert (plugin_dir / "manifest.yaml").is_file()
    assert (plugin_dir / "main.py").is_file()
    assert (plugin_dir / "assets" / "icon.svg").is_file()
    assert (plugin_dir / ".vscode" / "launch.json").is_file()
    assert (plugin_dir / "readme" / "README_zh_Hans.md").is_file()
    assert (plugin_dir / ".github" / "workflows" / "release.yml").is_file()
    manifest = yaml.safe_load((plugin_dir / "manifest.yaml").read_text())
    assert manifest["metadata"]["author"] == "tester"
    assert manifest["metadata"]["name"] == "demo-plugin"
    assert manifest["execution"]["python"]["attr"] == "demoplugin"


def test_init_plugin_process_rejects_invalid_name(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    initplugin.init_plugin_process("bad name")

    assert "!!" in capsys.readouterr().out
    assert not (tmp_path / "bad name").exists()


def test_init_plugin_process_rejects_non_empty_existing_directory(
    tmp_path, monkeypatch, capsys
):
    plugin_dir = tmp_path / "demo"
    plugin_dir.mkdir()
    (plugin_dir / "main.py").write_text("existing", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    initplugin.init_plugin_process("demo")

    assert "!!" in capsys.readouterr().out
