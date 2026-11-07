"""Materialisation must work on an installed, read-only artifact tree.

``_make_tree_read_only()`` in the SDK chmods an installed ``code/`` tree to
``0o555``/``0o444``. ``mkdir`` then fails with ``EACCES`` even for the owner,
so every upload silently stayed in plugin storage and every stable URL was a
404. ``os.chmod`` still works on an owner-owned directory, so the writer has to
re-grant the write bit instead of giving up.
"""

from __future__ import annotations

import asyncio
import os
import stat

import pytest

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def run(coro):
    return asyncio.run(coro)


def make_read_only(path):
    """Mirror the SDK's read-only tree, including the stickers directory."""

    stickers = path / "assets" / "stickers"
    stickers.mkdir(parents=True, exist_ok=True)
    (path / "assets" / "icon.svg").write_text("<svg/>", encoding="utf-8")
    (stickers / ".gitkeep").write_text("", encoding="utf-8")
    for entry in (stickers, path / "assets", path):
        entry.chmod(0o555)
    for entry in (path / "assets" / "icon.svg", stickers / ".gitkeep"):
        entry.chmod(0o444)
    return stickers


def test_missing_stickers_dir_is_created_in_a_read_only_tree(make_plugin, tmp_path, monkeypatch):
    async def scenario():
        # Installed artifacts ship no assets/stickers at all: the empty
        # directory is gone, leaving only a read-only assets/.
        (tmp_path / "assets").mkdir()
        (tmp_path / "assets").chmod(0o555)
        monkeypatch.chdir(tmp_path)

        plugin, _ = make_plugin()
        item = await plugin.add_sticker("cat", PNG)

        written = tmp_path / "assets" / "stickers" / item["filename"]
        assert written.is_file(), "the sticker never reached the served directory"
        assert written.read_bytes() == PNG
    run(scenario())


def test_existing_read_only_stickers_dir_still_accepts_writes(make_plugin, tmp_path, monkeypatch):
    async def scenario():
        make_read_only(tmp_path)
        monkeypatch.chdir(tmp_path)

        plugin, _ = make_plugin()
        item = await plugin.add_sticker("cat", PNG)

        written = tmp_path / "assets" / "stickers" / item["filename"]
        assert written.is_file()
        assert written.read_bytes() == PNG
        assert not list(written.parent.glob("*.tmp"))
    run(scenario())


def test_existing_asset_files_are_left_alone(make_plugin, tmp_path, monkeypatch):
    async def scenario():
        stickers = make_read_only(tmp_path)
        monkeypatch.chdir(tmp_path)

        plugin, _ = make_plugin()
        await plugin.add_sticker("cat", PNG)

        assert (tmp_path / "assets" / "icon.svg").read_text(encoding="utf-8") == "<svg/>"
        assert (stickers / ".gitkeep").is_file()
    run(scenario())


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits only")
def test_write_bit_is_restored_not_dropped(make_plugin, tmp_path, monkeypatch):
    async def scenario():
        make_read_only(tmp_path)
        monkeypatch.chdir(tmp_path)

        plugin, _ = make_plugin()
        await plugin.add_sticker("cat", PNG)

        mode = stat.S_IMODE((tmp_path / "assets" / "stickers").stat().st_mode)
        assert mode & stat.S_IWUSR, "the served directory must stay writable"
    run(scenario())
