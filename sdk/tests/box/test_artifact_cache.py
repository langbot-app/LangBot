"""Exercise immutable cache publication, pins and GC against real files."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import stat
import zipfile

import pytest

from langbot_plugin.box.artifact_cache import ArtifactCache
from langbot_plugin.box.errors import BoxCapacityExceededError
from langbot_plugin.box.models import BoxArtifactDescriptor
from langbot_plugin.entities.io.context import ActionContext


_CONTEXT = ActionContext(
    instance_uuid="instance-a", workspace_uuid="workspace-a", placement_generation=1
)


@pytest.fixture
def publication():
    def create(readme=b"Immutable reference bytes.\n"):
        files = {"README.md": readme, "scripts/run.sh": b"#!/bin/sh\necho immutable\n"}
        manifest = {
            "algorithm": "sha256-tree-v1",
            "files": [
                {
                    "path": path,
                    "size": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "executable": path.endswith(".sh"),
                }
                for path, body in sorted(files.items())
            ],
            "total_bytes": sum(map(len, files.values())),
        }
        canonical = json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            for path, body in files.items():
                member = zipfile.ZipInfo(path)
                member.external_attr = (
                    stat.S_IFREG | (0o755 if path.endswith(".sh") else 0o644)
                ) << 16
                archive.writestr(member, body)
        content = output.getvalue()
        descriptor = BoxArtifactDescriptor(
            content_digest="sha256:" + hashlib.sha256(canonical).hexdigest(),
            manifest=manifest,
            archive_size=len(content),
            archive_sha256=hashlib.sha256(content).hexdigest(),
        )
        return descriptor, content, files

    return create


def test_publish_is_verified_read_only_and_workspace_scoped(tmp_path, publication):
    descriptor, content, files = publication()
    cache = ArtifactCache(tmp_path / "cache")
    cache.prepare(_CONTEXT, descriptor, content)

    assert cache.probe(_CONTEXT, descriptor)
    foreign = _CONTEXT.model_copy(update={"workspace_uuid": "workspace-b"})
    assert not cache.probe(foreign, descriptor)
    with pytest.raises(ValueError, match="not prepared"):
        cache.acquire(foreign, [descriptor.content_digest], "foreign-session")
    (mount,) = cache.acquire(_CONTEXT, [descriptor.content_digest], "session")
    assert mount.mount_path == "/opt/langbot-artifacts/" + descriptor.content_digest[7:]
    for path, expected in files.items():
        actual = Path(mount.host_path, path)
        assert actual.read_bytes() == expected
        assert stat.S_IMODE(actual.stat().st_mode) == (
            0o555 if path.endswith(".sh") else 0o444
        )
    assert stat.S_IMODE(Path(mount.host_path).stat().st_mode) == 0o555
    cache.release("session")


@pytest.mark.parametrize("capacity", ["bytes", "entries"])
def test_pins_block_capacity_and_idle_gc_then_allow_reconstruction(
    tmp_path, publication, capacity
):
    first, first_bytes, files = publication(b"a" * 4096)
    second, second_bytes, _ = publication(b"b" * 4096)
    cache = ArtifactCache(
        tmp_path / "cache",
        max_bytes=8192 if capacity == "bytes" else 256 * 1024 * 1024,
        max_entries=1 if capacity == "entries" else 256,
        idle_ttl_sec=0,
    )
    cache.prepare(_CONTEXT, first, first_bytes)
    cache.acquire(_CONTEXT, [first.content_digest], "live-session")

    cache.reap()
    assert cache.probe(_CONTEXT, first)
    with pytest.raises(BoxCapacityExceededError, match="pinned"):
        cache.prepare(_CONTEXT, second, second_bytes)
    assert cache.probe(_CONTEXT, first)

    cache.release("live-session")
    cache.reap()
    assert not cache.probe(_CONTEXT, first)
    cache.prepare(_CONTEXT, second, second_bytes)
    assert cache.probe(_CONTEXT, second)
    cache.prepare(_CONTEXT, first, first_bytes)
    (mount,) = cache.acquire(_CONTEXT, [first.content_digest], "rebuilt-session")
    assert Path(mount.host_path, "README.md").read_bytes() == files["README.md"]
    cache.release("rebuilt-session")


def test_restart_reaps_clean_entries_but_preserves_crash_pins(tmp_path, publication):
    descriptor, content, _ = publication()
    root = tmp_path / "cache"
    before = ArtifactCache(root, idle_ttl_sec=0)
    before.prepare(_CONTEXT, descriptor, content)
    clean_restart = ArtifactCache(root, idle_ttl_sec=0)
    clean_restart.reap()
    assert not clean_restart.probe(_CONTEXT, descriptor)

    clean_restart.prepare(_CONTEXT, descriptor, content)
    clean_restart.acquire(_CONTEXT, [descriptor.content_digest], "crashed-session")
    crash_restart = ArtifactCache(root, idle_ttl_sec=0)
    crash_restart.acquire(_CONTEXT, [descriptor.content_digest], "new-session")
    crash_restart.release("new-session")
    crash_restart.reap()
    assert crash_restart.probe(_CONTEXT, descriptor)


@pytest.mark.parametrize("invalid", ["broken-zip", "symlink"])
def test_invalid_archive_cleans_staging_and_can_retry(tmp_path, publication, invalid):
    descriptor, content, files = publication()
    if invalid == "broken-zip":
        invalid_content = b"not a ZIP archive"
    else:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            for path, body in files.items():
                member = zipfile.ZipInfo(path)
                member.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(member, body)
        invalid_content = output.getvalue()
    invalid_descriptor = descriptor.model_copy(
        update={
            "archive_size": len(invalid_content),
            "archive_sha256": hashlib.sha256(invalid_content).hexdigest(),
        }
    )
    root = tmp_path / "cache"
    cache = ArtifactCache(root)

    with pytest.raises(ValueError):
        cache.prepare(_CONTEXT, invalid_descriptor, invalid_content)

    assert list(root.iterdir()) == []
    assert not cache.probe(_CONTEXT, descriptor)
    cache.prepare(_CONTEXT, descriptor, content)
    assert cache.probe(_CONTEXT, descriptor)
