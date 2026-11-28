"""Manifest and cross-plugin contract validation."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import yaml

import main as plugin_main

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PLUGIN_ROOT / "manifest.yaml"


def load_manifest():
    with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_tool_manifest(name: str):
    path = PLUGIN_ROOT / "components" / "tools" / f"{name}.yaml"
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def run(coro):
    return asyncio.run(coro)


def test_plugin_manifest_identity_matches_code():
    manifest = load_manifest()
    assert manifest["metadata"]["name"] == plugin_main.PLUGIN_NAME == "StickerHub"
    assert manifest["metadata"]["author"] == plugin_main.AUTHOR == "langbot-team"
    assert manifest["metadata"]["repository"] == (
        "https://github.com/langbot-app/LangBot/tree/master/plugins/misc/StickerHub"
    )
    assert manifest["execution"]["python"]["attr"] == "StickerHub"
    assert manifest["execution"]["python"]["path"] == "main.py"
    assert manifest["execution"]["sharedRuntime"] == "shared-runtime-v1"
    assert manifest["execution"]["componentModel"] == "stateless-v1"


def test_manifest_declares_minimal_permissions():
    manifest = load_manifest()
    assert manifest["spec"]["permissions"]["capabilities"] == ["storage.plugin"]
    assert manifest["spec"]["permissions"]["workspace_operations"] == []


def test_manifest_config_defaults_match_plugin():
    manifest = load_manifest()
    config = {item["name"]: item for item in manifest["spec"]["config"]}
    assert set(config) == {"public_base_url", "max_sticker_mb", "max_stickers", "materialize_to_assets"}
    assert config["max_sticker_mb"]["default"] == 8
    assert config["max_stickers"]["default"] == 2000
    assert config["materialize_to_assets"]["default"] is True


def test_manifest_components_are_discovered():
    manifest = load_manifest()
    components = manifest["spec"]["components"]
    assert "Page" in components and "Tool" in components
    pages = [Path(PLUGIN_ROOT / "components" / "pages")]
    tools = [Path(PLUGIN_ROOT / "components" / "tools")]
    assert pages[0].is_dir()
    assert tools[0].is_dir()
    assert (PLUGIN_ROOT / "components" / "pages" / "hub" / "hub.yaml").is_file()
    for tool_name in ("add_sticker", "get_sticker_url", "list_stickers", "delete_sticker"):
        assert (PLUGIN_ROOT / "components" / "tools" / f"{tool_name}.yaml").is_file()


def test_tool_manifests_match_code():
    expected = {
        "add_sticker": "AddSticker",
        "get_sticker_url": "GetStickerUrl",
        "list_stickers": "ListStickers",
        "delete_sticker": "DeleteSticker",
    }
    for name, attr in expected.items():
        manifest = load_tool_manifest(name)
        assert manifest["kind"] == "Tool"
        assert manifest["metadata"]["name"] == f"stickerhub_{name}"
        assert manifest["execution"]["python"]["attr"] == attr
        assert manifest["execution"]["python"]["path"] == f"{name}.py"
        assert manifest["spec"]["parameters"]["type"] == "object"


def test_stable_interface_name_is_declared():
    manifest = load_tool_manifest("get_sticker_url")
    assert manifest["metadata"]["name"] == "stickerhub_get_sticker_url"


def test_image_component_accepts_returned_url(make_plugin):
    """The URL returned by the tool must be usable as an IM image URL."""

    async def scenario():
        plugin, _ = make_plugin({"public_base_url": "https://bot.example.com"})
        await plugin.add_sticker("cat", b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
        url = await plugin.media_url("cat")

        from langbot_plugin.api.entities.builtin.platform.message import Image, MessageChain

        chain = MessageChain([Image(url=url)])
        assert chain[0].url == url
        assert "bot.example.com" in url
    run(scenario())


def test_add_sticker_tool_returns_machine_readable_json(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        from components.tools.add_sticker import AddSticker

        tool = AddSticker()
        tool.plugin = plugin
        import base64

        payload = "data:image/png;base64," + base64.b64encode(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
        ).decode("ascii")
        parsed = json.loads(await tool.call({"name": "cat", "data_url": payload}, {}, 1))
        assert parsed["ok"] is True
        assert parsed["sticker"]["url"].endswith(parsed["sticker"]["filename"])
    run(scenario())
