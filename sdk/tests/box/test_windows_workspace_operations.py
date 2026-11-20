import base64
import hashlib
import io
import json
import zipfile

import pytest

from langbot_plugin.box import windows_file_io as files
from langbot_plugin.box.windows_export import export


@pytest.mark.parametrize(
    "relative", ["../outside", "/outside", "dir/CON.txt", "NUL", "x:y"]
)
def test_invalid_windows_path(tmp_path, relative):
    root = tmp_path / "workspace"
    root.mkdir()
    with pytest.raises(ValueError):
        files.write(root, relative, b"bad")
    assert not (tmp_path / "outside").exists()


def test_symlink_parent_rejected(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="link"):
        files.write(root, "linked/new", b"bad")
    assert list(outside.iterdir()) == []


def test_transfer_archive_and_usage(tmp_path):
    path = "folder/input.bin"
    files.write(tmp_path, path, b"first")
    files.write(tmp_path, path, bytes(range(128)))
    assert files.read(tmp_path, path, 128) == bytes(range(128))
    with pytest.raises(ValueError, match="limit"):
        files.read(tmp_path, path, 127)
    assert files.usage(tmp_path, 128, 2) == (128, 2, False)
    assert files.usage(tmp_path, 128, 1) == (0, 2, True)
    archive = files.archive_directory(tmp_path, "", 1024)
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        assert zipped.namelist() == ["folder/", path]
        assert zipped.read(path) == bytes(range(128))
    with pytest.raises(ValueError, match="limit"):
        files.archive_directory(tmp_path, "", len(archive) - 1)


def test_owned_and_scoped_cleanup(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    info = root.stat()
    owner = root, info.st_dev, info.st_ino
    stale = root, info.st_dev, info.st_ino + 1
    for path in ("inbox/first/msg", "outbox/first/doc", "outbox/second/doc"):
        files.write(root, path, b"ok")
    with pytest.raises(ValueError, match="ownership changed"):
        files.clear(stale)
    with pytest.raises(ValueError, match="ownership changed"):
        files.remove_owned(stale, False)
    assert files.run_files(owner, "first")
    files.run_files(owner, "first", remove=True)
    assert not files.run_files(owner, "first")
    assert files.read(root, "outbox/second/doc", 2) == b"ok"
    files.clear(owner)
    assert list(root.iterdir()) == []
    files.remove_owned(owner, True)
    assert not root.exists()
    files.remove_owned(owner, False)


@pytest.fixture
def selected(tmp_path, monkeypatch):
    monkeypatch.setenv("LANGBOT_BOX_WORKSPACE", str(tmp_path))
    files.write(tmp_path, "outbox/run/sub/result", b"payload")
    return dict(
        paths=["/workspace/outbox/run/sub/result"],
        max_file_bytes=7,
        max_total_bytes=7,
        cleanup=None,
        snapshot_root=None,
    )


def test_selected_digest_controls_cleanup(tmp_path, selected):
    (path,) = selected["paths"]
    assert export("selected", selected) == [
        dict(name=path, b64=base64.b64encode(b"payload").decode())
    ]
    with pytest.raises(ValueError, match="changed after acceptance"):
        export("selected", dict(selected, cleanup={path: "wrong"}))
    assert files.read(tmp_path, "outbox/run/sub/result", 7) == b"payload"
    export(
        "selected",
        dict(selected, cleanup={path: hashlib.sha256(b"payload").hexdigest()}),
    )
    assert not (tmp_path / "outbox/run/sub/result").exists()


def test_snapshot_cleanup_checks_contents_and_identity(tmp_path, selected):
    root = "/workspace/.langbot-snapshots/run/.langbot-export-" + "a" * 32
    with pytest.raises(ValueError, match="Invalid export snapshot"):
        export("selected", dict(selected, snapshot_root="/workspace/outbox/run"))
    (item,) = export("selected", dict(selected, snapshot_root=root))
    snapshot = tmp_path / item["snapshot_path"].removeprefix("/workspace/")
    assert snapshot.read_bytes() == b"payload"
    assert item["sha256"] == hashlib.sha256(snapshot.read_bytes()).hexdigest()
    extra = snapshot.with_name("unexpected")
    extra.touch()
    with pytest.raises(ValueError, match="Unknown files"):
        export("cleanup_snapshot", root)
    extra.unlink()
    original = tmp_path / "original"
    snapshot.rename(original)
    snapshot.write_bytes(b"replacement")
    with pytest.raises(ValueError, match="changed; retained"):
        export("cleanup_snapshot", root)
    assert snapshot.read_bytes() == b"replacement"
    original.replace(snapshot)
    export("cleanup_snapshot", root)
    assert not snapshot.parent.exists()
    assert export("cleanup_snapshot", root) == []


def test_outbox_read_list_limits_and_clear(tmp_path, selected, capsys):
    settings = dict(
        outbox="outbox", query="run", max_file_bytes=7, max_total_bytes=7, max_files=1
    )
    assert export("outbox", dict(settings, operation="list")) == [
        {"name": "sub/result"}
    ]
    (entry,) = export("outbox", dict(settings, operation="read"))
    assert base64.b64decode(entry["b64"]) == b"payload"
    with pytest.raises(SystemExit) as failure:
        export("outbox", dict(settings, operation="read", max_total_bytes=6))
    assert failure.value.code == 73
    assert (
        json.loads(capsys.readouterr().err.split(":", 1)[1])["kind"]
        == "collection_bytes"
    )
    files.write(tmp_path, "outbox/other/result", b"keep")
    assert export("outbox", dict(settings, operation="clear")) == []
    assert list((tmp_path / "outbox/run").iterdir()) == []
    assert files.read(tmp_path, "outbox/other/result", 4) == b"keep"
