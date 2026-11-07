"""Page backend contract for the StickerHub management page."""

from __future__ import annotations

import asyncio
import base64

from langbot_plugin.api.definition.components.page import PageRequest

from components.pages.hub.hub import HubPage

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16


def run(coro):
    return asyncio.run(coro)


def page_for(plugin):
    page = HubPage()
    page.plugin = plugin
    return page


def request(endpoint, method="GET", body=None):
    return PageRequest(endpoint=endpoint, method=method, body=body)


def test_stats_endpoint(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        await plugin.add_sticker("cat", PNG)
        page = page_for(plugin)
        response = await page.handle_api(request("/stats"))
        assert response.error is None
        assert response.data["count"] == 1
    run(scenario())


def test_list_endpoint(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        await plugin.add_sticker("cat", PNG)
        await plugin.add_sticker("dog", JPEG)
        page = page_for(plugin)
        response = await page.handle_api(request("/list", body={"limit": 1, "offset": 0}))
        assert response.data["count"] == 1
        assert response.data["total"] == 2
    run(scenario())


def test_item_and_image_endpoints(make_plugin):
    async def scenario():
        plugin, _ = make_plugin({"public_base_url": "http://localhost:5300"})
        await plugin.add_sticker("cat", PNG)
        page = page_for(plugin)

        item = await page.handle_api(request("/item", body={"name": "cat"}))
        assert item.data["slug"] == "cat"
        assert item.data["url"].startswith("http://localhost:5300/api/v1/plugins/")

        # /image is the fallback path only: without ``with_data`` it reports
        # where the bytes are, without shipping them.
        image = await page.handle_api(request("/image", body={"name": "cat"}))
        assert image.data["name"] == "cat"
        assert image.data["mime"] == "image/png"
        assert image.data["url"] == item.data["url"]
        assert "base64" not in image.data

        # The fallback still carries the bytes when the page asks for them.
        fallback = await page.handle_api(
            request("/image", body={"name": "cat", "with_data": True})
        )
        assert fallback.data["base64"]
    run(scenario())


def test_item_missing_returns_error(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        page = page_for(plugin)
        response = await page.handle_api(request("/item", body={"name": "nope"}))
        assert response.error == "sticker not found"
    run(scenario())


def test_add_from_data_url(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        page = page_for(plugin)
        payload = "data:image/png;base64,iVBORw0KGgo="
        response = await page.handle_api(request("/add", "POST", {"name": "cat", "data_url": payload}))
        assert response.error is None
        assert response.data["slug"] == "cat"
        assert await plugin.get_sticker("cat") is not None
    run(scenario())


def test_add_requires_url_or_data(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        page = page_for(plugin)
        response = await page.handle_api(request("/add", "POST", {"name": "cat"}))
        assert response.error == "url or data_url is required"
    run(scenario())


def test_add_rejects_missing_name(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        page = page_for(plugin)
        response = await page.handle_api(
            request("/add", "POST", {"data_url": "data:image/png;base64,AAAA"})
        )
        assert response.error == "name is required"
    run(scenario())


def test_delete_and_clear(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        await plugin.add_sticker("cat", PNG)
        page = page_for(plugin)

        deleted = await page.handle_api(request("/delete", "POST", {"name": "cat"}))
        assert deleted.data["deleted"] is True
        assert await plugin.get_sticker("cat") is None

        await plugin.add_sticker("dog", JPEG)
        cleared = await page.handle_api(request("/clear", "DELETE"))
        assert cleared.data["cleared"] == 1
    run(scenario())


def test_delete_missing_returns_error(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        page = page_for(plugin)
        response = await page.handle_api(request("/delete", "POST", {"name": "nope"}))
        assert response.error == "sticker not found"
    run(scenario())


def test_unknown_endpoint(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        page = page_for(plugin)
        response = await page.handle_api(request("/nope"))
        assert "Unknown" in response.error
    run(scenario())


def test_upload_endpoints_round_trip(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        page = page_for(plugin)

        begin = await page.handle_api(request("/upload/begin", "POST", {}))
        assert begin.error is None
        session = begin.data["session"]
        assert begin.data["chunk_bytes"] == 256 * 1024

        chunk = await page.handle_api(
            request(
                "/upload/chunk",
                "POST",
                {"session": session, "index": 0, "data": base64.b64encode(PNG).decode()},
            )
        )
        assert chunk.error is None
        assert chunk.data["received"] == len(PNG)

        done = await page.handle_api(
            request("/upload/finish", "POST", {"session": session, "name": "chunky"})
        )
        assert done.error is None
        assert done.data["slug"] == "chunky"
        assert await plugin.get_sticker("chunky") is not None
    run(scenario())


def test_upload_endpoint_validation(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        page = page_for(plugin)
        missing_session = await page.handle_api(request("/upload/chunk", "POST", {"index": 0}))
        assert missing_session.error == "session is required"
        missing_index = await page.handle_api(
            request("/upload/chunk", "POST", {"session": "abc", "data": "AAAA"})
        )
        assert missing_index.error == "index is required"
        bad_finish = await page.handle_api(
            request("/upload/finish", "POST", {"session": "nope", "name": "cat"})
        )
        assert "no data" in bad_finish.error
    run(scenario())


def test_item_payload_carries_url_at_the_top_level(make_plugin):
    """The page reads ``item.url`` directly.

    ``langbot.api()`` already unwraps four layers (PageResponse.ok -> the HTTP
    ``data`` -> ``resp.data.data`` -> the SDK's ``resolve(data.data)``), so a
    page that writes ``item.data.url`` sees ``undefined`` forever. Pin the
    shape instead of the page's guess.
    """

    async def scenario():
        plugin, _ = make_plugin({"public_base_url": "http://localhost:5300"})
        await plugin.add_sticker("cat", PNG)
        page = page_for(plugin)
        response = await page.handle_api(request("/item", body={"name": "cat"}))

        assert response.error is None
        assert "url" in response.data, "url must sit on the payload itself"
        assert response.data["url"].startswith("http://localhost:5300/api/v1/plugins/")
        # Nothing in the payload is a nested wrapper the page would have to dig into.
        assert not isinstance(response.data.get("data"), dict)
    run(scenario())


def test_list_items_carry_url_at_the_top_level(make_plugin):
    async def scenario():
        plugin, _ = make_plugin({"public_base_url": "http://localhost:5300"})
        await plugin.add_sticker("cat", PNG)
        page = page_for(plugin)
        response = await page.handle_api(request("/list", body={"limit": 10}))
        item = response.data["items"][0]
        assert "url" in item
        assert "data" not in item
    run(scenario())
