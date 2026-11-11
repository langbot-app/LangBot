"""Reusable plugin packaging helpers.

This module centralises the ``.lbpkg`` build logic that used to live inline in
``langbot_plugin.cli.commands.buildplugin``. Both the CLI (``lbp build`` /
``lbp publish``) and the Runtime (the "upload a debug plugin to LangBot Space"
flow) build packages from a plugin directory on disk, so the logic must not be
owned by either caller.

Unlike the historical CLI implementation, packaging here is *in-memory* and
never mutates the developer's ``manifest.yaml``: callers that want to publish
edited metadata pass ``manifest_overrides`` and the packaged manifest reflects
those edits while the on-disk file is left untouched.
"""

from __future__ import annotations

import fnmatch
import io
import os
import posixpath
import typing
import zipfile
from pathlib import Path

import yaml

from langbot_plugin.utils.discover.engine import ComponentDiscoveryEngine

# Files/directories that are always excluded from a package, regardless of
# ``.gitignore``. Mirrors the historical CLI exclusion list.
ALWAYS_EXCLUDED_NAMES = frozenset(
    {
        ".git",
        "*.lbpkg",
        ".env",
        "__pycache__",
        ".pytest_cache",
        ".coverage",
        "*.pyc",
        "*.pyo",
        "*.pyd",
    }
)

# Manifest fields a publisher may edit from the upload page. ``name`` stays a
# fixed identity field, while ``author`` is intentionally editable so a
# publisher can publish under a different account (the upload page surfaces this
# explicitly). ``license`` records the chosen open-source license.
EDITABLE_METADATA_FIELDS = ("author", "repository", "version", "icon", "license")


def parse_gitignore(gitignore_path: str | os.PathLike[str]) -> list[str]:
    """Parse a ``.gitignore`` file into a list of patterns."""

    patterns: list[str] = []
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
    return patterns


def should_ignore(path: str, gitignore_patterns: list[str]) -> bool:
    """Check if a path should be ignored based on ``.gitignore`` patterns."""

    normalized_path = str(Path(path)).replace(os.sep, "/")

    for pattern in gitignore_patterns:
        if not pattern:
            continue

        # Directory patterns (ending with /)
        if pattern.endswith("/"):
            dir_pattern = pattern[:-1]
            if (
                normalized_path.endswith(f"/{dir_pattern}")
                or normalized_path == dir_pattern
            ):
                return True
            if dir_pattern in normalized_path.split("/"):
                return True
        # Root-relative patterns (starting with /)
        elif pattern.startswith("/"):
            root_pattern = pattern[1:]
            if normalized_path.startswith(root_pattern):
                return True
        # Wildcard patterns
        elif "*" in pattern or "?" in pattern:
            if fnmatch.fnmatch(normalized_path, pattern):
                return True
            if fnmatch.fnmatch(os.path.basename(path), pattern):
                return True
        # Exact matches
        else:
            if normalized_path.endswith(f"/{pattern}") or normalized_path == pattern:
                return True
            if pattern in normalized_path.split("/"):
                return True

    return False


def _localized_override(value: typing.Any) -> typing.Any:
    """Normalise a metadata override into the manifest i18n shape.

    The upload page sends a single string for label/description; the manifest
    stores an ``{en_US: ..., zh_Hans: ...}`` mapping. A mapping is passed
    through unchanged so callers can target specific locales.
    """

    if value is None:
        return None
    if isinstance(value, dict):
        return value
    text = str(value)
    return {
        "en_US": text,
        "zh_Hans": text,
        "th_TH": text,
        "vi_VN": text,
        "es_ES": text,
    }


def apply_manifest_overrides(
    manifest: dict[str, typing.Any],
    overrides: dict[str, typing.Any] | None,
) -> dict[str, typing.Any]:
    """Return a copy of ``manifest`` with publisher edits applied.

    ``label``/``description`` plus the fields in ``EDITABLE_METADATA_FIELDS``
    (``author``/``repository``/``version``/``icon``/``license``) are accepted.
    Unknown keys are ignored so a stale frontend cannot smuggle arbitrary
    manifest fields into a published package.
    """

    if not overrides:
        return manifest

    result = dict(manifest)
    metadata = dict(result.get("metadata") or {})

    label = _localized_override(overrides.get("label"))
    if label is not None:
        metadata["label"] = label

    description = _localized_override(overrides.get("description"))
    if description is not None:
        metadata["description"] = description

    for field in EDITABLE_METADATA_FIELDS:
        if field in overrides and overrides[field] is not None:
            metadata[field] = str(overrides[field])

    result["metadata"] = metadata

    return result


def load_plugin_manifest(
    plugin_root: str,
) -> tuple[ComponentDiscoveryEngine, typing.Any]:
    """Load and validate the plugin manifest under ``plugin_root``."""

    manifest_path = os.path.join(plugin_root, "manifest.yaml")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError("manifest.yaml not found")

    discovery_engine = ComponentDiscoveryEngine()
    plugin_manifest = discovery_engine.load_component_manifest(
        path=manifest_path,
        owner="builtin",
        no_save=True,
    )
    if plugin_manifest is None:
        raise ValueError("Invalid plugin manifest")
    return discovery_engine, plugin_manifest


def build_plugin_package(
    plugin_root: str,
    *,
    manifest_overrides: dict[str, typing.Any] | None = None,
    extra_files: dict[str, bytes] | None = None,
) -> tuple[bytes, str]:
    """Build a ``.lbpkg`` for the plugin at ``plugin_root`` in memory.

    Args:
        plugin_root: Directory containing ``manifest.yaml``.
        manifest_overrides: Optional ``label`` / ``description`` / ``author`` /
            ``version`` / ``repository`` / ``icon`` / ``license`` edits applied to
            the packaged manifest only.
        extra_files: Optional mapping of archive-relative path -> bytes, used to
            inject a replacement icon without mutating the source tree.

    Returns:
        A ``(package_bytes, filename)`` tuple.
    """

    plugin_root = os.path.abspath(plugin_root)
    discovery_engine, plugin_manifest = load_plugin_manifest(plugin_root)

    # Imported lazily: these helpers live under ``cli``, whose package
    # initialiser imports the CLI commands (which import this module). A
    # top-level import here would be circular.
    from langbot_plugin.cli.utils.page_components import (
        discover_plugin_components,
        populate_plugin_pages,
    )

    component_manifests = discover_plugin_components(plugin_manifest, discovery_engine)
    populate_plugin_pages(plugin_manifest, component_manifests)

    packaging_manifest = apply_manifest_overrides(
        plugin_manifest.manifest,
        manifest_overrides,
    )

    metadata = packaging_manifest.get("metadata") or {}
    plugin_author = str(metadata.get("author") or "unknown")
    plugin_name = str(metadata.get("name") or "plugin")
    plugin_version = str(metadata.get("version") or "0.0.0")

    filename = f"{plugin_author}-{plugin_name}-{plugin_version}.lbpkg"

    gitignore_patterns = parse_gitignore(os.path.join(plugin_root, ".gitignore"))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr(
            "manifest.yaml",
            yaml.safe_dump(
                packaging_manifest,
                allow_unicode=True,
                sort_keys=False,
            ),
        )

        for root, dirs, files in os.walk(plugin_root):
            dirs_to_remove = []
            for directory in dirs:
                dir_path = os.path.join(root, directory)
                relative_dir_path = os.path.relpath(dir_path, plugin_root)
                if should_ignore(relative_dir_path, gitignore_patterns) or any(
                    fnmatch.fnmatch(directory, pattern)
                    for pattern in ALWAYS_EXCLUDED_NAMES
                ):
                    dirs_to_remove.append(directory)
            for directory in dirs_to_remove:
                dirs.remove(directory)

            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, plugin_root)

                if relative_path == "manifest.yaml":
                    continue
                if should_ignore(relative_path, gitignore_patterns):
                    continue
                if any(
                    fnmatch.fnmatch(file, pattern) for pattern in ALWAYS_EXCLUDED_NAMES
                ):
                    continue

                zipf.write(file_path, relative_path)

        # Inject replacement files (e.g. an uploaded icon) last so they take
        # precedence over any same-named source file without mutating the tree.
        written: set[str] = set()
        for raw_path, data in (extra_files or {}).items():
            safe_path = safe_archive_relative_path(raw_path)
            if not safe_path or safe_path == "manifest.yaml" or safe_path in written:
                continue
            written.add(safe_path)
            zipf.writestr(safe_path, data)

    return buffer.getvalue(), filename


def read_plugin_manifest_metadata(plugin_root: str) -> dict[str, typing.Any]:
    """Read the raw manifest metadata for form pre-fill."""

    manifest_path = os.path.join(plugin_root, "manifest.yaml")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError("manifest.yaml not found")
    with open(manifest_path, "r", encoding="utf-8") as file:
        manifest = yaml.safe_load(file) or {}
    return manifest


def write_manifest_overrides(
    plugin_root: str,
    overrides: dict[str, typing.Any] | None,
) -> None:
    """Persist publisher edits into the on-disk ``manifest.yaml``.

    Used before a Git commit so the synchronised repository records the same
    metadata that is published to LangBot Space.
    """

    if not overrides:
        return

    manifest_path = os.path.join(plugin_root, "manifest.yaml")
    with open(manifest_path, "r", encoding="utf-8") as file:
        manifest = yaml.safe_load(file) or {}

    updated = apply_manifest_overrides(manifest, overrides)
    with open(manifest_path, "w", encoding="utf-8") as file:
        yaml.safe_dump(updated, file, allow_unicode=True, sort_keys=False)


def write_extra_files(
    plugin_root: str,
    extra_files: dict[str, bytes] | None,
) -> None:
    """Materialise replacement files into the working tree.

    Used before a Git commit so the synchronised repository contains the same
    icon (and any other injected file) that is published to LangBot Space.
    """

    if not extra_files:
        return

    for raw_path, data in extra_files.items():
        safe_path = safe_archive_relative_path(raw_path)
        if not safe_path or safe_path == "manifest.yaml":
            continue
        destination = os.path.join(plugin_root, *safe_path.split("/"))
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        with open(destination, "wb") as file:
            file.write(data)


def safe_archive_relative_path(raw: str) -> str | None:
    """Return a normalised, traversal-free archive path or ``None``."""

    normalized = str(raw or "").replace("\\", "/")
    normalized = posixpath.normpath(normalized)
    if normalized in (".", "") or normalized.startswith("../") or normalized == "..":
        return None
    return normalized
