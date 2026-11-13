"""Runtime-owned immutable artifact trees; authorization belongs to the caller."""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import io
import json
import math
import os
import re
import stat
import threading
import time
import uuid
import zipfile
import zlib
from typing import TYPE_CHECKING

from ..artifact import build_tree_manifest, validate_tree_manifest
from ..entities.io.context import ActionContext
from ..workspace import workspace_namespace
from .errors import BoxCapacityExceededError
from .file_io import _parent_directory
from .models import ARTIFACT_MOUNT_ROOT, BoxHostMountMode, BoxMountSpec

if TYPE_CHECKING:
    from .models import BoxArtifactDescriptor


_MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
_MAX_TREE_BYTES = 256 * 1024 * 1024
_MAX_METADATA_BYTES = 4 * 1024 * 1024
_MAX_TREE_NODES = 10_000
_SCOPE = re.compile(r"ws-[0-9a-f]{24}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_STAGING = re.compile(r"\.langbot-artifact-stage-[0-9a-f]{32}\Z")
_STATE_STAGING = re.compile(r"\.langbot-artifact-state-[0-9a-f]{32}\.tmp\Z")
_DIR_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _json_bytes(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


@dataclasses.dataclass
class _Entry:
    namespace: str
    descriptor: dict
    path: str
    size: int
    identity: tuple[int, int]
    last_used: float
    owners: set[str] = dataclasses.field(default_factory=set)
    protected: bool = False
    crash_protected: bool = False

    @property
    def key(self) -> tuple[str, str]:
        return self.namespace, self.descriptor["content_digest"]


class ArtifactCache:
    """Synchronize publication, session pins and eviction in one private root.

    The Runtime must validate authorization and generation even on cache hits.
    Persisted pin markers protect crash-surviving mounts conservatively. Only
    offline maintenance may reclaim a crash-protected tree after its backend
    consumers have been retired.
    """

    def __init__(
        self, root, *, max_bytes=256 * 1024 * 1024, idle_ttl_sec=300, max_entries=256
    ):
        if (
            not all(
                hasattr(os, name)
                for name in ("O_NOFOLLOW", "O_DIRECTORY", "geteuid", "fchmod")
            )
            or os.open not in os.supports_dir_fd
        ):
            raise ValueError(
                "Artifact cache requires POSIX descriptor-relative file IO"
            )
        for name, value in (("max_bytes", max_bytes), ("max_entries", max_entries)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if (
            isinstance(idle_ttl_sec, bool)
            or not isinstance(idle_ttl_sec, (int, float))
            or not math.isfinite(idle_ttl_sec)
            or idle_ttl_sec < 0
        ):
            raise ValueError("idle_ttl_sec must be finite and non-negative")
        self.root = os.path.abspath(os.path.expanduser(os.fspath(root)))
        self.max_bytes = max_bytes
        self.idle_ttl_sec = idle_ttl_sec
        self.max_entries = max_entries
        self._lock = threading.RLock()
        self._entries: dict[tuple[str, str], _Entry] = {}
        self._owners: dict[str, set[tuple[str, str]]] = {}
        with _parent_directory(self.root, "cache", create=True) as (root_fd, _):
            root_info = os.fstat(root_fd)
            if (
                root_info.st_uid != os.geteuid()
                or stat.S_IMODE(root_info.st_mode) & 0o077
            ):
                raise ValueError(
                    "Artifact cache root must be private and Runtime-owned"
                )
            self._restore_index(root_fd)

    @staticmethod
    def _descriptor(descriptor: BoxArtifactDescriptor) -> dict:
        data = json.loads(_json_bytes(descriptor.model_dump(mode="json")))
        if set(data) != {
            "content_digest",
            "manifest",
            "archive_size",
            "archive_sha256",
        }:
            raise ValueError("Invalid artifact descriptor")
        digest, manifest = validate_tree_manifest(
            data["manifest"], max_files=2048, max_total_bytes=_MAX_TREE_BYTES
        )
        if digest != data["content_digest"]:
            raise ValueError("Artifact manifest does not match content_digest")
        if len(_json_bytes(manifest)) > _MAX_METADATA_BYTES:
            raise ValueError("Artifact manifest is too large")
        size = data["archive_size"]
        if (
            isinstance(size, bool)
            or not isinstance(size, int)
            or not 0 <= size <= _MAX_ARCHIVE_BYTES
        ):
            raise ValueError("Artifact archive exceeds its size limit")
        if not isinstance(data["archive_sha256"], str) or not _DIGEST.fullmatch(
            data["archive_sha256"]
        ):
            raise ValueError("Invalid artifact archive digest")
        ArtifactCache._package_paths(manifest)
        return data

    @staticmethod
    def _package_paths(manifest: dict) -> set[str]:
        paths = {"package", "manifest.json", "descriptor.json"}
        for entry in manifest["files"]:
            parts = entry["path"].split("/")
            if len(parts) > 128 or len(entry["path"].encode("utf-8")) > 4096:
                raise ValueError("Artifact path exceeds its depth or length limit")
            for count in range(1, len(parts) + 1):
                paths.add("package/" + "/".join(parts[:count]))
                if len(paths) > _MAX_TREE_NODES:
                    raise ValueError("Artifact contains too many filesystem entries")
        return paths

    @staticmethod
    def _read_json(directory: int, name: str) -> dict:
        descriptor = os.open(
            name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
        )
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_size > _MAX_METADATA_BYTES + 4096
            ):
                raise ValueError("Invalid artifact cache metadata file")
            body = stream.read(_MAX_METADATA_BYTES + 4097)
        if len(body) > _MAX_METADATA_BYTES + 4096:
            raise ValueError("Artifact cache metadata is too large")
        result = json.loads(body)
        if not isinstance(result, dict):
            raise ValueError("Invalid artifact cache metadata")
        return result

    @staticmethod
    def _write_file(directory: int, name: str, body: bytes) -> None:
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory,
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, 0o444, dir_fd=directory, follow_symlinks=False)

    @staticmethod
    @contextlib.contextmanager
    def _directory(parent: int, name: str, *, create=False):
        if create:
            try:
                os.mkdir(name, 0o700, dir_fd=parent)
            except FileExistsError:
                pass
        descriptor = os.open(name, _DIR_FLAGS, dir_fd=parent)
        try:
            info = os.fstat(descriptor)
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o022:
                raise ValueError(
                    "Artifact cache directories must be Runtime-owned and not publicly writable"
                )
            yield descriptor
        finally:
            os.close(descriptor)

    @staticmethod
    def _nodes(directory: int, prefix="", result=None) -> set[str]:
        result = set() if result is None else result
        for name in os.listdir(directory):
            path = prefix + name
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
            result.add(path)
            if len(result) > _MAX_TREE_NODES:
                raise ValueError("Artifact cache tree contains too many entries")
            if stat.S_ISDIR(info.st_mode):
                with ArtifactCache._directory(directory, name) as child:
                    ArtifactCache._nodes(child, path + "/", result)
            elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("Artifact cache requires regular files without links")
        return result

    @staticmethod
    def _remove_contents(directory: int) -> None:
        os.fchmod(directory, 0o700)
        for name in os.listdir(directory):
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                with ArtifactCache._directory(directory, name) as child:
                    ArtifactCache._remove_contents(child)
                os.rmdir(name, dir_fd=directory)
            elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                os.unlink(name, dir_fd=directory)
            else:
                raise ValueError("Refusing to remove unsafe artifact cache contents")

    def _validate_entry(self, entry: _Entry) -> None:
        digest = entry.descriptor["content_digest"]
        with _parent_directory(self.root, "cache", create=False) as (root_fd, _):
            with (
                self._directory(root_fd, entry.namespace) as scope_fd,
                self._directory(scope_fd, digest[7:]) as entry_fd,
            ):
                info = os.fstat(entry_fd)
                if (info.st_dev, info.st_ino) != entry.identity:
                    raise ValueError("Artifact cache entry identity changed")
                if self._nodes(entry_fd) != self._package_paths(
                    entry.descriptor["manifest"]
                ):
                    raise ValueError("Artifact cache tree contains unexpected entries")
                envelope = self._read_json(entry_fd, "descriptor.json")
                if envelope != {
                    "format": 1,
                    "namespace": entry.namespace,
                    "descriptor": entry.descriptor,
                    "protected": entry.protected,
                }:
                    raise ValueError("Artifact cache descriptor changed")
                if (
                    self._read_json(entry_fd, "manifest.json")
                    != entry.descriptor["manifest"]
                ):
                    raise ValueError("Artifact cache manifest changed")
                with self._directory(entry_fd, "package"):
                    actual = build_tree_manifest(
                        os.path.join(entry.path, "package"),
                        max_files=2048,
                        max_total_bytes=_MAX_TREE_BYTES,
                    )
                if actual != (digest, entry.descriptor["manifest"]):
                    raise ValueError("Artifact cache tree failed digest verification")

    def _restore_index(self, root_fd: int) -> None:
        from .models import BoxArtifactDescriptor

        for namespace in os.listdir(root_fd):
            if not _SCOPE.fullmatch(namespace):
                continue
            with self._directory(root_fd, namespace) as scope_fd:
                for name in os.listdir(scope_fd):
                    if not _DIGEST.fullmatch(name):
                        continue
                    with self._directory(scope_fd, name) as entry_fd:
                        envelope = self._read_json(entry_fd, "descriptor.json")
                        if (
                            set(envelope)
                            != {"format", "namespace", "descriptor", "protected"}
                            or envelope["format"] != 1
                            or envelope["namespace"] != namespace
                            or not isinstance(envelope["protected"], bool)
                        ):
                            raise ValueError(
                                "Invalid persisted artifact cache identity"
                            )
                        data = self._descriptor(
                            BoxArtifactDescriptor.model_validate(envelope["descriptor"])
                        )
                        if data["content_digest"] != "sha256:" + name:
                            raise ValueError("Persisted artifact cache digest changed")
                        info = os.fstat(entry_fd)
                        entry = _Entry(
                            namespace,
                            data,
                            os.path.join(self.root, namespace, name),
                            self._stored_size(namespace, data),
                            (info.st_dev, info.st_ino),
                            time.monotonic() - self.idle_ttl_sec,
                            protected=envelope["protected"],
                            crash_protected=envelope["protected"],
                        )
                    self._validate_entry(entry)
                    self._entries[entry.key] = entry

    @staticmethod
    def _stored_size(namespace: str, data: dict) -> int:
        envelope = {
            "format": 1,
            "namespace": namespace,
            "descriptor": data,
            "protected": False,
        }
        return (
            data["manifest"]["total_bytes"]
            + len(_json_bytes(data["manifest"]))
            + len(_json_bytes(envelope))
        )

    def _evict(self, entry: _Entry) -> None:
        if entry.owners or entry.protected or entry.crash_protected:
            raise ValueError("Cannot evict an artifact pinned by a Box session")
        with _parent_directory(self.root, "cache", create=False) as (root_fd, _):
            with self._directory(root_fd, entry.namespace) as scope_fd:
                with self._directory(
                    scope_fd, entry.descriptor["content_digest"][7:]
                ) as entry_fd:
                    info = os.fstat(entry_fd)
                    if (info.st_dev, info.st_ino) != entry.identity or self._nodes(
                        entry_fd
                    ) != self._package_paths(entry.descriptor["manifest"]):
                        raise ValueError(
                            "Refusing to remove an unknown artifact cache tree"
                        )
                    self._remove_contents(entry_fd)
                os.rmdir(entry.descriptor["content_digest"][7:], dir_fd=scope_fd)
                self._entries.pop(entry.key, None)
                os.fsync(scope_fd)
                if not os.listdir(scope_fd):
                    os.rmdir(entry.namespace, dir_fd=root_fd)

    def _reap(self) -> None:
        now = time.monotonic()
        for entry in list(self._entries.values()):
            if (
                not entry.owners
                and not entry.protected
                and not entry.crash_protected
                and now - entry.last_used >= self.idle_ttl_sec
            ):
                self._evict(entry)

    def _make_room(self, size: int) -> None:
        if size > self.max_bytes:
            raise BoxCapacityExceededError(
                "Artifact exceeds the Runtime cache capacity"
            )
        self._reap()
        while (
            len(self._entries) >= self.max_entries
            or sum(entry.size for entry in self._entries.values()) + size
            > self.max_bytes
        ):
            candidates = [
                entry
                for entry in self._entries.values()
                if not entry.owners
                and not entry.protected
                and not entry.crash_protected
            ]
            if not candidates:
                raise BoxCapacityExceededError(
                    "Runtime artifact cache is full of pinned revisions"
                )
            self._evict(min(candidates, key=lambda entry: entry.last_used))

    def probe(self, context: ActionContext, descriptor: BoxArtifactDescriptor) -> bool:
        with self._lock:
            data = self._descriptor(descriptor)
            key = (
                workspace_namespace(context.instance_uuid, context.workspace_uuid),
                data["content_digest"],
            )
            entry = self._entries.get(key)
            if entry is None or entry.descriptor["manifest"] != data["manifest"]:
                return False
            try:
                self._validate_entry(entry)
            except (OSError, ValueError):
                return False
            entry.last_used = time.monotonic()
            return True

    def prepare(
        self, context: ActionContext, descriptor: BoxArtifactDescriptor, archive: bytes
    ) -> None:
        with self._lock:
            data = self._descriptor(descriptor)
            namespace = workspace_namespace(
                context.instance_uuid, context.workspace_uuid
            )
            key = namespace, data["content_digest"]
            existing = self._entries.get(key)
            if existing is not None:
                if existing.descriptor["manifest"] != data["manifest"]:
                    raise ValueError(
                        "Artifact descriptor conflicts with its cached revision"
                    )
                try:
                    self._validate_entry(existing)
                except (OSError, ValueError):
                    self._evict(existing)
                else:
                    existing.last_used = time.monotonic()
                    return
            if (
                not isinstance(archive, bytes)
                or len(archive) != data["archive_size"]
                or hashlib.sha256(archive).hexdigest() != data["archive_sha256"]
            ):
                raise ValueError("Artifact archive does not match its receipt")
            stage_name = ".langbot-artifact-stage-" + uuid.uuid4().hex
            with _parent_directory(self.root, "cache", create=False) as (root_fd, _):
                with self._directory(root_fd, namespace, create=True) as scope_fd:
                    os.mkdir(stage_name, 0o700, dir_fd=scope_fd)
                    try:
                        stage = os.path.join(self.root, namespace, stage_name)
                        package = os.path.join(stage, "package")
                        with self._directory(scope_fd, stage_name) as stage_fd:
                            self._write_file(
                                stage_fd,
                                "descriptor.json",
                                _json_bytes(
                                    {
                                        "format": 1,
                                        "namespace": namespace,
                                        "descriptor": data,
                                        "protected": False,
                                    }
                                ),
                            )
                            self._write_file(
                                stage_fd, "manifest.json", _json_bytes(data["manifest"])
                            )
                            os.mkdir("package", 0o700, dir_fd=stage_fd)
                            try:
                                self._extract(archive, data["manifest"], package)
                            except (
                                zipfile.BadZipFile,
                                zipfile.LargeZipFile,
                                RuntimeError,
                                NotImplementedError,
                                EOFError,
                                zlib.error,
                            ) as exc:
                                raise ValueError(
                                    "Invalid artifact ZIP archive"
                                ) from exc
                            if build_tree_manifest(
                                package, max_files=2048, max_total_bytes=_MAX_TREE_BYTES
                            ) != (data["content_digest"], data["manifest"]):
                                raise ValueError(
                                    "Artifact archive tree does not match its revision"
                                )
                            self._seal(stage_fd)
                            info = os.fstat(stage_fd)
                        size = self._stored_size(namespace, data)
                        self._make_room(size)
                        try:
                            os.stat(
                                data["content_digest"][7:],
                                dir_fd=scope_fd,
                                follow_symlinks=False,
                            )
                        except FileNotFoundError:
                            pass
                        else:
                            raise ValueError(
                                "Refusing to replace an unknown artifact cache entry"
                            )
                        os.rename(
                            stage_name,
                            data["content_digest"][7:],
                            src_dir_fd=scope_fd,
                            dst_dir_fd=scope_fd,
                        )
                        os.fsync(scope_fd)
                        self._entries[key] = _Entry(
                            namespace,
                            data,
                            os.path.join(
                                self.root, namespace, data["content_digest"][7:]
                            ),
                            size,
                            (info.st_dev, info.st_ino),
                            time.monotonic(),
                        )
                    finally:
                        try:
                            with self._directory(scope_fd, stage_name) as stage_fd:
                                self._nodes(stage_fd)
                                self._remove_contents(stage_fd)
                            os.rmdir(stage_name, dir_fd=scope_fd)
                        except FileNotFoundError:
                            pass

                        if not os.listdir(scope_fd):
                            os.rmdir(namespace, dir_fd=root_fd)

    @staticmethod
    def _extract(body: bytes, manifest: dict, package: str) -> None:
        expected = {entry["path"]: entry for entry in manifest["files"]}
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            members = archive.infolist()
            if len(members) != len(expected) or {
                member.filename for member in members
            } != set(expected):
                raise ValueError("Artifact archive members do not match its manifest")
            for member in members:
                entry = expected[member.filename]
                if (
                    member.is_dir()
                    or stat.S_IFMT(member.external_attr >> 16) not in {0, stat.S_IFREG}
                    or member.file_size != entry["size"]
                ):
                    raise ValueError("Artifact archive requires exact regular files")
                with _parent_directory(package, entry["path"], create=True) as (
                    directory,
                    name,
                ):
                    descriptor = os.open(
                        name,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=directory,
                    )
                    copied = 0
                    digest = hashlib.sha256()
                    with (
                        os.fdopen(descriptor, "wb") as target,
                        archive.open(member) as source,
                    ):
                        while chunk := source.read(
                            min(64 * 1024, entry["size"] - copied + 1)
                        ):
                            copied += len(chunk)
                            if copied > entry["size"]:
                                raise ValueError(
                                    "Artifact member exceeds its manifest size"
                                )
                            digest.update(chunk)
                            target.write(chunk)
                        target.flush()
                        os.fsync(target.fileno())
                    if copied != entry["size"] or digest.hexdigest() != entry["sha256"]:
                        raise ValueError("Artifact member failed digest verification")
                    os.chmod(
                        name,
                        0o555 if entry["executable"] else 0o444,
                        dir_fd=directory,
                        follow_symlinks=False,
                    )

    @staticmethod
    def _seal(directory: int) -> None:
        for name in os.listdir(directory):
            if stat.S_ISDIR(
                os.stat(name, dir_fd=directory, follow_symlinks=False).st_mode
            ):
                with ArtifactCache._directory(directory, name) as child:
                    ArtifactCache._seal(child)
        os.fsync(directory)
        os.fchmod(directory, 0o555)

    def acquire(
        self, context: ActionContext, digests: list[str], owner: str
    ) -> list[BoxMountSpec]:
        if not isinstance(owner, str) or not owner or len(owner) > 512:
            raise ValueError("Artifact pin requires a bounded session owner")
        with self._lock:
            namespace = workspace_namespace(
                context.instance_uuid, context.workspace_uuid
            )
            entries = []
            for digest in dict.fromkeys(digests):
                if (
                    not isinstance(digest, str)
                    or not digest.startswith("sha256:")
                    or not _DIGEST.fullmatch(digest[7:])
                ):
                    raise ValueError("Invalid artifact content digest")
                entry = self._entries.get((namespace, digest))
                if entry is None:
                    raise ValueError(
                        "Artifact revision is not prepared for this Workspace"
                    )
                self._validate_entry(entry)
                entries.append(entry)
            mounts = [
                BoxMountSpec(
                    host_path=os.path.join(entry.path, "package"),
                    manifest_path=os.path.join(entry.path, "manifest.json"),
                    mount_path=f"{ARTIFACT_MOUNT_ROOT}/{entry.descriptor['content_digest'][7:]}",
                    mode=BoxHostMountMode.READ_ONLY,
                    content_digest=entry.descriptor["content_digest"],
                )
                for entry in entries
            ]
            newly_protected = []
            try:
                for entry in entries:
                    if not entry.protected:
                        self._write_protected(entry, True)
                        newly_protected.append(entry)
            except BaseException:
                for entry in newly_protected:
                    try:
                        self._write_protected(entry, False)
                    except BaseException:
                        entry.crash_protected = True
                raise
            for entry in entries:
                entry.owners.add(owner)
                entry.last_used = time.monotonic()
                self._owners.setdefault(owner, set()).add(entry.key)
            return mounts

    def release(self, owner: str) -> None:
        with self._lock:
            owned = self._owners.get(owner)
            if owned is None:
                return
            for key in tuple(owned):
                entry = self._entries.get(key)
                if entry is not None:
                    if entry.owners == {owner} and not entry.crash_protected:
                        self._write_protected(entry, False)
                    entry.owners.discard(owner)
                    entry.last_used = time.monotonic()
                owned.discard(key)
            if not owned:
                self._owners.pop(owner, None)

    def reap(self) -> None:
        with self._lock:
            self._reap()

    def _write_protected(self, entry: _Entry, protected: bool) -> None:
        temporary = ".langbot-artifact-state-" + uuid.uuid4().hex + ".tmp"
        envelope = {
            "format": 1,
            "namespace": entry.namespace,
            "descriptor": entry.descriptor,
            "protected": protected,
        }
        try:
            with _parent_directory(self.root, "cache", create=False) as (root_fd, _):
                with (
                    self._directory(root_fd, entry.namespace) as scope_fd,
                    self._directory(
                        scope_fd, entry.descriptor["content_digest"][7:]
                    ) as entry_fd,
                ):
                    info = os.fstat(entry_fd)
                    if (info.st_dev, info.st_ino) != entry.identity:
                        raise ValueError("Artifact cache entry identity changed")
                    try:
                        self._write_file(scope_fd, temporary, _json_bytes(envelope))
                        os.fchmod(entry_fd, 0o755)
                        os.replace(
                            temporary,
                            "descriptor.json",
                            src_dir_fd=scope_fd,
                            dst_dir_fd=entry_fd,
                        )
                        entry.protected = protected
                        os.fsync(entry_fd)
                        os.fsync(scope_fd)
                    finally:
                        os.fchmod(entry_fd, 0o555)
                        try:
                            os.unlink(temporary, dir_fd=scope_fd)
                        except FileNotFoundError:
                            pass
        except BaseException:
            # An uncertain metadata write must never turn into permission to GC.
            entry.crash_protected = True
            raise

    def cleanup_staging(self) -> None:
        with self._lock:
            with _parent_directory(self.root, "cache", create=False) as (root_fd, _):
                for namespace in os.listdir(root_fd):
                    if not _SCOPE.fullmatch(namespace):
                        continue
                    with self._directory(root_fd, namespace) as scope_fd:
                        for name in os.listdir(scope_fd):
                            if _STATE_STAGING.fullmatch(name):
                                info = os.stat(
                                    name, dir_fd=scope_fd, follow_symlinks=False
                                )
                                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                                    raise ValueError(
                                        "Refusing to remove unsafe artifact metadata staging"
                                    )
                                os.unlink(name, dir_fd=scope_fd)
                                continue
                            if not _STAGING.fullmatch(name):
                                continue
                            with self._directory(scope_fd, name) as stage_fd:
                                self._nodes(stage_fd)
                                self._remove_contents(stage_fd)
                            os.rmdir(name, dir_fd=scope_fd)
                        if not os.listdir(scope_fd):
                            os.rmdir(namespace, dir_fd=root_fd)
