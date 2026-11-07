"""Shared fixtures for the StickerHub test suite.

The plugin is driven through a stub Host that mirrors the real plugin-storage
transport (``SET/GET/DELETE_PLUGIN_STORAGE`` / ``GET_PLUGIN_STORAGE_KEYS``)
without needing a live LangBot instance.
"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

# A shared-runtime worker without an invocation binding must refuse tenant
# state. Keep the tests on the dedicated profile unless they bind explicitly.
os.environ.pop("LANGBOT_PLUGIN_RUNTIME_PROFILE", None)

from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action  # noqa: E402
from langbot_plugin.entities.io.errors import ActionCallError  # noqa: E402

from main import StickerHub  # noqa: E402

# A tiny PNG-like payload: only the magic header is needed for mime sniffing.
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 16


class FakeHost:
    """Stub plugin-storage backend with call recording."""

    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}
        self.calls: list[tuple[str, dict]] = []
        self.failures: set[str] = set()

    async def call_action(self, action, data, *args, **kwargs):
        self.calls.append((action, dict(data)))
        if action in self.failures:
            raise OSError(f"stub refused {action}")
        key = data.get("key")
        if action == Action.GET_PLUGIN_STORAGE_KEYS:
            return {"keys": list(self.data)}
        if action == Action.GET_PLUGIN_STORAGE:
            if key not in self.data:
                # The real Host fails the action for a missing key.
                raise ActionCallError(f"Storage with key {key} not found")
            return {"value_base64": base64.b64encode(self.data[key]).decode("ascii")}
        if action == Action.SET_PLUGIN_STORAGE:
            self.data[key] = base64.b64decode(data["value_base64"])
            return {}
        if action == Action.DELETE_PLUGIN_STORAGE:
            self.data.pop(key, None)
            return {}
        raise AssertionError(f"unexpected action {action}")


def bind(plugin: StickerHub, installation_uuid: str = "installation-a") -> StickerHub:
    """Give one plugin object a trusted installation binding."""

    plugin.get_installation_binding = lambda: SimpleNamespace(
        instance_uuid="instance-a",
        workspace_uuid="workspace-a",
        installation_uuid=installation_uuid,
    )
    return plugin


def build_plugin(
    config: dict | None = None,
    *,
    host: FakeHost | None = None,
    installation_uuid: str | None = "installation-a",
) -> tuple[StickerHub, FakeHost]:
    host = host or FakeHost()
    plugin = StickerHub()
    plugin.config = dict(config or {})
    plugin.plugin_runtime_handler = host
    if installation_uuid is not None:
        bind(plugin, installation_uuid)
    return plugin, host


@pytest.fixture
def make_plugin():
    return build_plugin


@pytest.fixture
def host():
    return FakeHost()


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    """Run every test from its own temp dir.

    StickerHub materialises served copies into ``assets/stickers/``; keeping
    that write inside the test's temporary directory avoids polluting the plugin
    source tree.
    """

    monkeypatch.chdir(tmp_path)
    return tmp_path
