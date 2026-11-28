from __future__ import annotations

import hashlib
import io
import stat
import zipfile
from contextlib import nullcontext

import pytest

from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.runtime.plugin import artifact as artifact_module
from langbot_plugin.runtime.plugin.artifact import PluginArtifactStore


def _plugin_package(*, body: str = "VALUE = 1", extra_manifest: str = "") -> bytes:
    manifest = f"""
apiVersion: v1
kind: Plugin
metadata:
  author: tester
  name: demo
  version: 1.0.0
spec:
  worker:
    max_cpus: 99
{extra_manifest}
"""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("manifest.yaml", manifest)
        archive.writestr("main.py", body)
        archive.writestr(".env", "FORGED_RUNTIME_SECRET=yes")
    return output.getvalue()


def _binding(installation_uuid: str, digest: str) -> InstallationBinding:
    return InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid=f"workspace-{installation_uuid}",
        placement_generation=1,
        installation_uuid=installation_uuid,
        runtime_revision=1,
        artifact_digest=digest,
    )


def test_same_digest_shares_read_only_code_but_not_writable_paths(tmp_path):
    package = _plugin_package()
    digest = hashlib.sha256(package).hexdigest()
    store = PluginArtifactStore(tmp_path / "plugin-runtime")

    artifact_a = store.install_package(package, digest)
    artifact_b = store.install_package(package, digest)
    paths_a = store.ensure_installation_paths(_binding("installation-a", digest))
    paths_b = store.ensure_installation_paths(_binding("installation-b", digest))

    assert artifact_a.code_path == artifact_b.code_path
    assert stat.S_IMODE(artifact_a.code_path.stat().st_mode) == 0o555
    assert stat.S_IMODE((artifact_a.code_path / "main.py").stat().st_mode) == 0o444
    assert paths_a.home_path != paths_b.home_path
    assert paths_a.tmp_path != paths_b.tmp_path
    assert paths_a.data_path != paths_b.data_path
    assert paths_a.home_path.is_dir() and paths_b.home_path.is_dir()


def test_different_digest_never_shares_artifact_path(tmp_path):
    package_a = _plugin_package(body="VALUE = 1")
    package_b = _plugin_package(body="VALUE = 2")
    digest_a = hashlib.sha256(package_a).hexdigest()
    digest_b = hashlib.sha256(package_b).hexdigest()
    store = PluginArtifactStore(tmp_path / "plugin-runtime")

    artifact_a = store.install_package(package_a, digest_a)
    artifact_b = store.install_package(package_b, digest_b)

    assert digest_a != digest_b
    assert artifact_a.code_path != artifact_b.code_path
    assert artifact_a.code_path.parent.name == digest_a
    assert artifact_b.code_path.parent.name == digest_b


def test_artifact_digest_mismatch_and_zip_slip_fail_closed(tmp_path):
    package = _plugin_package()
    store = PluginArtifactStore(tmp_path / "plugin-runtime")

    with pytest.raises(ValueError, match="digest mismatch"):
        store.install_package(package, "0" * 64)

    malicious = io.BytesIO()
    with zipfile.ZipFile(malicious, "w") as archive:
        archive.writestr("../escape", "bad")
        archive.writestr("manifest.yaml", "kind: Plugin")
    malicious_package = malicious.getvalue()
    with pytest.raises(ValueError, match="unsafe path"):
        store.install_package(
            malicious_package,
            hashlib.sha256(malicious_package).hexdigest(),
        )


def _package_with_members(
    members: list[tuple[str | zipfile.ZipInfo, bytes]],
    *,
    compression: int = zipfile.ZIP_STORED,
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        archive.writestr(
            "manifest.yaml",
            "kind: Plugin\nmetadata:\n  author: tester\n  name: demo\n  version: 1.0.0\n",
        )
        for name, body in members:
            archive.writestr(name, body)
    return output.getvalue()


def _install_untrusted_package(tmp_path, package: bytes) -> None:
    PluginArtifactStore(tmp_path / "plugin-runtime").install_package(
        package,
        hashlib.sha256(package).hexdigest(),
    )


def test_artifact_rejects_entry_count_per_file_and_total_limits(tmp_path, monkeypatch):
    monkeypatch.setattr(artifact_module, "_MAX_ARTIFACT_ENTRIES", 2)
    with pytest.raises(ValueError, match="too many entries"):
        _install_untrusted_package(
            tmp_path,
            _package_with_members([("one.py", b"1"), ("two.py", b"2")]),
        )

    monkeypatch.setattr(artifact_module, "_MAX_ARTIFACT_ENTRIES", 512)
    monkeypatch.setattr(
        artifact_module,
        "_MAX_ARTIFACT_ENTRY_UNCOMPRESSED_BYTES",
        4,
    )
    with pytest.raises(ValueError, match="entry exceeds the uncompressed size"):
        _install_untrusted_package(
            tmp_path,
            _package_with_members([("large.py", b"12345")]),
        )

    monkeypatch.setattr(
        artifact_module,
        "_MAX_ARTIFACT_ENTRY_UNCOMPRESSED_BYTES",
        1024,
    )
    monkeypatch.setattr(
        artifact_module,
        "_MAX_ARTIFACT_TOTAL_UNCOMPRESSED_BYTES",
        90,
    )
    with pytest.raises(ValueError, match="total uncompressed size"):
        _install_untrusted_package(
            tmp_path,
            _package_with_members([("one.py", b"1" * 32), ("two.py", b"2" * 32)]),
        )


def test_artifact_rejects_compression_bombs(tmp_path, monkeypatch):
    monkeypatch.setattr(artifact_module, "_MAX_ARTIFACT_COMPRESSION_RATIO", 2.0)
    package = _package_with_members(
        [("compressed.py", b"a" * 4096)],
        compression=zipfile.ZIP_DEFLATED,
    )

    with pytest.raises(ValueError, match="compression ratio"):
        _install_untrusted_package(tmp_path, package)


def test_artifact_rejects_oversized_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(artifact_module, "_MAX_ARTIFACT_MANIFEST_BYTES", 128)
    manifest = (
        b"kind: Plugin\n"
        b"metadata:\n"
        b"  author: tester\n"
        b"  name: demo\n"
        b"  version: 1.0.0\n" + b"# padding\n" * 16
    )
    package_buffer = io.BytesIO()
    with zipfile.ZipFile(package_buffer, "w") as archive:
        archive.writestr("manifest.yaml", manifest)
        archive.writestr("main.py", b"VALUE = 1")

    with pytest.raises(ValueError, match="manifest.yaml exceeds the size limit"):
        _install_untrusted_package(tmp_path, package_buffer.getvalue())

    assert not list((tmp_path / "plugin-runtime" / "artifacts" / "sha256").glob("*"))


@pytest.mark.parametrize("file_type", [stat.S_IFLNK, stat.S_IFIFO, stat.S_IFDIR])
def test_artifact_rejects_links_and_nonregular_entries(tmp_path, file_type):
    unsafe = zipfile.ZipInfo("unsafe-entry")
    unsafe.create_system = 3
    unsafe.external_attr = (file_type | 0o777) << 16
    package = _package_with_members([(unsafe, b"target")])

    expected = "symbolic links" if file_type == stat.S_IFLNK else "non-regular entry"
    with pytest.raises(ValueError, match=expected):
        _install_untrusted_package(tmp_path, package)


def test_artifact_rejects_duplicate_and_conflicting_paths(tmp_path):
    with pytest.warns(UserWarning, match="Duplicate name"):
        duplicate = _package_with_members([("same.py", b"1"), ("same.py", b"2")])
    with pytest.raises(ValueError, match="duplicate path"):
        _install_untrusted_package(tmp_path, duplicate)

    conflict = _package_with_members([("parent", b"file"), ("parent/child", b"child")])
    with pytest.raises(ValueError, match="conflicts with a file"):
        _install_untrusted_package(tmp_path, conflict)


def test_failed_artifact_extraction_removes_atomic_staging_tree(tmp_path):
    package = _package_with_members([("../escape.py", b"bad")])
    store = PluginArtifactStore(tmp_path / "plugin-runtime")

    with pytest.raises(ValueError, match="unsafe path"):
        store.install_package(package, hashlib.sha256(package).hexdigest())

    assert not list(store.artifacts_path.glob("*"))


def test_artifact_counts_actual_streamed_bytes(tmp_path, monkeypatch):
    class FakeInfo:
        filename = "main.py"
        external_attr = 0
        file_size = 1
        compress_size = 1

        @staticmethod
        def is_dir() -> bool:
            return False

    class FakeArchive:
        @staticmethod
        def __enter__():
            return FakeArchive()

        @staticmethod
        def __exit__(*args):
            return None

        @staticmethod
        def infolist():
            return [FakeInfo()]

        @staticmethod
        def open(_info, _mode):
            return nullcontext(io.BytesIO(b"actual-bytes"))

    monkeypatch.setattr(
        artifact_module.zipfile, "ZipFile", lambda *_args, **_kwargs: FakeArchive()
    )
    monkeypatch.setattr(
        artifact_module,
        "_MAX_ARTIFACT_ENTRY_UNCOMPRESSED_BYTES",
        4,
    )

    with pytest.raises(ValueError, match="entry exceeds the uncompressed size"):
        PluginArtifactStore._extract_verified_zip(b"fake", tmp_path / "destination")
    assert not (tmp_path / "destination" / "main.py").exists()
