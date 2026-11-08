"""Storage-layer behaviour: content addressing, eviction and isolation."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import stickerlib
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
PNG2 = b"\x89PNG\r\n\x1a\n" + b"\x01" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16


def run(coro):
    return asyncio.run(coro)


def blob_keys(host):
    return [key for key in host.data if ":blob:" in key]


def meta_keys(host, scope="installation-a"):
    return [key for key in host.data if f":{scope}:meta:" in key]


def test_add_and_get_roundtrip(make_plugin):
    async def scenario():
        plugin, host = make_plugin()
        created = await plugin.add_sticker("cat", PNG)
        assert created["slug"] == "cat"
        assert created["mime"] == "image/png"
        assert created["size"] == len(PNG)
        assert created["filename"].endswith(".png")
        assert created["path"] == f"assets/stickers/{created['filename']}"

        fetched = await plugin.get_sticker("cat")
        assert fetched is not None
        assert fetched["filename"] == created["filename"]
        assert fetched["sha256"] == created["sha256"]
    run(scenario())


def test_content_addressing_shares_one_blob(make_plugin):
    async def scenario():
        plugin, host = make_plugin()
        await plugin.add_sticker("cat", PNG)
        await plugin.add_sticker("dog", PNG)
        await plugin.add_sticker("bird", JPEG)
        blobs = blob_keys(host)
        assert len(blobs) == 2
        assert len(meta_keys(host)) == 3
    run(scenario())


def test_add_same_name_and_content_is_idempotent(make_plugin):
    async def scenario():
        plugin, host = make_plugin()
        first = await plugin.add_sticker("cat", PNG)
        second = await plugin.add_sticker("cat", PNG)
        assert first["url"] == second["url"]
        assert first["filename"] == second["filename"]
        assert len(meta_keys(host)) == 1
        assert len(blob_keys(host)) == 1
    run(scenario())


def test_overwrite_changes_filename_and_keeps_history_url(make_plugin):
    async def scenario():
        plugin, host = make_plugin()
        first = await plugin.add_sticker("cat", PNG)
        second = await plugin.add_sticker("cat", PNG2)
        assert second["filename"] != first["filename"]
        assert second["sha256"] != first["sha256"]
        assert (await plugin.get_sticker("cat"))["filename"] == second["filename"]
        assert len(blob_keys(host)) == 2
    run(scenario())


def test_get_missing_returns_none(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        assert await plugin.get_sticker("missing") is None
        assert await plugin.get_sticker("missing") is None
    run(scenario())


def test_delete_removes_blob_when_last_reference(make_plugin):
    async def scenario():
        plugin, host = make_plugin()
        await plugin.add_sticker("cat", PNG)
        assert await plugin.delete_sticker("cat") is True
        assert await plugin.get_sticker("cat") is None
        assert blob_keys(host) == []
        assert meta_keys(host) == []
    run(scenario())


def test_delete_keeps_blob_while_still_referenced(make_plugin):
    async def scenario():
        plugin, host = make_plugin()
        await plugin.add_sticker("cat", PNG)
        await plugin.add_sticker("dog", PNG)
        assert await plugin.delete_sticker("cat") is True
        assert len(blob_keys(host)) == 1
        assert await plugin.get_sticker("dog") is not None
    run(scenario())


def test_delete_missing_returns_false(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        assert await plugin.delete_sticker("missing") is False
    run(scenario())


def test_size_limit_is_enforced(make_plugin):
    async def scenario():
        plugin, _ = make_plugin({"max_sticker_mb": 1})
        payload = b"\x89PNG\r\n\x1a\n" + b"\x00" * (2 * 1024 * 1024)
        with pytest.raises(ValueError, match="maximum"):
            await plugin.add_sticker("big", payload)
    run(scenario())


def test_unsupported_and_unlabelled_bytes_are_rejected(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        with pytest.raises(ValueError, match="unsupported image type"):
            await plugin.add_sticker("junk", b"not an image", "text/plain")
        with pytest.raises(ValueError, match="unsupported image type"):
            await plugin.add_sticker("junk2", b"not an image")
    run(scenario())


def test_name_and_data_validation(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        with pytest.raises(ValueError, match="name is required"):
            await plugin.add_sticker("   ", PNG)
        with pytest.raises(ValueError, match="empty"):
            await plugin.add_sticker("cat", b"")
    run(scenario())


def test_max_stickers_evicts_oldest(make_plugin):
    async def scenario():
        plugin, host = make_plugin({"max_stickers": 2})
        clock = iter(range(100, 1000))
        with patch.object(stickerlib.time, "time", side_effect=lambda: next(clock)):
            await plugin.add_sticker("first", PNG)
            await plugin.add_sticker("second", PNG2)
            await plugin.add_sticker("third", JPEG)
        page = await plugin.list_stickers()
        names = sorted(item["slug"] for item in page["items"])
        assert names == ["second", "third"]
        assert page["total"] == 2
        assert len(meta_keys(host)) == 2
    run(scenario())


def test_list_paginates(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        for index in range(5):
            await plugin.add_sticker(f"sticker-{index}", PNG + bytes([index]))
        first = await plugin.list_stickers(limit=2, offset=0)
        second = await plugin.list_stickers(limit=2, offset=2)
        assert first["total"] == 5
        assert first["count"] == 2
        assert second["count"] == 2
        ids_first = {item["slug"] for item in first["items"]}
        ids_second = {item["slug"] for item in second["items"]}
        assert not (ids_first & ids_second)
    run(scenario())


def test_clear_removes_only_scoped_keys(make_plugin):
    async def scenario():
        plugin, host = make_plugin()
        await plugin.add_sticker("cat", PNG)
        # Another installation's unrelated row must survive.
        host.data["sh:other-scope:meta:kept"] = b"{}"
        removed = await plugin.clear_stickers()
        assert removed == 1  # one sticker was removed (its blob too)
        assert await plugin.get_sticker("cat") is None
        assert "sh:other-scope:meta:kept" in host.data
    run(scenario())


def test_stats_counts_bytes_and_mimes(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        await plugin.add_sticker("cat", PNG)
        await plugin.add_sticker("dog", JPEG)
        stats = await plugin.stats()
        assert stats["count"] == 2
        assert stats["bytes"] == len(PNG) + len(JPEG)
        assert stats["mime_counts"] == {"image/png": 1, "image/jpeg": 1}
        assert stats["scope"] == "instance-a:workspace-a:installation-a"
    run(scenario())


def test_installation_scope_isolation(make_plugin):
    async def scenario():
        plugin, host = make_plugin()
        await plugin.add_sticker("cat", PNG)
        a_page = await plugin.list_stickers()
        assert a_page["total"] == 1
        assert a_page["items"][0]["slug"] == "cat"

        plugin.get_installation_binding = lambda: SimpleNamespace(
            instance_uuid="instance-b",
            workspace_uuid="workspace-b",
            installation_uuid="installation-b",
        )
        await plugin.add_sticker("cat", PNG2)

        b_page = await plugin.list_stickers()
        assert b_page["total"] == 1
        assert b_page["items"][0]["slug"] == "cat"
        assert b_page["items"][0]["sha256"] != a_page["items"][0]["sha256"]
        # Storage rows stay scoped: each installation keeps its own copy.
        assert "instance-a" in meta_keys(host, "installation-a")[0]
        assert "instance-b" in meta_keys(host, "installation-b")[0]
    run(scenario())


def test_concurrent_adds_do_not_corrupt(make_plugin):
    async def scenario():
        plugin, host = make_plugin()

        async def add(index):
            await plugin.add_sticker(f"item-{index}", PNG + bytes([index]))

        await asyncio.gather(*(add(index) for index in range(12)))
        page = await plugin.list_stickers()
        assert page["total"] == 12
        assert len(meta_keys(host)) == 12
        assert len(blob_keys(host)) == 12
    run(scenario())


def test_add_returns_metadata_without_url_when_base_unset(make_plugin):
    async def scenario():
        plugin, _ = make_plugin({"public_base_url": ""})
        item = await plugin.add_sticker("cat", PNG)
        assert item["url"] == (
            f"/api/v1/plugins/langbot-team/StickerHub/assets/stickers/{item['filename']}"
        )
    run(scenario())


def test_stats_reuses_the_list_scan(make_plugin):
    """One refresh calls /list then /stats; the key scan must run once."""

    async def scenario():
        plugin, host = make_plugin()
        for index in range(5):
            await plugin.add_sticker(f"item-{index}", PNG + bytes([index]))
        host.calls.clear()

        page = await plugin.list_stickers()
        assert page["total"] == 5
        await plugin.stats()

        scans = [c for c in host.calls if c[0] is Action.GET_PLUGIN_STORAGE_KEYS]
        assert len(scans) == 1, f"expected one key scan, saw {len(scans)}"
        reads = [c for c in host.calls if c[0] is Action.GET_PLUGIN_STORAGE]
        assert len(reads) == 5, f"expected one read per sticker, saw {len(reads)}"
    run(scenario())


def test_list_does_not_read_metadata_twice(make_plugin):
    async def scenario():
        plugin, host = make_plugin()
        for index in range(8):
            await plugin.add_sticker(f"item-{index}", PNG + bytes([index]))
        host.calls.clear()
        await plugin.list_stickers()
        reads = [c for c in host.calls if c[0] is Action.GET_PLUGIN_STORAGE]
        assert len(reads) == 8, "a 2000-row refresh must stay one read per row"
    run(scenario())


def test_mutations_invalidate_the_snapshot(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        await plugin.add_sticker("cat", PNG)
        assert (await plugin.list_stickers())["total"] == 1
        await plugin.add_sticker("dog", PNG2)
        assert (await plugin.list_stickers())["total"] == 2
        await plugin.delete_sticker("cat")
        assert (await plugin.list_stickers())["total"] == 1
        await plugin.clear_stickers()
        assert (await plugin.list_stickers())["total"] == 0
    run(scenario())


def test_stats_reports_a_human_readable_size(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        await plugin.add_sticker("cat", PNG + b"\x00" * 2048)
        stats = await plugin.stats()
        assert stats["display_bytes"].endswith(("B", "KB", "MB"))
        assert "\n" not in stats["display_bytes"]
    run(scenario())
