from __future__ import annotations

import yaml

from langbot_plugin.cli.commands import gencomponent


def _write_plugin_manifest(path):
    (path / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "apiVersion": "v1",
                "kind": "Plugin",
                "metadata": {
                    "author": "tester",
                    "name": "demo",
                    "label": {"en_US": "Demo"},
                    "version": "0.1.0",
                },
                "spec": {"components": {}},
                "execution": {"python": {"path": "main.py", "attr": "Demo"}},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_generate_component_requires_plugin_root(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    gencomponent.generate_component_process("Command")

    assert "!!" in capsys.readouterr().out


def test_generate_component_reports_unknown_component(tmp_path, monkeypatch, capsys):
    _write_plugin_manifest(tmp_path)
    monkeypatch.chdir(tmp_path)

    gencomponent.generate_component_process("Nope")

    output = capsys.readouterr().out
    assert "!!" in output
    assert "Command" in output


def test_generate_command_component_creates_files_and_updates_manifest(
    tmp_path, monkeypatch
):
    _write_plugin_manifest(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gencomponent, "cli_print", lambda *args: None)
    monkeypatch.setattr(
        gencomponent,
        "input_form_values",
        lambda fields: {
            "cmd_name": "hello",
            "cmd_description": "Say hello",
        },
    )

    gencomponent.generate_component_process("Command")

    assert (tmp_path / "components" / "__init__.py").is_file()
    assert (tmp_path / "components" / "commands" / "__init__.py").is_file()
    assert (tmp_path / "components" / "commands" / "hello.yaml").is_file()
    assert (tmp_path / "components" / "commands" / "hello.py").is_file()
    manifest = yaml.safe_load((tmp_path / "manifest.yaml").read_text())
    assert manifest["spec"]["components"]["Command"] == {
        "fromDirs": [{"path": "components/commands/"}]
    }


def test_generate_page_component_skips_python_package_init_files(tmp_path, monkeypatch):
    _write_plugin_manifest(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gencomponent, "cli_print", lambda *args: None)
    monkeypatch.setattr(
        gencomponent,
        "input_form_values",
        lambda fields: {"page_name": "settings"},
    )

    gencomponent.generate_component_process("Page")

    assert not (tmp_path / "components" / "__init__.py").exists()
    assert not (tmp_path / "components" / "pages" / "__init__.py").exists()
    assert (tmp_path / "components" / "pages" / "settings.yaml").is_file()
    assert (tmp_path / "components" / "pages" / "settings.html").is_file()


def test_generate_runner_declares_usage_and_builds(tmp_path, monkeypatch):
    from langbot_plugin.cli.commands.buildplugin import build_plugin_process
    from langbot_plugin.utils.discover.engine import ComponentDiscoveryEngine

    _write_plugin_manifest(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        gencomponent,
        "input_form_values",
        lambda fields: {
            "runner_name": "echo",
            "runner_label": "Echo",
            "runner_description": "Echo input",
            "runner_attr": "EchoRunner",
        },
    )
    gencomponent.generate_component_process("Runner")
    component = ComponentDiscoveryEngine().load_component_manifest(
        "components/runner/echo.yaml"
    )
    assert component is not None
    assert component.spec["usages"] == ["agent"]
    assert build_plugin_process(str(tmp_path / "dist"))
