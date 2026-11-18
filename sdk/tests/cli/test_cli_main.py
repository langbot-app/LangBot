from __future__ import annotations

import sys

import pytest

from langbot_plugin import cli
from langbot_plugin.box import server as box_server


def _run(monkeypatch, argv: list[str]):
    monkeypatch.setattr(sys, "argv", ["lbp", *argv])
    return cli.main()


def test_help_prints_usage(monkeypatch, capsys):
    _run(monkeypatch, ["help"])

    assert "LangBot Plugin CLI" in capsys.readouterr().out


def test_ver_prints_version(monkeypatch):
    calls: list = []
    monkeypatch.setattr(cli, "cli_print", lambda *args: calls.append(args))

    _run(monkeypatch, ["ver"])

    assert calls and calls[0][0] == "version_info"


def test_no_command_exits(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["lbp"])

    with pytest.raises(SystemExit):
        cli.main()


def test_unknown_command_exits(monkeypatch):
    monkeypatch.setattr(cli, "cli_print", lambda *args: None)

    with pytest.raises(SystemExit):
        _run(monkeypatch, ["does-not-exist"])


def test_login_dispatches(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        cli, "login_process", lambda token=None: captured.setdefault("token", token)
    )

    _run(monkeypatch, ["login", "--token", "abc"])

    assert captured["token"] == "abc"


def test_logout_dispatches(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        cli, "logout_process", lambda: captured.setdefault("called", True)
    )

    _run(monkeypatch, ["logout"])

    assert captured["called"] is True


def test_init_dispatches(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        cli, "init_plugin_process", lambda name: captured.setdefault("name", name)
    )

    _run(monkeypatch, ["init", "demo"])

    assert captured["name"] == "demo"


def test_comp_dispatches(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        cli,
        "generate_component_process",
        lambda kind: captured.setdefault("kind", kind),
    )

    _run(monkeypatch, ["comp", "tool"])

    assert captured["kind"] == "tool"


def test_run_dispatches(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(cli, "cli_print", lambda *args: None)
    monkeypatch.setattr(
        cli,
        "run_plugin_process",
        lambda *args, **kwargs: captured.update(args=args, kwargs=kwargs),
    )

    _run(monkeypatch, ["run", "--prod", "--plugin-debug-key", "key", "--tag", "demo"])

    assert captured["args"][1] is True
    assert captured["args"][2] == "key"
    assert captured["kwargs"]["tag"] == "demo"


def test_run_dispatches_without_tag(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(cli, "cli_print", lambda *args: None)
    monkeypatch.setattr(
        cli,
        "run_plugin_process",
        lambda *args, **kwargs: captured.update(args=args, kwargs=kwargs),
    )

    _run(monkeypatch, ["run"])

    assert captured["kwargs"]["tag"] == ""


def test_build_dispatches(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        cli,
        "build_plugin_process",
        lambda output: captured.setdefault("output", output),
    )

    _run(monkeypatch, ["build", "-o", "outdir"])

    assert captured["output"] == "outdir"


def test_publish_dispatches(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        cli, "publish_process", lambda: captured.setdefault("called", True)
    )

    _run(monkeypatch, ["publish"])

    assert captured["called"] is True


def test_rt_dispatches(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        cli.runtime_app, "main", lambda args: captured.setdefault("args", args)
    )

    _run(monkeypatch, ["rt", "--ws-control-port", "1234"])

    assert captured["args"].ws_control_port == 1234


def test_box_dispatches(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        box_server, "main", lambda args: captured.setdefault("args", args)
    )

    _run(monkeypatch, ["box", "--ws-control-port", "2222"])

    assert captured["args"].ws_control_port == 2222
