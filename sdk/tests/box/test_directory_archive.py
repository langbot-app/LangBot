"""Validate bounded directory exports against real filesystem trees."""

from __future__ import annotations

import io
import inspect
import os
import stat
import subprocess
import sys
import zipfile

import pytest

from langbot_plugin.box.file_io import archive_workspace_directory
from langbot_plugin.box import file_io


def test_archive_preserves_bytes_empty_directories_and_executable_mode(tmp_path):
    source = tmp_path / "draft"
    source.mkdir()
    (source / "empty").mkdir()
    (source / "nested").mkdir()
    (source / "nested" / "data.bin").write_bytes(bytes(range(256)))
    executable = source / "run.py"
    executable.write_bytes(b"print('directory export')\n")
    executable.chmod(0o751)
    before = {p.relative_to(source): p.stat() for p in [source, *source.rglob("*")]}

    content = archive_workspace_directory(str(tmp_path), "draft", 4096)

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert set(archive.namelist()) == {
            "empty/",
            "nested/",
            "nested/data.bin",
            "run.py",
        }
        assert archive.read("nested/data.bin") == bytes(range(256))
        assert archive.read("run.py") == b"print('directory export')\n"
        assert archive.getinfo("run.py").external_attr >> 16 == stat.S_IFREG | 0o755
        assert (
            archive.getinfo("nested/data.bin").external_attr >> 16
            == stat.S_IFREG | 0o644
        )
        assert all(
            member.compress_type == zipfile.ZIP_STORED for member in archive.infolist()
        )
    assert set(before) == {p.relative_to(source) for p in [source, *source.rglob("*")]}
    for path, expected in before.items():
        current = (source / path).stat()
        assert (
            current.st_ino,
            current.st_size,
            current.st_mtime_ns,
            current.st_ctime_ns,
        ) == (
            expected.st_ino,
            expected.st_size,
            expected.st_mtime_ns,
            expected.st_ctime_ns,
        )


def test_archive_accepts_workspace_root_and_empty_tree(tmp_path):
    content = archive_workspace_directory(str(tmp_path), "", 22)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert archive.namelist() == []
    with pytest.raises(ValueError, match="size limit"):
        archive_workspace_directory(str(tmp_path), "", 21)


@pytest.mark.parametrize(
    "relative",
    [
        ".",
        "..",
        "../outside",
        "/outside",
        "a/../b",
        "a/./b",
        "a//b",
        "a/",
        "a\\b",
        "a\x00b",
    ],
)
def test_archive_rejects_noncanonical_relative_paths(tmp_path, relative):
    with pytest.raises(ValueError, match="inside the session workspace"):
        archive_workspace_directory(str(tmp_path), relative, 4096)


@pytest.mark.parametrize("kind", ["symlink", "directory_symlink", "hardlink", "fifo"])
def test_archive_rejects_links_and_special_files(tmp_path, kind):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.write_bytes(b"must not be exported")
    if kind == "symlink":
        (source / "entry").symlink_to(outside)
    elif kind == "directory_symlink":
        (source / "entry").symlink_to(tmp_path, target_is_directory=True)
    elif kind == "hardlink":
        os.link(outside, source / "entry")
    else:
        os.mkfifo(source / "entry")
    with pytest.raises(ValueError, match="link or special file"):
        archive_workspace_directory(str(tmp_path), "source", 4096)
    assert outside.read_bytes() == b"must not be exported"


def test_archive_does_not_follow_source_path_symlink(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "data").write_bytes(b"outside")
    (tmp_path / "source").symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        archive_workspace_directory(str(tmp_path), "source", 4096)


@pytest.mark.parametrize("kind", ["entry", "depth", "file", "expanded", "archive"])
def test_archive_enforces_tree_and_output_limits(tmp_path, kind):
    if kind == "entry":
        for index in range(513):
            (tmp_path / str(index)).touch()
    elif kind == "depth":
        parent = tmp_path
        for _ in range(17):
            parent /= "nested"
            parent.mkdir()
    else:
        count = 5 if kind == "expanded" else 2 if kind == "archive" else 1
        size = 16 * 1024 * 1024 + (1 if kind == "file" else 0)
        for index in range(count):
            with (tmp_path / str(index)).open("wb") as stream:
                stream.truncate(size)
    with pytest.raises(ValueError, match="limit"):
        archive_workspace_directory(str(tmp_path), "", 64 * 1024 * 1024)


def test_archive_rejects_a_file_changed_after_it_was_copied(tmp_path, monkeypatch):
    (tmp_path / "first").write_bytes(b"first")
    (tmp_path / "second").write_bytes(b"second")
    open_member = zipfile.ZipFile.open
    copied = []

    def mutate_after_copy(archive, member, mode="r", *args, **kwargs):
        if mode == "w":
            if copied:
                (tmp_path / copied[0]).write_bytes(b"changed after copying")
            copied.append(member.filename)
        return open_member(archive, member, mode, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "open", mutate_after_copy)
    with pytest.raises(ValueError, match="file changed"):
        archive_workspace_directory(str(tmp_path), "", 4096)


def test_archive_rejects_a_directory_changed_during_export(tmp_path, monkeypatch):
    (tmp_path / "file").write_bytes(b"source")
    close_archive = zipfile.ZipFile.close

    def mutate_tree(archive):
        if archive.fp is not None and archive.mode == "w":
            (tmp_path / "new-file").write_bytes(b"late addition")
        return close_archive(archive)

    monkeypatch.setattr(zipfile.ZipFile, "close", mutate_tree)
    with pytest.raises(ValueError, match="Directory changed"):
        archive_workspace_directory(str(tmp_path), "", 4096)


def test_interrupted_standalone_archive_leaves_only_original_files(tmp_path):
    original = tmp_path / "payload"
    original.write_bytes(b"keep original")
    script = (
        inspect.getsource(file_io)
        + "\noriginal_open = zipfile.ZipFile.open\n"
        + "def interrupt_read(archive, member, mode='r', *args, **kwargs):\n"
        + "    if mode == 'w':\n"
        + "        os._exit(91)\n"
        + "    return original_open(archive, member, mode, *args, **kwargs)\n"
        + "zipfile.ZipFile.open = interrupt_read\n"
        + f"archive_workspace_directory({str(tmp_path)!r}, '', 4096)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, timeout=10
    )
    assert result.returncode == 91, result.stderr
    assert list(tmp_path.iterdir()) == [original]
    assert original.read_bytes() == b"keep original"
