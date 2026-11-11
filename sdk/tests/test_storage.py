from __future__ import annotations

import os

import pytest

from langbot_plugin.storage import collect_storage_directories, storage_total_bytes


def test_collect_storage_directories_counts_roots_and_details_once(tmp_path):
    root = tmp_path / "workspace"
    detail = root / ".mcp"
    detail.mkdir(parents=True)
    (root / "message.txt").write_bytes(b"abc")
    (detail / "cache.bin").write_bytes(b"12345")

    directories = collect_storage_directories(
        (
            ("workspace", root, "root", None),
            ("mcp", detail, "detail", "workspace"),
            ("missing", root / "missing", "detail", "workspace"),
        )
    )

    by_key = {item["key"]: item for item in directories}
    assert by_key["workspace"]["size_bytes"] == 8
    assert by_key["workspace"]["file_count"] == 2
    assert by_key["mcp"]["size_bytes"] == 5
    assert by_key["mcp"]["parent_key"] == "workspace"
    assert by_key["missing"]["exists"] is False
    assert storage_total_bytes(directories) == 8


def test_collect_storage_directories_does_not_follow_symlinks(tmp_path):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.bin").write_bytes(b"secret")
    link = root / "outside-link"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlinks are unavailable on this host")

    [result] = collect_storage_directories((("root", root, "root", None),))

    assert result["file_count"] == 1
    assert result["size_bytes"] != len(b"secret")
