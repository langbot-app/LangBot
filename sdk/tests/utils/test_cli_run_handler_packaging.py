from __future__ import annotations

import base64
import shutil
import subprocess
from pathlib import Path

import yaml

from langbot_plugin.cli.run.handler import PluginRuntimeHandler
from langbot_plugin.entities.io.actions.enums import RuntimeToPluginAction
from tests.helpers.protocol import ProtocolConnection

FIXTURE_PLUGIN = (
    Path(__file__).resolve().parent.parent / "fixtures" / "eba_event_probe_plugin"
)


def _copy_plugin(tmp_path: Path) -> Path:
    destination = tmp_path / "plugin"
    shutil.copytree(FIXTURE_PLUGIN, destination)
    return destination


def _new_handler() -> PluginRuntimeHandler:
    connection = ProtocolConnection()

    async def _initialize(settings: dict) -> None:
        return None

    return PluginRuntimeHandler(connection, _initialize)


def _build_action(handler: PluginRuntimeHandler):
    return handler.actions[RuntimeToPluginAction.BUILD_PLUGIN_PACKAGE.value]


def _git_sync_action(handler: PluginRuntimeHandler):
    return handler.actions[RuntimeToPluginAction.GIT_SYNC_PLUGIN.value]


async def test_build_plugin_package_action_persists_edits(tmp_path, monkeypatch):
    root = _copy_plugin(tmp_path)
    monkeypatch.chdir(root)
    handler = _new_handler()
    sent: dict = {}

    async def _send_file(file_bytes, file_extension, **kwargs):
        sent["bytes"] = file_bytes
        sent["extension"] = file_extension
        return "file-key"

    monkeypatch.setattr(handler, "send_file", _send_file)

    response = await _build_action(handler)(
        {"manifest_overrides": {"version": "1.0.1"}}
    )

    assert response.code == 0
    assert response.data["package_file_key"] == "file-key"
    assert sent["extension"] == "lbpkg"
    assert sent["bytes"]

    # The WebUI edit is written back to the plugin's own manifest.
    on_disk = yaml.safe_load((root / "manifest.yaml").read_text(encoding="utf-8"))
    assert on_disk["metadata"]["version"] == "1.0.1"


async def test_build_plugin_package_action_applies_icon(tmp_path, monkeypatch):
    root = _copy_plugin(tmp_path)
    monkeypatch.chdir(root)
    handler = _new_handler()

    async def _send_file(file_bytes, file_extension, **kwargs):
        return "file-key"

    monkeypatch.setattr(handler, "send_file", _send_file)
    icon = "data:image/png;base64," + base64.b64encode(b"png-bytes").decode()

    response = await _build_action(handler)(
        {"manifest_overrides": {"icon_base64": icon}}
    )

    assert response.code == 0
    assert (root / "assets" / "icon.png").read_bytes() == b"png-bytes"


async def test_build_plugin_package_action_rejects_bad_icon(tmp_path, monkeypatch):
    root = _copy_plugin(tmp_path)
    monkeypatch.chdir(root)
    handler = _new_handler()

    response = await _build_action(handler)(
        {"manifest_overrides": {"icon_base64": "!!!not-base64!!!"}}
    )

    assert response.code == 1
    assert "icon" in response.message.lower()


async def test_build_plugin_package_action_missing_manifest(tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    handler = _new_handler()

    response = await _build_action(handler)({})

    assert response.code == 1


async def test_git_sync_plugin_action_pushes(tmp_path, monkeypatch):
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        capture_output=True,
        text=True,
    )
    root = _copy_plugin(tmp_path)
    monkeypatch.chdir(root)
    handler = _new_handler()

    response = await _git_sync_action(handler)(
        {
            "repo_url": str(remote),
            "commit_message": "sync",
            "manifest_overrides": {"version": "2.0.0"},
        }
    )

    assert response.code == 0
    assert response.data["pushed"] is True
    assert response.data["committed"] is True
