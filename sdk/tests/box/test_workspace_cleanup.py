"""Check identity and no-follow boundaries of stopped-workspace cleanup."""

from __future__ import annotations

from contextlib import nullcontext
import os
import stat
from types import SimpleNamespace

import pytest

from langbot_plugin.box.file_io import (
    clear_workspace_directory,
    remove_owned_workspace,
)


def test_clear_preserves_root_and_does_not_follow_links(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    private = root / "private"
    private.mkdir(mode=0o700)
    (private / "data").write_bytes(b"private")
    outside = tmp_path / "outside"
    outside.mkdir()
    protected = outside / "protected"
    protected.write_bytes(b"must remain")
    (root / "linked-dir").symlink_to(outside, target_is_directory=True)
    (root / "linked-file").symlink_to(protected)
    (root / "missing-link").symlink_to(outside / "missing")
    os.link(protected, root / "hard-link")
    info = root.stat()

    clear_workspace_directory(str(root), info.st_dev, info.st_ino)

    assert root.is_dir()
    assert (root.stat().st_dev, root.stat().st_ino) == (info.st_dev, info.st_ino)
    assert list(root.iterdir()) == []
    assert protected.read_bytes() == b"must remain"


def test_clear_rejects_wrong_root_identity_and_symlink(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    original = root / "data"
    original.write_bytes(b"keep")
    info = root.stat()
    with pytest.raises(ValueError, match="ownership changed"):
        clear_workspace_directory(str(root), info.st_dev, info.st_ino + 1)
    link = tmp_path / "link"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(OSError):
        clear_workspace_directory(str(link), info.st_dev, info.st_ino)
    assert original.read_bytes() == b"keep"


def test_clear_rejects_foreign_directory_device(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()
    child = root / "other-device"
    child.mkdir()
    original = child / "keep"
    original.write_bytes(b"foreign device")
    info = root.stat()
    scan = os.scandir

    def scan_other_device(descriptor):
        iterator = scan(descriptor)

        class OtherDevice:
            def __enter__(self):
                return iter(self)

            def __exit__(self, *_args):
                iterator.close()

            def __iter__(self):
                for entry in iterator:
                    data = entry.stat(follow_symlinks=False)
                    yield SimpleNamespace(
                        name=entry.name,
                        stat=lambda **_kwargs: SimpleNamespace(
                            st_mode=data.st_mode, st_dev=info.st_dev + 1
                        ),
                    )

        return OtherDevice()

    monkeypatch.setattr(os, "scandir", scan_other_device)
    with pytest.raises(ValueError, match="cross a filesystem"):
        clear_workspace_directory(str(root), info.st_dev, info.st_ino)
    assert original.read_bytes() == b"foreign device"


def test_clear_stops_at_the_entry_limit(tmp_path, monkeypatch):
    info = tmp_path.stat()
    entries = (
        SimpleNamespace(
            name=str(index),
            stat=lambda **_kwargs: SimpleNamespace(st_mode=stat.S_IFREG),
        )
        for index in range(100_001)
    )
    removed = []
    monkeypatch.setattr(os, "scandir", lambda _descriptor: nullcontext(entries))
    monkeypatch.setattr(os, "unlink", lambda name, **_kwargs: removed.append(name))
    with pytest.raises(ValueError, match="entry limit"):
        clear_workspace_directory(str(tmp_path), info.st_dev, info.st_ino)
    assert len(removed) == 100_000


@pytest.mark.parametrize("empty_only", [False, True])
def test_remove_rejects_replacement_root_and_is_idempotent(tmp_path, empty_only):
    root = tmp_path / "workspace"
    root.mkdir()
    info = root.stat()
    saved = tmp_path / "saved"
    root.rename(saved)
    root.mkdir()
    (root / "replacement").write_bytes(b"keep")

    with pytest.raises(ValueError, match="ownership changed"):
        remove_owned_workspace(
            (str(root), info.st_dev, info.st_ino), empty_only=empty_only
        )
    assert (root / "replacement").read_bytes() == b"keep"

    remove_owned_workspace(
        (str(saved), info.st_dev, info.st_ino), empty_only=empty_only
    )
    assert not saved.exists()
    remove_owned_workspace(
        (str(saved), info.st_dev, info.st_ino), empty_only=empty_only
    )


def test_empty_only_does_not_traverse_or_change_a_nonempty_root(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    protected = root / "keep"
    protected.write_bytes(b"keep")
    info = root.stat()
    with pytest.raises(OSError):
        remove_owned_workspace((str(root), info.st_dev, info.st_ino), empty_only=True)
    assert protected.read_bytes() == b"keep"
    protected.unlink()
    root.chmod(0)
    remove_owned_workspace((str(root), info.st_dev, info.st_ino), empty_only=True)
    assert not root.exists()
