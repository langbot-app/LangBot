"""Tool contract and the stable cross-plugin interface."""

from __future__ import annotations

import asyncio
import json

from components.tools.add_sticker import AddSticker
from components.tools.delete_sticker import DeleteSticker
from components.tools.get_sticker_url import GetStickerUrl
from components.tools.list_stickers import ListStickers

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16


def run(coro):
    return asyncio.run(coro)


def make_tool(plugin, tool):
    tool.plugin = plugin
    return tool


def data_url(payload: bytes) -> str:
    import base64

    return "data:image/png;base64," + base64.b64encode(payload).decode("ascii")


def test_add_sticker_tool_stores_image(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        tool = make_tool(plugin, AddSticker())
        result = json.loads(
            await tool.call({"name": "cat", "data_url": data_url(PNG)}, {}, 1)
        )
        assert result["ok"] is True
        assert result["sticker"]["slug"] == "cat"
        assert await plugin.get_sticker("cat") is not None
    run(scenario())


def test_add_sticker_tool_requires_input(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        tool = make_tool(plugin, AddSticker())
        assert json.loads(await tool.call({}, {}, 1))["ok"] is False
        assert json.loads(await tool.call({"name": "cat"}, {}, 1))["ok"] is False
    run(scenario())


def test_get_sticker_url_is_the_stable_contract(make_plugin):
    async def scenario():
        plugin, _ = make_plugin({"public_base_url": "http://localhost:5300"})
        await plugin.add_sticker("cat", PNG)
        tool = make_tool(plugin, GetStickerUrl())
        url = await tool.call({"name": "cat"}, {}, 1)
        assert url == (
            "http://localhost:5300/api/v1/plugins/langbot-team/StickerHub/assets/stickers/"
            + (await plugin.get_sticker("cat"))["filename"]
        )
        # The same URL comes back from the plugin API and the Page endpoint, so
        # HumanTakeover gets a stable value regardless of the caller.
        page_url = (await plugin.get_sticker("cat"))["url"]
        assert page_url == url
    run(scenario())


def test_get_sticker_url_missing_is_error_string(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        tool = make_tool(plugin, GetStickerUrl())
        url = await tool.call({"name": "nope"}, {}, 1)
        assert url.startswith("error:")
        assert "nope" in url
    run(scenario())


def test_list_stickers_tool(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        await plugin.add_sticker("cat", PNG)
        await plugin.add_sticker("dog", JPEG)
        tool = make_tool(plugin, ListStickers())
        result = json.loads(await tool.call({"limit": 5}, {}, 1))
        assert result["ok"] is True
        assert result["total"] == 2
        assert {item["name"] for item in result["items"]} == {"cat", "dog"}
        for item in result["items"]:
            assert item["uri"].startswith("/api/v1/plugins/langbot-team/StickerHub/assets/stickers/")
    run(scenario())


def test_delete_sticker_tool(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        await plugin.add_sticker("cat", PNG)
        tool = make_tool(plugin, DeleteSticker())
        assert json.loads(await tool.call({"name": "cat"}, {}, 1))["ok"] is True
        assert json.loads(await tool.call({"name": "cat"}, {}, 1))["ok"] is False
    run(scenario())


def test_add_then_get_round_trip_through_tools(make_plugin):
    """The AI path: store via the tool, then fetch the stable URL via the tool."""

    async def scenario():
        plugin, _ = make_plugin({"public_base_url": "https://bot.example.com"})
        add = make_tool(plugin, AddSticker())
        get = make_tool(plugin, GetStickerUrl())

        stored = json.loads(
            await add.call({"name": "问候", "data_url": data_url(PNG)}, {}, 1)
        )
        url = await get.call({"name": "问候"}, {}, 1)
        assert url == stored["sticker"]["url"]
        assert url.startswith("https://bot.example.com/api/v1/plugins/langbot-team/StickerHub/")
    run(scenario())
