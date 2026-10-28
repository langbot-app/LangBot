"""Two installations must not share one OpenAI credential or endpoint.

Pre-fix failure this test pins: ``AIImagePlugin.initialize()`` cached a single
``AsyncOpenAI`` built from whichever config the worker started with, and
``Draw._execute`` called ``self.plugin.openai_client``. With that code the second
installation's ``!draw`` was sent with installation A's API key to installation
A's base URL, and ``assert not hasattr(plugin, "openai_client")`` fails.

Both installations are driven through the *same* plugin object and the *same*
``Draw`` component object under the real SDK ``bind_invocation`` /
``InstallationBinding`` task-local scope; only the per-binding config differs.
``sys.modules["openai"]`` is replaced with a recorder so no network or real SDK is
involved (the ``openai`` package is not installed for these local runs).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from langbot_plugin.api.proxies.invocation import bind_invocation
from langbot_plugin.entities.io.context import InstallationBinding

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from components.commands.draw import Draw  # noqa: E402
from main import AIImagePlugin  # noqa: E402

CONFIG_A = {
    "openai_api_key": "key-a",
    "api_base_url": "https://a.example/v1",
    "model_name": "model-a",
    "image_size": "768x1280",
}
CONFIG_B = {
    "openai_api_key": "key-b",
    "api_base_url": "https://b.example/v1",
    "model_name": "model-b",
    "image_size": "1280x768",
}


def _binding(installation: str) -> InstallationBinding:
    return InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid=f"workspace-{installation}",
        installation_uuid=installation,
        runtime_revision=1,
        artifact_digest="a" * 64,
    )


def _ctx(params: list[str]) -> SimpleNamespace:
    return SimpleNamespace(params=params)


@pytest.fixture
def fake_openai(monkeypatch):
    """Record every AsyncOpenAI construction, generate call, and close."""

    created: list[dict] = []

    class _Images:
        def __init__(self, entry: dict) -> None:
            self._entry = entry

        async def generate(self, **kwargs):
            self._entry["generate"] = kwargs
            return SimpleNamespace(
                data=[
                    SimpleNamespace(
                        url=f"https://img.test/{self._entry['api_key']}.png"
                    )
                ]
            )

    class _AsyncOpenAI:
        def __init__(self, *, api_key: str, base_url: str) -> None:
            entry = {"api_key": api_key, "base_url": base_url, "closed": False}
            created.append(entry)
            self.entry = entry
            self.images = _Images(entry)

        async def close(self) -> None:
            self.entry["closed"] = True

    module = types.ModuleType("openai")
    module.AsyncOpenAI = _AsyncOpenAI
    monkeypatch.setitem(sys.modules, "openai", module)
    return created


@pytest.mark.asyncio
async def test_each_installation_uses_its_own_key_base_url_model_and_size(
    fake_openai,
) -> None:
    handler = SimpleNamespace()
    plugin = AIImagePlugin()
    plugin.plugin_runtime_handler = handler
    draw = Draw()
    draw.plugin = plugin

    with bind_invocation(handler, config=CONFIG_A, binding=_binding("installation-a")):
        results_a = [item async for item in draw._execute(_ctx(["a", "cat"]))]
    with bind_invocation(handler, config=CONFIG_B, binding=_binding("installation-b")):
        results_b = [item async for item in draw._execute(_ctx(["b", "dog"]))]

    assert [(entry["api_key"], entry["base_url"]) for entry in fake_openai] == [
        ("key-a", "https://a.example/v1"),
        ("key-b", "https://b.example/v1"),
    ]
    assert fake_openai[0]["generate"] == {
        "model": "model-a",
        "prompt": "a cat",
        "size": "768x1280",
        "n": 1,
    }
    assert fake_openai[1]["generate"] == {
        "model": "model-b",
        "prompt": "b dog",
        "size": "1280x768",
        "n": 1,
    }
    assert results_a[-1].image_url == "https://img.test/key-a.png"
    assert results_b[-1].image_url == "https://img.test/key-b.png"
    assert [entry["closed"] for entry in fake_openai] == [True, True]

    # Nothing on the shared object retains a single tenant's credential.
    assert not hasattr(plugin, "openai_client")
    assert "key-a" not in repr(vars(plugin))
    assert "key-b" not in repr(vars(plugin))
    assert "a.example" not in repr(vars(plugin))
    assert "b.example" not in repr(vars(plugin))


@pytest.mark.asyncio
async def test_missing_key_reports_without_building_a_client(fake_openai) -> None:
    handler = SimpleNamespace()
    plugin = AIImagePlugin()
    plugin.plugin_runtime_handler = handler
    draw = Draw()
    draw.plugin = plugin

    config = {"openai_api_key": "", "api_base_url": "https://a.example/v1"}
    with bind_invocation(handler, config=config, binding=_binding("installation-a")):
        results = [item async for item in draw._execute(_ctx(["a", "cat"]))]

    assert fake_openai == []
    assert "API Key" in results[-1].text
    assert results[-1].image_url is None


def test_dedicated_config_without_an_invocation_is_still_used(fake_openai) -> None:
    # Dedicated workers attach the legacy config and call the same code path.
    plugin = AIImagePlugin()
    plugin.plugin_runtime_handler = SimpleNamespace()
    plugin.config = {"openai_api_key": "dedicated-key", "api_base_url": "https://d.example/v1"}

    client = plugin.create_client()

    assert client.entry["api_key"] == "dedicated-key"
    assert client.entry["base_url"] == "https://d.example/v1"
