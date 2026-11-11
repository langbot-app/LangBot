from __future__ import annotations

import collections
import contextlib
import datetime as dt
import io
import json
import mimetypes
import os
import posixpath
import re
import shutil
import stat
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Optional

import yaml

from .artifact import build_tree_manifest
from .workspace import workspace_namespace


_PUBLIC_SKILL_FIELDS = (
    "name",
    "display_name",
    "description",
    "metadata",
    "instructions",
    "package_root",
    "manifest_path",
    "entry_file",
    "python_project",
    "revision",
    "created_at",
    "updated_at",
)

# Skill uploads are untrusted. These fixed store-owned caps apply to both
# preview and installation and are deliberately not configurable per tenant.
_MAX_ZIP_COMPRESSED_BYTES = 20 * 1024 * 1024
_MAX_ZIP_ENTRIES = 512
_MAX_ZIP_ENTRY_UNCOMPRESSED_BYTES = 16 * 1024 * 1024
_MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
_MAX_ZIP_COMPRESSION_RATIO = 100.0
_ZIP_COPY_CHUNK_BYTES = 64 * 1024
_MAX_SKILL_TEXT_BYTES = 1024 * 1024
_MAX_DISCOVERED_SKILLS = 1_000
_MAX_SKILL_SCAN_ENTRIES = 10_000
_MAX_SKILL_LIST_ENTRIES = 1_000
_MAX_SKILL_DIRECTORY_ENTRIES = 10_000
_MAX_SKILL_LIST_TOTAL_TEXT_BYTES = 16 * 1024 * 1024
_MAX_REVISION_FILES = 2_048
_MAX_REVISION_BYTES = 256 * 1024 * 1024
_REVISION_SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules"}
_STORE_DIRECTORY = ".langbot-skill-store"
_REVISION_PREFIX = "sha256:"


class SkillRevisionMismatchError(ValueError):
    """Raised when a caller reads a package other than the activated revision."""


class SkillRevisionConflictError(SkillRevisionMismatchError):
    """Raised when a publication is based on a stale current revision."""


class SkillRevisionNotFoundError(SkillRevisionMismatchError):
    """Raised when a pinned immutable revision can no longer be recovered."""


@contextlib.contextmanager
def _exclusive_file_lock(path: str):
    """Hold an OS-backed exclusive lock shared by all Core processes."""

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a+b") as lock_file:
        if os.name == "nt":  # pragma: no cover - exercised on Windows CI
            import msvcrt

            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def skill_namespace(instance_uuid: str, workspace_uuid: str) -> str:
    """Return the durable Skill namespace for one instance and Workspace."""

    return workspace_namespace(instance_uuid, workspace_uuid)


def _resource_mime_type(path: str) -> str:
    if Path(path).suffix.lower() == ".md":
        return "text/markdown"
    return mimetypes.guess_type(path)[0] or "text/plain"


def _read_utf8_text_limited(path: str, *, subject: str) -> str:
    if os.path.getsize(path) > _MAX_SKILL_TEXT_BYTES:
        raise ValueError(f"{subject} exceeds the {_MAX_SKILL_TEXT_BYTES}-byte limit")
    with open(path, "rb") as file:
        content = file.read(_MAX_SKILL_TEXT_BYTES + 1)
    if len(content) > _MAX_SKILL_TEXT_BYTES:
        raise ValueError(f"{subject} exceeds the {_MAX_SKILL_TEXT_BYTES}-byte limit")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{subject} is not valid UTF-8 text") from exc


def parse_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---"):
        return {}, content

    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, content

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            metadata_text = "".join(lines[1:index])
            instructions = "".join(lines[index + 1 :]).lstrip("\n")
            metadata = yaml.safe_load(metadata_text) or {}
            if not isinstance(metadata, dict):
                metadata = {}
            return metadata, instructions

    return {}, content


def build_skill_md(metadata: dict, instructions: str) -> str:
    # Preserve complete extensible Agent Skills frontmatter.
    frontmatter = {}
    for key, value in (metadata or {}).items():
        if key in {
            "package_root",
            "manifest_path",
            "entry_file",
            "instructions",
            "revision",
            "created_at",
            "updated_at",
            "source_path",
            "python_project",
        }:
            continue
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        frontmatter[key] = value

    if not frontmatter:
        return instructions

    frontmatter_text = yaml.dump(
        frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False
    ).strip()
    return f"---\n{frontmatter_text}\n---\n\n{instructions}"


class SkillStore:
    """Filesystem-backed Skill package storage independent from execution."""

    def __init__(
        self,
        root: str | os.PathLike[str] = "./data/skills",
        *,
        namespace: str | None = None,
    ):
        root_path = Path(root).expanduser()
        if not root_path.is_absolute():
            root_path = Path.cwd() / root_path
        self._base_root = root_path.resolve()
        self._namespace = namespace

    def scoped(self, namespace: str) -> SkillStore:
        """Return an immutable Workspace view over the configured skill store."""

        normalized = str(namespace or "").strip()
        if (
            not normalized
            or "/" in normalized
            or "\\" in normalized
            or normalized in {".", ".."}
        ):
            raise ValueError("Invalid Skill store namespace")
        return SkillStore(self._base_root, namespace=normalized)

    @property
    def root(self) -> str:
        resolved_root = self._base_root
        if self._namespace is not None:
            resolved_root = resolved_root / "tenants" / self._namespace
        return str(resolved_root)

    def list_skills(self) -> list[dict]:
        self._ensure_legacy_packages_published()
        skills: list[dict] = []
        retained_text_bytes = 0
        registry_root = self._registry_root()
        if not os.path.isdir(registry_root):
            return []
        for entry in sorted(os.scandir(registry_root), key=lambda item: item.name):
            if not entry.is_file(follow_symlinks=False) or not entry.name.endswith(
                ".json"
            ):
                continue
            skill_name = entry.name[: -len(".json")]
            skill = self._load_published_skill(skill_name)
            retained_text_bytes += sum(
                len(value.encode("utf-8"))
                for key, value in skill.items()
                if key != "metadata" and isinstance(value, str)
            )
            metadata = skill.get("metadata")
            if metadata is not None:
                retained_text_bytes += len(
                    json.dumps(
                        metadata,
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                        separators=(",", ":"),
                    ).encode("utf-8")
                )
            if retained_text_bytes > _MAX_SKILL_LIST_TOTAL_TEXT_BYTES:
                raise ValueError("Skill listing exceeds the configured text limit")
            skills.append(skill)
        skills.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return skills

    def get_skill(
        self,
        skill_name: str,
        *,
        revision: str | None = None,
    ) -> Optional[dict]:
        skill_name = self._validate_skill_name(skill_name)
        self._ensure_legacy_packages_published()
        if revision is not None:
            return self._load_published_skill(skill_name, revision=revision)
        if not os.path.isfile(self._registry_path(skill_name)):
            return None
        return self._load_published_skill(skill_name)

    def get_skill_snapshot(
        self,
        skill_name: str,
        revision: str | None = None,
    ) -> Optional[dict]:
        """Return the current or explicitly pinned immutable publication."""

        return self.get_skill(skill_name, revision=revision)

    def resolve_skill_package_root(
        self,
        skill_name: str,
        revision: str | None = None,
    ) -> str:
        """Return a trusted package root for a Runtime-owned sandbox mount.

        Only Workspace-scoped stores may resolve mounts. The result comes from
        the store's own discovery, is canonicalized back under that Workspace's
        root, and never incorporates a Core-supplied host path.
        """

        if self._namespace is None:
            raise ValueError("Skill sandbox mounts require a Workspace-scoped store")
        skill_name = self._validate_skill_name(skill_name)
        skill = self._require_skill(skill_name, revision=revision)
        package_root = self._require_scoped_path(
            str(skill.get("package_root") or ""), "skill package"
        )
        if not os.path.isdir(package_root):
            raise ValueError(f'Skill "{skill_name}" package directory is unavailable')
        return package_root

    def create_skill(self, data: dict) -> dict:
        name = self._validate_skill_name(data.get("name", ""))
        source_root = self._normalize_package_root(data.get("package_root", ""))
        if self._namespace is not None and source_root:
            self._require_scoped_path(source_root, "package_root")
        self._ensure_legacy_packages_published()
        with self._skill_lock(name):
            if self._read_registry(name) is not None:
                raise ValueError(f'Skill with name "{name}" already exists')
            return self._publish_from_source_locked(name, data)

    def update_skill(
        self,
        skill_name: str,
        data: dict,
        *,
        base_revision: str | None,
    ) -> dict:
        skill_name = self._validate_skill_name(skill_name)
        self._ensure_legacy_packages_published()
        with self._skill_lock(skill_name):
            current = self._require_current_registry(skill_name)
            self._require_base_revision(skill_name, current, base_revision)
            skill = self._load_published_skill(skill_name, registry=current)
            requested_name = str(
                data.get("name", skill["name"]) or skill["name"]
            ).strip()
            if requested_name != skill["name"]:
                raise ValueError("Renaming skills is not supported")
            requested_package_root = str(data.get("package_root", "") or "").strip()
            if requested_package_root:
                raise ValueError(
                    "Updating package_root is not supported; publish a draft directory instead"
                )
            publish_data = {
                "name": skill["name"],
                "display_name": data.get("display_name", skill.get("display_name", "")),
                "description": data.get("description", skill.get("description", "")),
                "instructions": str(
                    data.get("instructions", skill.get("instructions", "")) or ""
                ),
                "package_root": skill["package_root"],
            }
            return self._publish_from_source_locked(
                skill_name,
                publish_data,
                current_registry=current,
            )

    def delete_skill(self, skill_name: str) -> dict:
        skill_name = self._validate_skill_name(skill_name)
        self._ensure_legacy_packages_published()
        with self._skill_lock(skill_name):
            self._require_current_registry(skill_name)
            os.unlink(self._registry_path(skill_name))
            self._fsync_directory(self._registry_root())
        # Immutable revisions are retained for active and recoverable runs.
        return {"deleted": skill_name}

    def scan_directory(self, path: str) -> dict:
        if self._namespace is not None:
            path = self._require_scoped_path(path, "scan path")
        if not os.path.isdir(path):
            raise ValueError(f"Directory does not exist: {path}")

        discovered = self._discover_skill_directories(path, max_depth=2)
        if not discovered:
            raise ValueError(
                f"No SKILL.md found in {path} or its subdirectories (max depth: 2)"
            )
        if len(discovered) > 1:
            candidates = ", ".join(found_path for found_path, _entry in discovered)
            raise ValueError(
                f"Multiple skill directories found in {path}. Please choose a more specific path: {candidates}"
            )

        package_root, entry_file = discovered[0]
        skill = self._load_skill_package(package_root, entry_file)
        self._validate_agent_skill_package(package_root, skill.get("metadata") or {})
        return skill

    def scan_import_directory(self, path: str, *, source_root: str) -> dict:
        """Scan a trusted import source without granting arbitrary host access."""

        source = self._require_path_under(path, source_root, "scan path")
        self._require_safe_import_tree(source)
        return SkillStore(self.root).scan_directory(source)

    def import_skill_directory(
        self,
        path: str,
        data: dict,
        *,
        source_root: str,
        base_revision: str | None = None,
    ) -> dict:
        """Atomically publish a fenced draft as a new immutable revision."""

        source = self._require_path_under(path, source_root, "import path")
        self._require_safe_import_tree(source)
        payload = dict(data)
        payload["package_root"] = source
        name = self._validate_skill_name(payload.get("name", ""))
        self._ensure_legacy_packages_published()
        with self._skill_lock(name):
            current = self._read_registry(name)
            if current is None:
                if str(base_revision or "").strip():
                    raise SkillRevisionConflictError(
                        f'Skill "{name}" does not exist; base_revision must be omitted'
                    )
            else:
                self._require_base_revision(name, current, base_revision)
            return self._publish_from_source_locked(
                name,
                payload,
                current_registry=current,
            )

    def _require_scoped_path(self, path: str, label: str) -> str:
        """Keep host-path operations inside this Workspace's skill root.

        A scoped SkillStore may be shared by mutually untrusted Workspaces. Host
        paths supplied over RPC are therefore routing input, not authority.
        ``realpath`` also prevents a symlink inside one tenant root from being
        used to import or scan another tenant's files.
        """

        candidate = self._normalize_package_root(path)
        scoped_root = self._normalize_package_root(self.root)
        if not candidate or (
            candidate != scoped_root
            and not candidate.startswith(f"{scoped_root}{os.sep}")
        ):
            raise ValueError(f"{label} must stay within the Workspace skill root")
        return candidate

    def list_skill_files(
        self,
        skill_name: str,
        path: str = ".",
        include_hidden: bool = False,
        max_entries: int = 200,
    ) -> dict:
        return self._list_skill_files(
            self._require_skill(skill_name),
            path,
            include_hidden,
            max_entries,
        )

    def _list_skill_files(
        self,
        skill: dict,
        path: str,
        include_hidden: bool,
        max_entries: int,
    ) -> dict:
        if (
            isinstance(max_entries, bool)
            or not isinstance(max_entries, int)
            or max_entries <= 0
        ):
            raise ValueError("max_entries must be a positive integer")
        max_entries = min(max_entries, _MAX_SKILL_LIST_ENTRIES)
        target_dir, relative_path = self._resolve_skill_path(
            skill, path, expect_directory=True
        )
        with os.scandir(target_dir) as iterator:
            directory_entries = []
            for entry in iterator:
                if len(directory_entries) >= _MAX_SKILL_DIRECTORY_ENTRIES:
                    raise ValueError(
                        "Skill directory exceeds the configured entry limit"
                    )
                directory_entries.append(entry)
        directory_entries.sort(key=lambda item: item.name)
        visible_entries = [
            entry
            for entry in directory_entries
            if include_hidden or not entry.name.startswith(".")
        ]
        entries: list[dict] = []
        for entry in visible_entries[:max_entries]:
            entry_rel_path = (
                entry.name
                if relative_path in ("", ".")
                else os.path.join(relative_path, entry.name)
            )
            is_dir = entry.is_dir()
            entries.append(
                {
                    "path": entry_rel_path.replace(os.sep, "/"),
                    "name": entry.name,
                    "is_dir": is_dir,
                    "size": None if is_dir else entry.stat().st_size,
                }
            )

        return {
            "skill": {"name": skill["name"]},
            "base_path": "."
            if relative_path in ("", ".")
            else relative_path.replace(os.sep, "/"),
            "entries": entries,
            "truncated": len(visible_entries) > max_entries,
        }

    def read_skill_file(self, skill_name: str, path: str) -> dict:
        return self._read_skill_file(self._require_skill(skill_name), path)

    def _read_skill_file(self, skill: dict, path: str) -> dict:
        target_path, relative_path = self._resolve_skill_path(
            skill, path, expect_directory=False
        )
        if not os.path.isfile(target_path):
            raise ValueError(f"Skill file not found: {relative_path}")

        content = _read_utf8_text_limited(
            target_path,
            subject=f"Skill file {relative_path}",
        )

        return {
            "skill": {"name": skill["name"]},
            "path": relative_path.replace(os.sep, "/"),
            "content": content,
        }

    def list_skill_resources(
        self,
        skill_name: str,
        path: str = ".",
        include_hidden: bool = False,
        max_entries: int = 200,
        *,
        expected_revision: str | None = None,
    ) -> dict:
        """List resources after checking the activated Skill revision."""

        skill = self._require_skill(skill_name, revision=expected_revision)
        revision = str(skill["revision"])
        result = self._list_skill_files(
            skill,
            path,
            include_hidden,
            max_entries,
        )
        result["revision"] = revision
        for entry in result.get("entries", []):
            if not entry.get("is_dir"):
                entry["mime_type"] = _resource_mime_type(str(entry.get("path", "")))
        return result

    def read_skill_resource(
        self,
        skill_name: str,
        path: str,
        *,
        expected_revision: str | None = None,
    ) -> dict:
        """Read one UTF-8 resource after checking the activated revision."""

        skill = self._require_skill(skill_name, revision=expected_revision)
        revision = str(skill["revision"])
        result = self._read_skill_file(skill, path)
        result["revision"] = revision
        result["mime_type"] = _resource_mime_type(path)
        return result

    def write_skill_file(
        self,
        skill_name: str,
        path: str,
        content: str,
        *,
        base_revision: str | None,
    ) -> dict:
        """Publish a new revision containing one changed text file.

        This API remains useful to trusted management UIs, but it never writes
        into the current published package. Agent authoring should use a draft
        directory and ``import_skill_directory`` instead.
        """

        encoded_content = content.encode("utf-8")
        relative_path = str(path or "").strip()
        if len(encoded_content) > _MAX_SKILL_TEXT_BYTES:
            raise ValueError(
                f"Skill file {relative_path} exceeds the "
                f"{_MAX_SKILL_TEXT_BYTES}-byte limit"
            )
        skill_name = self._validate_skill_name(skill_name)
        self._ensure_legacy_packages_published()
        with self._skill_lock(skill_name):
            current = self._require_current_registry(skill_name)
            self._require_base_revision(skill_name, current, base_revision)
            skill = self._load_published_skill(skill_name, registry=current)
            staging_root, staging_package = self._stage_package(skill["package_root"])
            try:
                staging_skill = dict(skill)
                staging_skill["package_root"] = staging_package
                target_path, normalized_relative = self._resolve_skill_path(
                    staging_skill, relative_path, expect_directory=False
                )
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "w", encoding="utf-8") as file:
                    file.write(content)
                published = self._publish_staged_locked(
                    skill_name,
                    staging_root,
                    current_registry=current,
                )
                staging_root = ""
            finally:
                if staging_root:
                    self._remove_staging_tree(staging_root)
        return {
            "skill": {"name": skill["name"]},
            "path": normalized_relative.replace(os.sep, "/"),
            "bytes_written": len(encoded_content),
            "revision": published["revision"],
        }

    def preview_zip_upload(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        source_subdir: str = "",
        target_suffix: str = "upload",
    ) -> list[dict]:
        if not file_bytes:
            raise ValueError("Uploaded file is empty")
        self._validate_zip_upload_size(file_bytes)

        tmp_dir = tempfile.mkdtemp(prefix="langbot_skill_preview_")
        try:
            skill_root, allow_root_package = self._extract_uploaded_skill_to_temp(
                file_bytes, tmp_dir
            )
            skill_root = self._resolve_source_subdir_root(skill_root, source_subdir)
            allow_root_package = allow_root_package and not source_subdir.strip()
            return self._preview_skill_candidates(
                skill_root,
                base_target_name=self._uploaded_skill_target_stem(filename),
                suffix=target_suffix,
                allow_root_package=allow_root_package,
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def install_zip_upload(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        source_paths: list[str] | None = None,
        source_path: str = "",
        source_subdir: str = "",
        target_suffix: str = "upload",
    ) -> list[dict]:
        if not file_bytes:
            raise ValueError("Uploaded file is empty")
        self._validate_zip_upload_size(file_bytes)

        tmp_dir = tempfile.mkdtemp(prefix="langbot_skill_upload_")
        try:
            skill_root, allow_root_package = self._extract_uploaded_skill_to_temp(
                file_bytes, tmp_dir
            )
            skill_root = self._resolve_source_subdir_root(skill_root, source_subdir)
            allow_root_package = allow_root_package and not source_subdir.strip()
            previews = self._preview_skill_candidates(
                skill_root,
                base_target_name=self._uploaded_skill_target_stem(filename),
                suffix=target_suffix,
                allow_root_package=allow_root_package,
            )
            selected_previews = self._select_preview_candidates(
                previews,
                {"source_paths": source_paths or [], "source_path": source_path},
            )
            scanned = self._install_preview_candidates(
                skill_root, selected_previews, allow_root_package=allow_root_package
            )
            return scanned
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _require_skill(
        self,
        skill_name: str,
        *,
        revision: str | None = None,
    ) -> dict:
        skill = self.get_skill(skill_name, revision=revision)
        if not skill:
            raise ValueError(f'Skill "{skill_name}" not found')
        return skill

    @staticmethod
    def _require_path_under(path: str, root: str, label: str) -> str:
        raw_candidate = os.path.abspath(str(path or "").strip())
        candidate = os.path.realpath(raw_candidate)
        trusted_root = os.path.realpath(os.path.abspath(str(root or "").strip()))
        if (
            not path
            or not root
            or (
                candidate != trusted_root
                and not candidate.startswith(f"{trusted_root}{os.sep}")
            )
        ):
            raise ValueError(f"{label} must stay within the trusted source root")
        if not os.path.isdir(candidate):
            raise ValueError(f"Directory does not exist: {path}")
        if os.path.islink(raw_candidate):
            raise ValueError(f"{label} cannot be a symbolic link")
        return candidate

    @staticmethod
    def _require_safe_import_tree(root: str) -> None:
        scanned_entries = 0
        for current_root, dir_names, file_names in os.walk(root, followlinks=False):
            dir_names[:] = [
                name for name in dir_names if name not in _REVISION_SKIP_DIRS
            ]
            for name in (*dir_names, *file_names):
                scanned_entries += 1
                if scanned_entries > _MAX_SKILL_SCAN_ENTRIES:
                    raise ValueError("Skill import exceeded the configured entry limit")
                path = os.path.join(current_root, name)
                stat_result = os.lstat(path)
                if stat.S_ISLNK(stat_result.st_mode):
                    raise ValueError("Skill imports cannot contain symbolic links")
                if name in file_names and not stat.S_ISREG(stat_result.st_mode):
                    raise ValueError("Skill imports can contain regular files only")

    @staticmethod
    def _package_manifest(package_root: str) -> tuple[str, dict]:
        """Validate and digest a complete staged package exactly once."""

        return build_tree_manifest(
            package_root,
            max_files=_MAX_REVISION_FILES,
            max_total_bytes=_MAX_REVISION_BYTES,
            skip_directories=_REVISION_SKIP_DIRS,
            subject="Skill package",
        )

    @staticmethod
    def _package_revision(package_root: str) -> str:
        """Return the publication digest for a staged package.

        Published reads use the persisted registry pointer and never call this
        function, so package-size work stays confined to publication.
        """

        return SkillStore._package_manifest(package_root)[0]

    def _store_root(self) -> str:
        return os.path.join(self.root, _STORE_DIRECTORY)

    def _registry_root(self) -> str:
        return os.path.join(self._store_root(), "registry")

    def _revisions_root(self) -> str:
        return os.path.join(self._store_root(), "revisions")

    def _staging_root(self) -> str:
        return os.path.join(self._store_root(), "staging")

    def _locks_root(self) -> str:
        return os.path.join(self._store_root(), "locks")

    def _registry_path(self, skill_name: str) -> str:
        return os.path.join(self._registry_root(), f"{skill_name}.json")

    def _revision_directory(self, revision: str) -> str:
        digest = self._validate_revision(revision)
        return os.path.join(self._revisions_root(), digest)

    def _revision_package_root(self, revision: str) -> str:
        return os.path.join(self._revision_directory(revision), "package")

    @staticmethod
    def _validate_revision(revision: str | None) -> str:
        normalized = str(revision or "").strip()
        if not normalized.startswith(_REVISION_PREFIX):
            raise SkillRevisionNotFoundError(
                f"Pinned Skill revision is invalid: {normalized or '<empty>'}"
            )
        digest = normalized[len(_REVISION_PREFIX) :]
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise SkillRevisionNotFoundError(
                f"Pinned Skill revision is invalid: {normalized}"
            )
        return digest

    @contextlib.contextmanager
    def _skill_lock(self, skill_name: str):
        lock_path = os.path.join(self._locks_root(), f"{skill_name}.lock")
        with _exclusive_file_lock(lock_path):
            yield

    def _read_registry(self, skill_name: str) -> dict | None:
        path = self._registry_path(skill_name)
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f'Skill "{skill_name}" registry is unreadable') from exc
        if not isinstance(data, dict) or data.get("name") != skill_name:
            raise ValueError(f'Skill "{skill_name}" registry is invalid')
        self._validate_revision(data.get("current_revision"))
        return data

    def _require_current_registry(self, skill_name: str) -> dict:
        registry = self._read_registry(skill_name)
        if registry is None:
            raise ValueError(f'Skill "{skill_name}" not found')
        return registry

    @staticmethod
    def _require_base_revision(
        skill_name: str,
        registry: dict,
        base_revision: str | None,
    ) -> None:
        current_revision = str(registry.get("current_revision") or "")
        normalized = str(base_revision or "").strip()
        if not normalized:
            raise SkillRevisionConflictError(
                f'Updating Skill "{skill_name}" requires base_revision '
                f"(current {current_revision})"
            )
        if normalized != current_revision:
            raise SkillRevisionConflictError(
                f'Skill "{skill_name}" changed since the draft was created '
                f"(base {normalized}, current {current_revision})"
            )

    def _load_published_skill(
        self,
        skill_name: str,
        *,
        revision: str | None = None,
        registry: dict | None = None,
    ) -> dict:
        registry = registry if registry is not None else self._read_registry(skill_name)
        if revision is None:
            if registry is None:
                raise ValueError(f'Skill "{skill_name}" not found')
            revision = str(registry["current_revision"])
        normalized_revision = f"{_REVISION_PREFIX}{self._validate_revision(revision)}"
        package_root = self._revision_package_root(normalized_revision)
        if not os.path.isdir(package_root):
            raise SkillRevisionNotFoundError(
                f'Skill "{skill_name}" pinned revision {normalized_revision} is unavailable'
            )
        skill = self._load_skill_package(package_root)
        if skill["name"] != skill_name:
            raise SkillRevisionNotFoundError(
                f'Pinned revision {normalized_revision} does not belong to Skill "{skill_name}"'
            )
        skill["revision"] = normalized_revision
        skill["manifest_path"] = os.path.join(
            self._revision_directory(normalized_revision),
            "manifest.json",
        )
        if registry is not None:
            skill["created_at"] = registry.get("created_at", skill["created_at"])
            if normalized_revision == registry.get("current_revision"):
                skill["updated_at"] = registry.get("updated_at", skill["updated_at"])
        return self._serialize_skill(skill)

    def _stage_package(self, source_root: str | None = None) -> tuple[str, str]:
        os.makedirs(self._staging_root(), exist_ok=True)
        staging_root = tempfile.mkdtemp(prefix="publish-", dir=self._staging_root())
        package_root = os.path.join(staging_root, "package")
        try:
            if source_root:
                self._copy_publish_tree(source_root, package_root)
                self._make_tree_writable(package_root)
            else:
                os.makedirs(package_root, exist_ok=True)
        except Exception:
            self._remove_staging_tree(staging_root)
            raise
        return staging_root, package_root

    def _copy_publish_tree(self, source_root: str, target_root: str) -> None:
        source_root = self._normalize_package_root(source_root)
        if not os.path.isdir(source_root):
            raise ValueError(f"Directory does not exist: {source_root}")
        self._require_safe_import_tree(source_root)

        def ignore(_path: str, names: list[str]) -> set[str]:
            return {name for name in names if name in _REVISION_SKIP_DIRS}

        shutil.copytree(source_root, target_root, symlinks=False, ignore=ignore)

    def _publish_from_source_locked(
        self,
        skill_name: str,
        data: dict,
        *,
        current_registry: dict | None = None,
    ) -> dict:
        source_root = self._normalize_package_root(data.get("package_root", ""))
        if source_root and not os.path.isdir(source_root):
            raise ValueError(f"Directory does not exist: {source_root}")
        imported = self._read_skill_package(source_root) if source_root else None
        staging_root, package_root = self._stage_package(source_root or None)
        try:
            metadata = dict((imported or {}).get("metadata") or {})
            metadata.update(
                {
                    "name": skill_name,
                    "display_name": self._resolve_create_field(
                        data, "display_name", imported, default=""
                    ),
                    "description": self._resolve_create_field(
                        data, "description", imported, default=""
                    ),
                }
            )
            for key, value in data.items():
                if (
                    key
                    not in {
                        "name",
                        "display_name",
                        "description",
                        "instructions",
                        "package_root",
                    }
                    and value is not None
                ):
                    metadata[key] = value
            instructions = self._resolve_create_field(
                data, "instructions", imported, default=""
            )
            self._write_skill_md(package_root, metadata, instructions)
            published = self._publish_staged_locked(
                skill_name,
                staging_root,
                current_registry=current_registry,
            )
            staging_root = ""
            return published
        finally:
            if staging_root:
                self._remove_staging_tree(staging_root)

    def _publish_staged_locked(
        self,
        skill_name: str,
        staging_root: str,
        *,
        current_registry: dict | None,
    ) -> dict:
        package_root = os.path.join(staging_root, "package")
        loaded = self._load_skill_package(package_root)
        if loaded["name"] != skill_name:
            raise ValueError(
                f'Published package name "{loaded["name"]}" does not match "{skill_name}"'
            )
        revision, manifest = self._package_manifest(package_root)
        manifest_path = os.path.join(staging_root, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as file:
            json.dump(manifest, file, ensure_ascii=False, sort_keys=True)
            file.flush()
            os.fsync(file.fileno())

        os.makedirs(self._revisions_root(), exist_ok=True)
        target_revision_root = self._revision_directory(revision)
        if os.path.exists(target_revision_root):
            self._require_matching_revision_manifest(
                target_revision_root,
                revision,
                manifest,
            )
            self._remove_staging_tree(staging_root)
        else:
            self._make_tree_read_only(staging_root)
            # A directory itself must remain writable while it is renamed on
            # some filesystems. Children are already immutable and the root is
            # sealed immediately after it reaches its content-addressed path,
            # before the registry pointer can expose it.
            os.chmod(staging_root, 0o755)
            try:
                os.rename(staging_root, target_revision_root)
            except FileExistsError:
                self._require_matching_revision_manifest(
                    target_revision_root,
                    revision,
                    manifest,
                )
                self._remove_staging_tree(staging_root)
            else:
                os.chmod(target_revision_root, 0o555)
            self._fsync_directory(self._revisions_root())

        now = dt.datetime.now(dt.timezone.utc).isoformat()
        registry = {
            "format": 1,
            "name": skill_name,
            "current_revision": revision,
            "metadata": {
                "display_name": loaded.get("display_name", skill_name),
                "description": loaded.get("description", ""),
                "entry_file": loaded.get("entry_file", "SKILL.md"),
                "python_project": loaded.get("python_project", False),
            },
            "created_at": (
                current_registry.get("created_at", now)
                if current_registry is not None
                else now
            ),
            "updated_at": now,
        }
        self._write_registry_atomic(skill_name, registry)
        return self._load_published_skill(skill_name, registry=registry)

    def _write_registry_atomic(self, skill_name: str, registry: dict) -> None:
        registry_root = self._registry_root()
        os.makedirs(registry_root, exist_ok=True)
        temporary = os.path.join(
            registry_root,
            f".{skill_name}.{uuid.uuid4().hex}.tmp",
        )
        try:
            with open(temporary, "x", encoding="utf-8") as file:
                json.dump(
                    registry,
                    file,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self._registry_path(skill_name))
            self._fsync_directory(registry_root)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    @staticmethod
    def _make_tree_read_only(root: str) -> None:
        for current_root, dir_names, file_names in os.walk(root, topdown=False):
            for file_name in file_names:
                path = os.path.join(current_root, file_name)
                mode = stat.S_IMODE(os.stat(path, follow_symlinks=False).st_mode)
                os.chmod(path, 0o555 if mode & 0o111 else 0o444)
            for directory_name in dir_names:
                os.chmod(os.path.join(current_root, directory_name), 0o555)
        os.chmod(root, 0o555)

    @staticmethod
    def _make_tree_writable(root: str) -> None:
        for current_root, dir_names, file_names in os.walk(root):
            os.chmod(current_root, 0o755)
            for directory_name in dir_names:
                os.chmod(os.path.join(current_root, directory_name), 0o755)
            for file_name in file_names:
                path = os.path.join(current_root, file_name)
                mode = stat.S_IMODE(os.stat(path, follow_symlinks=False).st_mode)
                os.chmod(path, 0o755 if mode & 0o111 else 0o644)

    def _remove_staging_tree(self, root: str) -> None:
        if not os.path.exists(root):
            return
        try:
            self._make_tree_writable(root)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    @staticmethod
    def _require_matching_revision_manifest(
        revision_root: str,
        revision: str,
        expected_manifest: dict,
    ) -> None:
        existing_manifest = os.path.join(revision_root, "manifest.json")
        try:
            with open(existing_manifest, "r", encoding="utf-8") as file:
                if json.load(file) != expected_manifest:
                    raise ValueError(
                        f"Revision collision or corrupt manifest for {revision}"
                    )
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Published revision {revision} is corrupt") from exc

    @staticmethod
    def _fsync_directory(path: str) -> None:
        if os.name == "nt":  # pragma: no cover - directories cannot be fsynced
            return
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _ensure_legacy_packages_published(self) -> None:
        """One-time online upgrade from the former mutable directory layout."""

        os.makedirs(self.root, exist_ok=True)
        marker = os.path.join(self._store_root(), "legacy-import-complete")
        if os.path.isfile(marker):
            return
        with _exclusive_file_lock(os.path.join(self._locks_root(), "migration.lock")):
            if os.path.isfile(marker):
                return
            discovered: list[tuple[str, str]] = []
            for entry in sorted(os.scandir(self.root), key=lambda item: item.name):
                if entry.name == _STORE_DIRECTORY or not entry.is_dir(
                    follow_symlinks=False
                ):
                    continue
                discovered.extend(
                    self._discover_skill_directories(entry.path, max_depth=5)
                )
            for package_root, entry_file in discovered:
                try:
                    legacy = self._load_skill_package(package_root, entry_file)
                except Exception:
                    continue
                skill_name = legacy["name"]
                with self._skill_lock(skill_name):
                    if self._read_registry(skill_name) is not None:
                        continue
                    self._publish_from_source_locked(
                        skill_name,
                        {
                            "name": skill_name,
                            "package_root": package_root,
                            "display_name": legacy.get("display_name", ""),
                            "description": legacy.get("description", ""),
                            "instructions": legacy.get("instructions", ""),
                        },
                    )
                    registry = self._require_current_registry(skill_name)
                    registry["created_at"] = legacy.get(
                        "created_at", registry["created_at"]
                    )
                    registry["updated_at"] = legacy.get(
                        "updated_at", registry["updated_at"]
                    )
                    self._write_registry_atomic(skill_name, registry)
            os.makedirs(self._store_root(), exist_ok=True)
            temporary = f"{marker}.{uuid.uuid4().hex}.tmp"
            with open(temporary, "x", encoding="utf-8") as file:
                file.write("1\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, marker)
            self._fsync_directory(self._store_root())

    @staticmethod
    def _serialize_skill(skill: dict) -> dict:
        return {
            field: skill.get(field) for field in _PUBLIC_SKILL_FIELDS if field in skill
        }

    def _load_skill_package(
        self, package_root: str, entry_file: str = "SKILL.md"
    ) -> dict:
        package_root = self._normalize_package_root(package_root)
        entry_path = os.path.join(package_root, entry_file)
        content = _read_utf8_text_limited(
            entry_path,
            subject=f"Skill entry file {entry_file}",
        )

        metadata, instructions = parse_frontmatter(content)
        dir_name = os.path.basename(os.path.normpath(package_root))
        skill_name = self._validate_skill_name(metadata.get("name") or dir_name)
        stat = os.stat(entry_path)
        return {
            "name": skill_name,
            "display_name": str(metadata.get("display_name") or skill_name).strip(),
            "description": str(metadata.get("description") or "").strip(),
            "metadata": dict(metadata),
            "instructions": instructions,
            "package_root": package_root,
            "entry_file": entry_file,
            "python_project": any(
                os.path.isfile(os.path.join(package_root, filename))
                for filename in (
                    "requirements.txt",
                    "pyproject.toml",
                    "setup.py",
                    "setup.cfg",
                )
            )
            or os.path.isdir(os.path.join(package_root, ".venv")),
            "created_at": dt.datetime.fromtimestamp(
                stat.st_ctime, tz=dt.timezone.utc
            ).isoformat(),
            "updated_at": dt.datetime.fromtimestamp(
                stat.st_mtime, tz=dt.timezone.utc
            ).isoformat(),
        }

    def _read_skill_package(self, package_root: str) -> dict:
        entry = self._find_skill_entry(package_root)
        if entry is None:
            raise ValueError(f"No SKILL.md found in {package_root}")

        skill = self._load_skill_package(entry[0], entry[1])
        return {
            "entry_file": skill.get("entry_file", "SKILL.md"),
            "display_name": skill.get("display_name", ""),
            "description": skill.get("description", ""),
            "metadata": dict(skill.get("metadata") or {}),
            "instructions": skill.get("instructions", ""),
        }

    def _write_skill_md(
        self, package_root: str, metadata: dict, instructions: str
    ) -> None:
        package_root = self._normalize_package_root(package_root)
        os.makedirs(package_root, exist_ok=True)
        content = build_skill_md(metadata, instructions)
        with open(os.path.join(package_root, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(content)

    def _build_preview_target_dir(
        self, base_target_name: str, source_path: str, suffix: str
    ) -> str:
        relative = str(source_path or "").strip().replace("\\", "/").strip("/")
        leaf_name = relative.split("/")[-1] if relative else ""
        target_name = base_target_name
        if leaf_name and leaf_name != base_target_name:
            target_name = f"{base_target_name}-{leaf_name}"
        if suffix:
            target_name = f"{target_name}-{suffix}"
        return os.path.join(self.root, target_name)

    def _preview_skill_candidates(
        self,
        root_path: str,
        *,
        base_target_name: str,
        suffix: str,
        allow_root_package: bool = False,
    ) -> list[dict]:
        discovered = self._discover_skill_directories(root_path, max_depth=2)
        if not discovered:
            raise ValueError(
                f"No SKILL.md found in {root_path} or its subdirectories (max depth: 2)"
            )

        previews: list[dict] = []
        for package_root, entry_file in discovered:
            skill = self._load_skill_package(package_root, entry_file)
            relative_path = os.path.relpath(package_root, root_path)
            is_archive_root_skill = allow_root_package and relative_path in ("", ".")
            self._validate_agent_skill_package(
                package_root,
                skill.get("metadata") or {},
                require_directory_name=not is_archive_root_skill,
            )
            if relative_path in ("", "."):
                relative_path = ""
            skill["source_path"] = relative_path.replace(os.sep, "/")
            skill["package_root"] = self._build_preview_target_dir(
                base_target_name, relative_path, suffix
            )
            previews.append(skill)

        previews.sort(key=lambda item: item["source_path"])
        return [self._serialize_skill_with_source(preview) for preview in previews]

    @staticmethod
    def _validate_agent_skill_package(
        package_root: str, metadata: dict, *, require_directory_name: bool = True
    ) -> None:
        name = metadata.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"Skill package {package_root} must declare a frontmatter name"
            )
        name = name.strip()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            raise ValueError(
                "Skill name must use lowercase letters, numbers, and hyphens"
            )
        if len(name) > 64:
            raise ValueError("Skill name cannot exceed 64 characters")
        directory_name = os.path.basename(os.path.normpath(package_root))
        if require_directory_name and name != directory_name:
            raise ValueError(
                f'Skill frontmatter name "{name}" must match directory "{directory_name}"'
            )
        description = metadata.get("description")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(
                f'Skill "{name}" must declare a non-empty frontmatter description'
            )
        if len(description) > 1024:
            raise ValueError(
                f'Skill "{name}" description cannot exceed 1024 characters'
            )

    @staticmethod
    def _serialize_skill_with_source(skill: dict) -> dict:
        data = SkillStore._serialize_skill(skill)
        if "source_path" in skill:
            data["source_path"] = skill["source_path"]
        return data

    def _select_preview_candidates(
        self, previews: list[dict], data: dict
    ) -> list[dict]:
        normalized_paths: list[str] = []
        raw_source_paths = data.get("source_paths", [])
        if isinstance(raw_source_paths, list):
            for source_path in raw_source_paths:
                normalized = (
                    str(source_path or "").strip().replace("\\", "/").strip("/")
                )
                if normalized not in normalized_paths:
                    normalized_paths.append(normalized)

        legacy_source_path = (
            str(data.get("source_path", "") or "").strip().replace("\\", "/").strip("/")
        )
        if legacy_source_path and legacy_source_path not in normalized_paths:
            normalized_paths.append(legacy_source_path)

        if len(previews) == 1 and not normalized_paths:
            return previews

        if not normalized_paths:
            candidates = ", ".join(item["source_path"] or "." for item in previews)
            raise ValueError(
                f"Multiple skills found. Please choose one or more source_paths: {candidates}"
            )

        selected: list[dict] = []
        available = {preview["source_path"]: preview for preview in previews}
        for normalized_path in normalized_paths:
            preview = available.get(normalized_path)
            if preview is None:
                candidates = ", ".join(item["source_path"] or "." for item in previews)
                raise ValueError(
                    f'Invalid source_path "{normalized_path}". Available: {candidates}'
                )
            selected.append(preview)

        return selected

    def _install_preview_candidates(
        self,
        root_path: str,
        selected_previews: list[dict],
        *,
        allow_root_package: bool = False,
    ) -> list[dict]:
        installed: list[dict] = []
        try:
            for preview in selected_previews:
                source_root = self._preview_source_root(
                    root_path, preview["source_path"]
                )
                if preview["source_path"] or not allow_root_package:
                    scanned = SkillStore(self.root).scan_directory(source_root)
                else:
                    entry = self._find_skill_entry(source_root)
                    if entry is None:
                        raise ValueError(f"No SKILL.md found in {source_root}")
                    scanned = self._load_skill_package(entry[0], entry[1])
                    self._validate_agent_skill_package(
                        source_root,
                        scanned.get("metadata") or {},
                        require_directory_name=False,
                    )
                skill_name = self._validate_skill_name(scanned["name"])
                self._ensure_legacy_packages_published()
                with self._skill_lock(skill_name):
                    if self._read_registry(skill_name) is not None:
                        raise ValueError(
                            f'Skill with name "{skill_name}" already exists'
                        )
                    installed.append(
                        self._publish_from_source_locked(
                            skill_name,
                            {
                                "name": skill_name,
                                "display_name": scanned.get("display_name", ""),
                                "description": scanned.get("description", ""),
                                "instructions": scanned.get("instructions", ""),
                                "package_root": source_root,
                            },
                        )
                    )
        except Exception:
            for skill in installed:
                try:
                    self.delete_skill(skill["name"])
                except Exception:
                    pass
            raise

        return installed

    def _extract_uploaded_skill_to_temp(
        self, file_bytes: bytes, tmp_dir: str
    ) -> tuple[str, bool]:
        extract_dir = os.path.join(tmp_dir, "extracted")
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as zf:
                self._safe_extract_zip(zf, extract_dir)
        except zipfile.BadZipFile as exc:
            raise ValueError("Uploaded file must be a valid .zip archive") from exc

        entries = os.listdir(extract_dir)
        if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
            return os.path.join(extract_dir, entries[0]), False
        return extract_dir, True

    @staticmethod
    def _validate_zip_upload_size(file_bytes: bytes) -> None:
        if len(file_bytes) > _MAX_ZIP_COMPRESSED_BYTES:
            raise ValueError(
                "Uploaded archive exceeds the compressed size limit "
                f"({_MAX_ZIP_COMPRESSED_BYTES} bytes)"
            )

    @staticmethod
    def _uploaded_skill_target_stem(filename: str) -> str:
        stem = os.path.splitext(os.path.basename(str(filename or "").strip()))[0]
        safe_stem = "".join(
            ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in stem
        ).strip("-_")
        return safe_stem or "uploaded-skill"

    @staticmethod
    def _preview_source_root(root_path: str, source_path: str) -> str:
        normalized = str(source_path or "").strip().replace("\\", "/").strip("/")
        if not normalized:
            return root_path
        return os.path.join(root_path, normalized)

    @staticmethod
    def _resolve_source_subdir_root(root_path: str, source_subdir: str) -> str:
        normalized = str(source_subdir or "").strip().replace("\\", "/").strip("/")
        if not normalized:
            return root_path

        normalized_path = os.path.normpath(normalized)
        if (
            normalized_path.startswith("..")
            or normalized_path == ".."
            or os.path.isabs(normalized_path)
        ):
            raise ValueError("source_subdir must stay within the uploaded archive")

        target_root = os.path.realpath(os.path.join(root_path, normalized_path))
        archive_root = os.path.realpath(root_path)
        if target_root != archive_root and not target_root.startswith(
            f"{archive_root}{os.sep}"
        ):
            raise ValueError("source_subdir must stay within the uploaded archive")
        if not os.path.isdir(target_root):
            raise ValueError(
                f"source_subdir does not exist in the uploaded archive: {normalized}"
            )
        return target_root

    @staticmethod
    def _safe_extract_zip(archive: zipfile.ZipFile, target_dir: str) -> None:
        """Validate and stream-extract a bounded ZIP archive.

        ``ZipFile.extractall`` is intentionally avoided: all metadata limits are
        checked before the first file is written and every member is then copied
        through an explicit byte counter. This prevents path traversal, symlink
        materialization, metadata-only size lies, and decompression bombs.
        """

        target_root = os.path.realpath(target_dir)
        os.makedirs(target_root, exist_ok=True)
        members = archive.infolist()
        if len(members) > _MAX_ZIP_ENTRIES:
            raise ValueError(
                f"Archive contains too many entries (maximum {_MAX_ZIP_ENTRIES})"
            )

        validated: list[tuple[zipfile.ZipInfo, str, bool]] = []
        seen_paths: set[str] = set()
        total_compressed = 0
        total_uncompressed = 0
        for member in members:
            member_name = str(member.filename or "")
            if not member_name or "\x00" in member_name:
                raise ValueError("Archive contains an unsafe empty or NUL path")

            portable_name = member_name.replace("\\", "/")
            normalized = posixpath.normpath(portable_name)
            first_component = normalized.split("/", 1)[0]
            if (
                portable_name.startswith("/")
                or normalized in {"", ".", ".."}
                or normalized.startswith("../")
                or (len(first_component) >= 2 and first_component[1] == ":")
            ):
                raise ValueError(f"Archive contains an unsafe path: {member_name}")

            destination = os.path.realpath(
                os.path.join(target_root, *normalized.split("/"))
            )
            if destination != target_root and not destination.startswith(
                f"{target_root}{os.sep}"
            ):
                raise ValueError(f"Archive contains an unsafe path: {member_name}")

            destination_key = os.path.normcase(destination)
            if destination_key in seen_paths:
                raise ValueError(f"Archive contains a duplicate path: {member_name}")
            seen_paths.add(destination_key)

            unix_mode = (member.external_attr >> 16) & 0xFFFF
            file_type = stat.S_IFMT(unix_mode)
            is_directory = member.is_dir() or portable_name.endswith("/")
            if file_type == stat.S_IFLNK:
                raise ValueError(f"Archive contains a symbolic link: {member_name}")
            if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise ValueError(f"Archive contains a non-regular entry: {member_name}")
            if is_directory:
                if member.file_size != 0:
                    raise ValueError(
                        f"Archive directory has unexpected content: {member_name}"
                    )
                validated.append((member, destination, True))
                continue

            if member.file_size < 0 or member.compress_size < 0:
                raise ValueError(
                    f"Archive contains invalid size metadata: {member_name}"
                )
            if member.file_size > _MAX_ZIP_ENTRY_UNCOMPRESSED_BYTES:
                raise ValueError(
                    f"Archive entry exceeds the uncompressed size limit: {member_name}"
                )
            if member.file_size and (
                member.compress_size == 0
                or member.file_size / member.compress_size > _MAX_ZIP_COMPRESSION_RATIO
            ):
                raise ValueError(
                    f"Archive entry exceeds the compression ratio limit: {member_name}"
                )
            total_compressed += member.compress_size
            total_uncompressed += member.file_size
            if total_compressed > _MAX_ZIP_COMPRESSED_BYTES:
                raise ValueError("Archive exceeds the compressed size limit")
            if total_uncompressed > _MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES:
                raise ValueError("Archive exceeds the total uncompressed size limit")
            validated.append((member, destination, False))

        if total_uncompressed and (
            total_compressed == 0
            or total_uncompressed / total_compressed > _MAX_ZIP_COMPRESSION_RATIO
        ):
            raise ValueError("Archive exceeds the aggregate compression ratio limit")

        extracted_total = 0
        for member, destination, is_directory in validated:
            if is_directory:
                os.makedirs(destination, mode=0o755, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(destination), mode=0o755, exist_ok=True)
            extracted_entry = 0
            try:
                with (
                    archive.open(member, "r") as source,
                    open(destination, "xb") as target,
                ):
                    while True:
                        chunk = source.read(_ZIP_COPY_CHUNK_BYTES)
                        if not chunk:
                            break
                        extracted_entry += len(chunk)
                        extracted_total += len(chunk)
                        if extracted_entry > _MAX_ZIP_ENTRY_UNCOMPRESSED_BYTES:
                            raise ValueError(
                                "Archive entry exceeds the uncompressed size limit: "
                                f"{member.filename}"
                            )
                        if extracted_total > _MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES:
                            raise ValueError(
                                "Archive exceeds the total uncompressed size limit"
                            )
                        target.write(chunk)
            except Exception:
                try:
                    os.unlink(destination)
                except OSError:
                    pass
                raise
            if extracted_entry != member.file_size:
                raise ValueError(
                    f"Archive entry size changed while extracting: {member.filename}"
                )
            source_mode = (member.external_attr >> 16) & 0o777
            os.chmod(destination, 0o755 if source_mode & 0o111 else 0o644)

    def _resolve_skill_path(
        self, skill: dict, path: str, *, expect_directory: bool
    ) -> tuple[str, str]:
        package_root = self._normalize_package_root(skill.get("package_root", ""))
        if not package_root:
            raise ValueError(f'Skill "{skill.get("name", "")}" has no package_root')

        relative_path = str(path or ".").strip() or "."
        if os.path.isabs(relative_path):
            raise ValueError("path must be relative to the skill package root")

        normalized_relative = os.path.normpath(relative_path)
        if normalized_relative.startswith("..") or normalized_relative == "..":
            raise ValueError("path must stay within the skill package root")

        target_path = os.path.realpath(os.path.join(package_root, normalized_relative))
        if target_path != package_root and not target_path.startswith(
            f"{package_root}{os.sep}"
        ):
            raise ValueError("path must stay within the skill package root")

        if expect_directory:
            if not os.path.isdir(target_path):
                raise ValueError(f"Skill directory not found: {relative_path}")
        else:
            parent_dir = os.path.dirname(target_path) or package_root
            if parent_dir != package_root and not parent_dir.startswith(
                f"{package_root}{os.sep}"
            ):
                raise ValueError("path must stay within the skill package root")

        return target_path, normalized_relative

    @staticmethod
    def _find_skill_entry(path: str) -> Optional[tuple[str, str]]:
        for candidate in ("SKILL.md", "skill.md"):
            if os.path.isfile(os.path.join(path, candidate)):
                return path, candidate
        return None

    def _discover_skill_directories(
        self,
        root_path: str,
        max_depth: int = 2,
        *,
        max_scan_entries: int = _MAX_SKILL_SCAN_ENTRIES,
        max_skills: int = _MAX_DISCOVERED_SKILLS,
    ) -> list[tuple[str, str]]:
        discovered: list[tuple[str, str]] = []
        queue: collections.deque[tuple[str, int]] = collections.deque([(root_path, 0)])
        seen: set[str] = set()
        scanned_entries = 0

        while queue:
            current_path, depth = queue.popleft()
            normalized_path = os.path.abspath(current_path)
            if normalized_path in seen:
                continue
            seen.add(normalized_path)

            found = self._find_skill_entry(normalized_path)
            if found:
                discovered.append(found)
                if len(discovered) > max_skills:
                    raise ValueError(
                        "Skill discovery exceeded the configured package limit"
                    )
                continue

            if depth >= max_depth:
                continue

            try:
                with os.scandir(normalized_path) as iterator:
                    entries = []
                    for entry in iterator:
                        scanned_entries += 1
                        if scanned_entries > max_scan_entries:
                            raise ValueError(
                                "Skill discovery exceeded the configured entry limit"
                            )
                        entries.append(entry)
                entries.sort(key=lambda entry: entry.name)
            except OSError:
                continue

            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    queue.append((entry.path, depth + 1))

        return discovered

    @staticmethod
    def _validate_skill_name(name: str) -> str:
        name = str(name or "").strip()
        if not name:
            raise ValueError("Skill name is required")
        if not name.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                "Skill name can only contain letters, numbers, hyphens and underscores"
            )
        if len(name) > 64:
            raise ValueError("Skill name cannot exceed 64 characters")
        return name

    @staticmethod
    def _normalize_package_root(package_root: str) -> str:
        package_root = str(package_root).strip()
        if not package_root:
            return ""
        return os.path.realpath(os.path.abspath(package_root))

    @staticmethod
    def _resolve_create_field(
        data: dict, field: str, imported_skill_data: dict | None, *, default: str
    ) -> str:
        raw_value = data.get(field) if field in data else None
        if raw_value is None:
            if imported_skill_data is not None:
                return str(imported_skill_data.get(field, default) or default)
            return default

        value = str(raw_value or "")
        if imported_skill_data is not None and not value.strip():
            return str(imported_skill_data.get(field, default) or default)
        return value


__all__ = [
    "SkillRevisionConflictError",
    "SkillRevisionMismatchError",
    "SkillRevisionNotFoundError",
    "SkillStore",
    "build_skill_md",
    "parse_frontmatter",
    "skill_namespace",
]
