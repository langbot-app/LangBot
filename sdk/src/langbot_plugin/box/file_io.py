"""Bounded, descriptor-relative file IO for a sandbox workspace."""

from __future__ import annotations

import contextlib
import io
import json
import os
import posixpath
import shutil
import stat
import uuid
import zipfile


def workspace_usage(
    root: str, stop_after_bytes: int, max_entries: int
) -> tuple[int, int, bool]:
    """Bound a no-follow workspace scan by both bytes and directory entries."""
    if os.name == "nt":
        from .windows_file_io import usage

        return usage(root, stop_after_bytes, max_entries)
    _require_descriptor_io()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW

    def scan(descriptor):
        try:
            return descriptor, os.scandir(descriptor)
        except BaseException:
            os.close(descriptor)
            raise

    stack = [scan(os.open(root, flags))]
    total = entries = 0
    try:
        while stack:
            directory, iterator = stack[-1]
            entry = next(iterator, None)
            if entry is None:
                iterator.close()
                os.close(directory)
                stack.pop()
                continue
            entries += 1
            if entries > max_entries:
                return total, entries, True
            try:
                info = os.stat(entry.name, dir_fd=directory, follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    child = os.open(entry.name, flags, dir_fd=directory)
                    stack.append(scan(child))
                else:
                    total += info.st_size
            except FileNotFoundError:
                continue
            if total > stop_after_bytes:
                return total, entries, False
        return total, entries, False
    finally:
        for directory, iterator in reversed(stack):
            iterator.close()
            os.close(directory)


def run_files_cleanup_script(io_scope: str) -> str:
    """Remove one run's IO directories without following sandbox symlinks."""
    return f"""import os, stat
scope = {json.dumps(io_scope)}
flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
def remove(parent, name):
    info = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode):
        os.unlink(name, dir_fd=parent)
        return
    child = os.open(name, flags, dir_fd=parent)
    try:
        current = os.fstat(child)
        if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
            raise ValueError('Run cleanup directory changed')
        with os.scandir(child) as entries:
            for entry in entries:
                remove(child, entry.name)
    finally:
        os.close(child)
    os.rmdir(name, dir_fd=parent)
root = os.open('/workspace', flags)
try:
    for name in ('inbox', 'outbox', '.langbot-snapshots'):
        try:
            parent = os.open(name, flags, dir_fd=root)
        except FileNotFoundError:
            continue
        try:
            try:
                info = os.stat(scope, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                continue
            remove(parent, scope)
        finally:
            os.close(parent)
finally:
    os.close(root)
"""


def run_files_present(owner: tuple[str, int, int], io_scope: str) -> bool:
    """Check one run without following links; uncertainty requires sandbox cleanup."""
    if os.name == "nt":
        from .windows_file_io import run_files

        return run_files(owner, io_scope)
    _require_descriptor_io()
    root, device, inode = owner
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        with _parent_directory(root, "unused", create=False) as (root_fd, _name):
            info = os.fstat(root_fd)
            if (info.st_dev, info.st_ino) != (device, inode):
                return True
            for parent in ("inbox", "outbox", ".langbot-snapshots"):
                try:
                    directory = os.open(parent, flags, dir_fd=root_fd)
                except FileNotFoundError:
                    continue
                try:
                    try:
                        os.stat(io_scope, dir_fd=directory, follow_symlinks=False)
                    except FileNotFoundError:
                        continue
                    return True
                finally:
                    os.close(directory)
    except OSError:
        return True
    return False


def workspace_relative_path(mount_path: str, path: str) -> str:
    for value in (mount_path, path):
        if (
            not isinstance(value, str)
            or not value.startswith("/")
            or "\\" in value
            or "\x00" in value
            or posixpath.normpath(value) != value
            or (
                value != "/"
                and any(part in ("", ".", "..") for part in value.split("/")[1:])
            )
        ):
            raise ValueError("File path must be a normalized absolute POSIX path")
    prefix = mount_path.rstrip("/") + "/"
    if not path.startswith(prefix):
        raise ValueError("File path must stay inside the session workspace")
    return path[len(prefix) :]


def _require_descriptor_io() -> None:
    if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
        raise ValueError("Workspace file transfer requires descriptor-relative file IO")


@contextlib.contextmanager
def _parent_directory(root: str, relative: str, *, create: bool):
    _require_descriptor_io()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    current = os.open("/", flags)
    try:
        for part in root.split("/") + relative.split("/")[:-1]:
            if not part:
                continue
            if part in (".", ".."):
                raise ValueError("Invalid workspace file path")
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=current)
                except FileExistsError:
                    pass
            child = os.open(part, flags, dir_fd=current)
            os.close(current)
            current = child
        yield current, relative.split("/")[-1]
    finally:
        os.close(current)


def read_workspace_file(root: str, relative: str, max_bytes: int) -> bytes:
    if os.name == "nt":
        from .windows_file_io import read

        return read(root, relative, max_bytes)
    with _parent_directory(root, relative, create=False) as (directory, name):
        fd = os.open(
            name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
        )
        with os.fdopen(fd, "rb") as file:
            info = os.fstat(file.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError(
                    "Workspace transfer requires a regular file with one link"
                )
            if info.st_size > max_bytes:
                raise ValueError("Workspace file exceeds the transfer size limit")
            content = file.read(max_bytes + 1)
            if len(content) > max_bytes:
                raise ValueError("Workspace file exceeds the transfer size limit")
            return content


def archive_workspace_directory(root: str, relative: str, max_bytes: int) -> bytes:
    """Read a bounded, stable directory tree without links or workspace staging."""
    if (
        not isinstance(relative, str)
        or "\\" in relative
        or "\x00" in relative
        or (
            relative
            and (
                relative.startswith("/")
                or posixpath.normpath(relative) != relative
                or any(part in ("", ".", "..") for part in relative.split("/"))
            )
        )
    ):
        raise ValueError("Directory path must stay inside the session workspace")
    if type(max_bytes) is not int or max_bytes < 0:
        raise ValueError("Directory archive size limit must be nonnegative")
    limit = min(max_bytes, 20 * 1024 * 1024)
    if os.name == "nt":
        from .windows_file_io import archive_directory

        return archive_directory(root, relative, limit)
    _require_descriptor_io()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW

    def identity(info):
        return (
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        )

    class BoundedArchive(io.BytesIO):
        def write(self, data):
            if self.tell() + len(data) > limit:
                raise ValueError("Directory archive exceeds the transfer size limit")
            return super().write(data)

    source_path = relative + "/unused" if relative else "unused"
    with _parent_directory(root, source_path, create=False) as (source_fd, _name):
        entries = []
        directories = []
        total = 0

        def source_entry(path, is_directory):
            descriptor = os.dup(source_fd)
            try:
                parts = path.split("/")
                for part in parts[:-1]:
                    child = os.open(part, flags, dir_fd=descriptor)
                    os.close(descriptor)
                    descriptor = child
                return os.open(
                    parts[-1],
                    flags
                    if is_directory
                    else os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                    dir_fd=descriptor,
                )
            finally:
                os.close(descriptor)

        def scan(descriptor, prefix="", depth=0):
            nonlocal total
            if depth > 16:
                raise ValueError("Directory archive exceeds the depth limit (16)")
            names = set()
            directories.append((prefix, identity(os.fstat(descriptor)), names))
            with os.scandir(descriptor) as children:
                for child in children:
                    names.add(child.name)
                    path = prefix + child.name
                    if (
                        "\\" in child.name
                        or "\x00" in child.name
                        or (
                            not prefix and len(child.name) >= 2 and child.name[1] == ":"
                        )
                    ):
                        raise ValueError("Unsafe directory archive path: " + path)
                    if len(entries) >= 512:
                        raise ValueError(
                            "Directory archive exceeds the entry limit (512)"
                        )
                    info = child.stat(follow_symlinks=False)
                    is_directory = stat.S_ISDIR(info.st_mode)
                    if not is_directory:
                        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                            raise ValueError(
                                "Directory contains a link or special file: " + path
                            )
                        if info.st_size > 16 * 1024 * 1024:
                            raise ValueError(
                                "Directory file exceeds the size limit: " + path
                            )
                        total += info.st_size
                        if total > 64 * 1024 * 1024:
                            raise ValueError(
                                "Directory archive exceeds the expanded size limit"
                            )
                    entries.append((path, info, is_directory))
                    if is_directory:
                        child_fd = os.open(child.name, flags, dir_fd=descriptor)
                        try:
                            if identity(os.fstat(child_fd)) != identity(info):
                                raise ValueError("Directory changed: " + path)
                            scan(child_fd, path + "/", depth + 1)
                        finally:
                            os.close(child_fd)

        scan(source_fd)
        with BoundedArchive() as output:
            with zipfile.ZipFile(
                output, "w", compression=zipfile.ZIP_STORED, allowZip64=False
            ) as archive:
                for path, expected, is_directory in entries:
                    member = zipfile.ZipInfo(path + "/" if is_directory else path)
                    member.create_system = 3
                    mode = (
                        stat.S_IFDIR | 0o755
                        if is_directory
                        else stat.S_IFREG
                        | (0o755 if expected.st_mode & 0o111 else 0o644)
                    )
                    member.external_attr = mode << 16
                    if is_directory:
                        archive.writestr(member, b"")
                        continue
                    with os.fdopen(source_entry(path, False), "rb") as source:
                        before = os.fstat(source.fileno())
                        if (
                            not stat.S_ISREG(before.st_mode)
                            or before.st_nlink != 1
                            or identity(before) != identity(expected)
                        ):
                            raise ValueError("Directory file changed: " + path)
                        copied = 0
                        with archive.open(member, "w") as target:
                            while True:
                                chunk = source.read(65536)
                                if not chunk:
                                    break
                                copied += len(chunk)
                                if copied > expected.st_size:
                                    raise ValueError("Directory file changed: " + path)
                                target.write(chunk)
                        if copied != expected.st_size or identity(
                            os.fstat(source.fileno())
                        ) != identity(expected):
                            raise ValueError("Directory file changed: " + path)

            for path, expected, names in directories:
                descriptor = (
                    source_entry(path.rstrip("/"), True) if path else os.dup(source_fd)
                )
                try:
                    if identity(os.fstat(descriptor)) != expected:
                        raise ValueError("Directory changed: " + path)
                    remaining = set(names)
                    with os.scandir(descriptor) as children:
                        for child in children:
                            if child.name not in remaining:
                                raise ValueError("Directory changed: " + path)
                            remaining.remove(child.name)
                    if remaining:
                        raise ValueError("Directory changed: " + path)
                finally:
                    os.close(descriptor)
            for path, expected, is_directory in entries:
                if is_directory:
                    continue
                descriptor = source_entry(path, False)
                try:
                    current = os.fstat(descriptor)
                    if (
                        not stat.S_ISREG(current.st_mode)
                        or current.st_nlink != 1
                        or identity(current) != identity(expected)
                    ):
                        raise ValueError("Directory file changed: " + path)
                finally:
                    os.close(descriptor)
            return output.getvalue()


def clear_workspace_directory(root: str, device: int, inode: int) -> None:
    """Clear an identity-bound workspace without following links or other devices."""
    if os.name == "nt":
        from .windows_file_io import clear

        return clear((root, device, inode))
    _require_descriptor_io()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    entries = 0

    def clear(directory):
        nonlocal entries
        with os.scandir(directory) as children:
            for child in children:
                entries += 1
                if entries > 100_000:
                    raise ValueError("Workspace cleanup exceeds the entry limit")
                expected = child.stat(follow_symlinks=False)
                if not stat.S_ISDIR(expected.st_mode):
                    os.unlink(child.name, dir_fd=directory)
                    continue
                if expected.st_dev != device:
                    raise ValueError("Workspace cleanup cannot cross a filesystem")
                descriptor = os.open(child.name, flags, dir_fd=directory)
                try:
                    current = os.fstat(descriptor)
                    if (current.st_dev, current.st_ino) != (
                        expected.st_dev,
                        expected.st_ino,
                    ):
                        raise ValueError("Workspace cleanup directory changed")
                    clear(descriptor)
                    current = os.stat(
                        child.name, dir_fd=directory, follow_symlinks=False
                    )
                    if (current.st_dev, current.st_ino) != (
                        expected.st_dev,
                        expected.st_ino,
                    ):
                        raise ValueError("Workspace cleanup directory changed")
                    os.rmdir(child.name, dir_fd=directory)
                finally:
                    os.close(descriptor)

    with _parent_directory(root, "unused", create=False) as (directory, _name):
        info = os.fstat(directory)
        if (info.st_dev, info.st_ino) != (device, inode):
            raise ValueError("Runtime workspace ownership changed during cleanup")
        clear(directory)


def remove_owned_workspace(
    owner: tuple[str, int, int], *, empty_only: bool = False
) -> None:
    """Remove only the workspace still matching Runtime's allocated identity."""
    if os.name == "nt":
        from .windows_file_io import remove_owned

        return remove_owned(owner, empty_only)
    path, device, inode = owner
    try:
        os.stat(path, follow_symlinks=False)
    except FileNotFoundError:
        return
    parent_path, name = posixpath.split(path)
    with _parent_directory(parent_path, name, create=False) as (parent, _name):
        try:
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return
        if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != (
            device,
            inode,
        ):
            raise ValueError("Runtime workspace ownership changed during cleanup")
        if empty_only:
            os.rmdir(name, dir_fd=parent)
        else:
            shutil.rmtree(path)


def write_workspace_file(
    root: str, relative: str, content: bytes, max_bytes: int
) -> None:
    if len(content) > max_bytes:
        raise ValueError("Workspace file exceeds the transfer size limit")
    if os.name == "nt":
        from .windows_file_io import write

        return write(root, relative, content)
    with _parent_directory(root, relative, create=True) as (directory, name):
        try:
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError(
                    "Workspace target must be a regular file with one link"
                )
        temporary = ".langbot-transfer-" + uuid.uuid4().hex
        fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory,
        )
        try:
            with os.fdopen(fd, "wb") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
        finally:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
