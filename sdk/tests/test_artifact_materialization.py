import json

import pytest

from langbot_plugin.artifact import build_tree_manifest, materialize_tree


def publication(tmp_path, name, files):
    root = tmp_path / name
    root.mkdir()
    for path, body in files.items():
        (root / path).write_text(body)
    digest, manifest = build_tree_manifest(
        str(root), max_files=10, max_total_bytes=1024
    )
    manifest_path = tmp_path / (name + ".json")
    manifest_path.write_text(json.dumps(manifest))
    return str(root), str(manifest_path), digest


def test_publication_is_atomic_and_old_revisions_survive(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    first = publication(tmp_path, "v1", {"value": "one", "removed": "old"})
    second = publication(tmp_path, "v2", {"value": "two"})
    one = materialize_tree(*first, str(cache))
    two = materialize_tree(*second, str(cache))
    from pathlib import Path

    assert (Path(one) / "value").read_text() == "one"
    assert (Path(two) / "value").read_text() == "two"
    assert not (Path(two) / "removed").exists()
    assert materialize_tree(*first, str(cache)) == one


def test_changed_or_partial_source_never_becomes_visible(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    source = publication(tmp_path, "broken", {"first": "one", "second": "two"})
    (tmp_path / "broken" / "second").write_text("corrupted")
    with pytest.raises(ValueError, match="changed"):
        materialize_tree(*source, str(cache))
    assert list(cache.iterdir()) == []
    assert not list(tmp_path.glob("langbot-artifact-stage-*"))


@pytest.mark.parametrize(
    "mode,revision,path",
    [
        ("rw", "sha256:" + "1" * 64, "/opt/langbot-artifacts/" + "1" * 64),
        ("ro", "sha256:" + "1" * 64, "/opt/langbot-artifacts/" + "2" * 64),
        ("ro", None, "/opt/langbot-artifacts"),
    ],
)
def test_reserved_artifact_paths_require_exact_immutable_identity(mode, revision, path):
    from langbot_plugin.box.models import BoxMountSpec

    with pytest.raises(ValueError):
        BoxMountSpec(
            host_path="/tmp/source",
            mount_path=path,
            mode=mode,
            content_digest=revision,
            manifest_path="/tmp/manifest.json",
        )


def test_artifact_cache_rejects_wrong_digest_and_capacity_exhaustion(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    source = publication(tmp_path, "package", {"value": "expected"})
    with pytest.raises(ValueError, match="content_digest"):
        materialize_tree(source[0], source[1], "sha256:" + "0" * 64, str(cache))
    for index in range(256):
        (cache / str(index)).mkdir()
    with pytest.raises(ValueError, match="cache limit"):
        materialize_tree(*source, str(cache))
