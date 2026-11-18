"""Filesystem usage helpers shared by LangBot-managed runtimes.

The scanner deliberately does not follow symbolic links. Runtime storage roots
can contain user-controlled files, so following a link here could both escape
the managed directory and make a diagnostic request unexpectedly expensive.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any, Iterable


StorageRoot = tuple[str, Path, str, str | None]


def collect_storage_directories(roots: Iterable[StorageRoot]) -> list[dict[str, Any]]:
    """Collect size and file counts for logical runtime-owned directories.

    Each root is ``(key, path, kind, parent_key)``. ``kind == "root"`` marks
    independent storage included in the process total; ``detail`` entries are
    useful subdirectories whose bytes are already included in their parent.
    """

    return [
        _collect_storage_directory(
            key=key,
            path=Path(path),
            kind=kind,
            parent_key=parent_key,
        )
        for key, path, kind, parent_key in roots
    ]


def storage_total_bytes(directories: Iterable[dict[str, Any]]) -> int:
    return sum(
        int(item.get("size_bytes") or 0)
        for item in directories
        if item.get("kind") == "root"
    )


def _collect_storage_directory(
    *,
    key: str,
    path: Path,
    kind: str,
    parent_key: str | None,
) -> dict[str, Any]:
    size_bytes = 0
    file_count = 0
    error_count = 0
    exists = False

    try:
        root_stat = path.lstat()
        exists = True
    except (FileNotFoundError, NotADirectoryError):
        root_stat = None
    except OSError:
        root_stat = None
        error_count = 1

    if root_stat is not None:
        if not _is_traversable_directory(root_stat):
            size_bytes = int(root_stat.st_size)
            file_count = 1
        else:
            stack = [path]
            while stack:
                current = stack.pop()
                try:
                    with os.scandir(current) as entries:
                        for entry in entries:
                            try:
                                entry_stat = entry.stat(follow_symlinks=False)
                            except (FileNotFoundError, NotADirectoryError):
                                continue
                            except OSError:
                                error_count += 1
                                continue
                            if _is_traversable_directory(entry_stat):
                                stack.append(Path(entry.path))
                                continue
                            size_bytes += int(entry_stat.st_size)
                            file_count += 1
                except (FileNotFoundError, NotADirectoryError):
                    continue
                except OSError:
                    error_count += 1

    result: dict[str, Any] = {
        "key": key,
        "path": str(path),
        "kind": kind,
        "exists": exists,
        "size_bytes": size_bytes,
        "file_count": file_count,
        "error_count": error_count,
    }
    if parent_key is not None:
        result["parent_key"] = parent_key
    return result


def _is_traversable_directory(value: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    file_attributes = int(getattr(value, "st_file_attributes", 0) or 0)
    return stat.S_ISDIR(value.st_mode) and not (
        reparse_flag and file_attributes & reparse_flag
    )
