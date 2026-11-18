from __future__ import annotations

import hashlib
import json
import os
import posixpath
import stat
from collections.abc import Collection


TREE_MANIFEST_ALGORITHM = "sha256-tree-v1"
_MAX_MANIFEST_BYTES = 4 * 1024 * 1024


def validate_tree_manifest(
    manifest: dict,
    *,
    max_files: int,
    max_total_bytes: int,
    subject: str = "Artifact",
) -> tuple[str, dict]:
    """Validate a persisted manifest and return its canonical digest."""

    if not isinstance(manifest, dict) or set(manifest) != {
        "algorithm",
        "files",
        "total_bytes",
    }:
        raise ValueError(f"{subject} manifest has an invalid shape")
    if manifest["algorithm"] != TREE_MANIFEST_ALGORITHM:
        raise ValueError(f"{subject} manifest uses an unsupported algorithm")
    files = manifest["files"]
    if not isinstance(files, list) or len(files) > max_files:
        raise ValueError(f"{subject} manifest contains too many files")
    seen: set[str] = set()
    calculated_total = 0
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {
            "path",
            "size",
            "sha256",
            "executable",
        }:
            raise ValueError(f"{subject} manifest contains an invalid file entry")
        path = entry["path"]
        if (
            not isinstance(path, str)
            or not path
            or "\0" in path
            or "\\" in path
            or posixpath.isabs(path)
            or posixpath.normpath(path) != path
            or path in {".", ".."}
            or path.startswith("../")
            or path in seen
        ):
            raise ValueError(f"{subject} manifest contains an unsafe path")
        seen.add(path)
        size = entry["size"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError(f"{subject} manifest contains an invalid file size")
        calculated_total += size
        digest = entry["sha256"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(ch not in "0123456789abcdef" for ch in digest)
        ):
            raise ValueError(f"{subject} manifest contains an invalid file digest")
        if not isinstance(entry["executable"], bool):
            raise ValueError(f"{subject} manifest contains an invalid file mode")

    declared_total = manifest["total_bytes"]
    if (
        isinstance(declared_total, bool)
        or not isinstance(declared_total, int)
        or declared_total != calculated_total
        or declared_total > max_total_bytes
    ):
        raise ValueError(f"{subject} manifest contains an invalid total size")
    canonical = json.dumps(
        manifest,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}", manifest


def load_tree_manifest(
    path: str,
    *,
    max_files: int,
    max_total_bytes: int,
    subject: str = "Artifact",
) -> tuple[str, dict]:
    if os.path.getsize(path) > _MAX_MANIFEST_BYTES:
        raise ValueError(f"{subject} manifest is too large")
    with open(path, "rb") as file:
        body = file.read(_MAX_MANIFEST_BYTES + 1)
    if len(body) > _MAX_MANIFEST_BYTES:
        raise ValueError(f"{subject} manifest is too large")
    try:
        manifest = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{subject} manifest is invalid JSON") from exc
    return validate_tree_manifest(
        manifest,
        max_files=max_files,
        max_total_bytes=max_total_bytes,
        subject=subject,
    )


def build_tree_manifest(
    root: str,
    *,
    max_files: int,
    max_total_bytes: int,
    skip_directories: Collection[str] = (),
    subject: str = "Artifact",
) -> tuple[str, dict]:
    """Validate a regular-file tree and return its canonical content digest."""

    resolved_root = os.path.realpath(str(root or "").strip())
    if not resolved_root or not os.path.isdir(resolved_root):
        raise ValueError(f"{subject} directory is unavailable")

    files: list[dict] = []
    total_bytes = 0
    for current_root, dir_names, file_names in os.walk(
        resolved_root,
        followlinks=False,
    ):
        dir_names[:] = [name for name in dir_names if name not in skip_directories]
        dir_names.sort()
        file_names.sort()
        for directory_name in dir_names:
            if os.path.islink(os.path.join(current_root, directory_name)):
                raise ValueError(f"{subject} cannot contain symbolic links")
        for file_name in file_names:
            path = os.path.join(current_root, file_name)
            file_stat = os.stat(path, follow_symlinks=False)
            if os.path.islink(path):
                raise ValueError(f"{subject} cannot contain symbolic links")
            if not stat.S_ISREG(file_stat.st_mode):
                raise ValueError(f"{subject} can contain regular files only")
            if len(files) >= max_files:
                raise ValueError(f"{subject} contains too many files")
            total_bytes += file_stat.st_size
            if total_bytes > max_total_bytes:
                raise ValueError(f"{subject} is too large")

            file_digest = hashlib.sha256()
            with open(path, "rb") as file:
                while True:
                    chunk = file.read(256 * 1024)
                    if not chunk:
                        break
                    file_digest.update(chunk)
            files.append(
                {
                    "path": os.path.relpath(path, resolved_root).replace(os.sep, "/"),
                    "size": file_stat.st_size,
                    "sha256": file_digest.hexdigest(),
                    "executable": bool(stat.S_IMODE(file_stat.st_mode) & 0o111),
                }
            )

    manifest = {
        "algorithm": TREE_MANIFEST_ALGORITHM,
        "files": files,
        "total_bytes": total_bytes,
    }
    return validate_tree_manifest(
        manifest,
        max_files=max_files,
        max_total_bytes=max_total_bytes,
        subject=subject,
    )


__all__ = [
    "TREE_MANIFEST_ALGORITHM",
    "build_tree_manifest",
    "load_tree_manifest",
    "validate_tree_manifest",
]


def materialize_tree(
    source: str, manifest_path: str, expected_digest: str, cache_root: str
) -> str:
    """Publish a complete verified tree outside the sandbox before making it visible."""
    import shutil
    import tempfile

    max_bytes = 256 * 1024 * 1024
    digest, manifest = load_tree_manifest(
        manifest_path, max_files=2048, max_total_bytes=max_bytes
    )
    if digest != expected_digest:
        raise ValueError("Artifact manifest does not match content_digest")
    target = os.path.join(cache_root, digest[7:])
    if os.path.isdir(target) and not os.path.islink(target):
        return target
    used = sum(
        os.path.getsize(os.path.join(root, name))
        for root, _, names in os.walk(cache_root)
        for name in names
    )
    if len(os.listdir(cache_root)) >= 256 or used + manifest["total_bytes"] > max_bytes:
        raise ValueError("Immutable artifact cache limit reached; acquire a new Box")
    staging = tempfile.mkdtemp(
        prefix="langbot-artifact-stage-", dir=os.path.dirname(cache_root)
    )
    try:
        for entry in manifest["files"]:
            source_path = os.path.join(source, *entry["path"].split("/"))
            descriptor = os.open(
                source_path,
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0),
            )
            with os.fdopen(descriptor, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError("Artifact source must be a regular file")
                body = stream.read(entry["size"] + 1)
            if (
                len(body) != entry["size"]
                or hashlib.sha256(body).hexdigest() != entry["sha256"]
            ):
                raise ValueError(f"Artifact source changed: {entry['path']}")
            destination = os.path.join(staging, *entry["path"].split("/"))
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            with open(destination, "xb") as stream:
                stream.write(body)
            os.chmod(destination, 0o555 if entry["executable"] else 0o444)
        os.chmod(staging, 0o755)
        os.rename(staging, target)
        return target
    finally:
        if os.path.isdir(staging):
            shutil.rmtree(staging)
