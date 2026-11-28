"""Stable URL and asset-materialisation behaviour."""

from __future__ import annotations

import asyncio

from stickerlib import media_path

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
PNG2 = b"\x89PNG\r\n\x1a\n" + b"\x01" * 16


def run(coro):
    return asyncio.run(coro)


def test_media_url_is_absolute_when_base_configured(make_plugin):
    async def scenario():
        plugin, _ = make_plugin({"public_base_url": "http://localhost:5300"})
        await plugin.add_sticker("cat", PNG)
        url = await plugin.media_url("cat")
        assert url.startswith(
            "http://localhost:5300/api/v1/plugins/langbot-team/StickerHub/assets/stickers/"
        )
        assert url.endswith(".png")
    run(scenario())


def test_media_url_is_stable_for_the_same_sticker(make_plugin):
    async def scenario():
        plugin, _ = make_plugin({"public_base_url": "http://localhost:5300"})
        first = await plugin.add_sticker("cat", PNG)
        again = await plugin.add_sticker("cat", PNG)
        assert first["url"] == again["url"]
        assert first["filename"] == again["filename"]

        # Different names are distinct stickers, so their URLs differ; both
        # still point at the same content-addressed blob.
        other = await plugin.add_sticker("dog", PNG)
        assert other["filename"] != first["filename"]
        assert other["sha256"] == first["sha256"]
        assert await plugin.media_url("cat") == first["url"]
    run(scenario())


def test_media_url_changes_when_content_changes(make_plugin):
    async def scenario():
        plugin, _ = make_plugin({"public_base_url": "http://localhost:5300"})
        first = await plugin.add_sticker("cat", PNG)
        second = await plugin.add_sticker("cat", PNG2)
        assert first["url"] != second["url"]
        assert await plugin.media_url("cat") == second["url"]
    run(scenario())


def test_media_url_missing_returns_none(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        assert await plugin.media_url("missing") is None
    run(scenario())


def test_served_path_matches_asset_path(make_plugin):
    plugin, _ = make_plugin()
    assert plugin.served_path("cat-abc.png") == media_path("cat-abc.png")
    assert plugin.served_path("cat-abc.png") == "assets/stickers/cat-abc.png"


def test_materialize_writes_asset_file(make_plugin, tmp_path, monkeypatch):
    async def scenario():
        monkeypatch.chdir(tmp_path)
        plugin, _ = make_plugin({"materialize_to_assets": True})
        item = await plugin.add_sticker("cat", PNG)
        written = tmp_path / "assets" / "stickers" / item["filename"]
        assert written.is_file()
        assert written.read_bytes() == PNG
        # No temp file left behind.
        assert not list((tmp_path / "assets" / "stickers").glob("*.tmp"))
    run(scenario())


def test_materialize_is_disabled_by_config(make_plugin, tmp_path, monkeypatch):
    async def scenario():
        monkeypatch.chdir(tmp_path)
        plugin, _ = make_plugin({"materialize_to_assets": False})
        item = await plugin.add_sticker("cat", PNG)
        assert not (tmp_path / "assets" / "stickers" / item["filename"]).exists()
    run(scenario())


def test_materialize_never_escapes_sticker_dir(make_plugin, tmp_path, monkeypatch):
    async def scenario():
        monkeypatch.chdir(tmp_path)
        plugin, _ = make_plugin()
        await plugin.add_sticker("cat", PNG)
        # A filename containing path separators cannot escape the directory.
        assert await plugin._materialize({"filename": "../evil.png", "slug": "cat"}) is False
        assert not (tmp_path / "evil.png").exists()
    run(scenario())
