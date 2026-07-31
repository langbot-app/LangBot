from __future__ import annotations

import contextlib
import errno
import os
import stat
from collections.abc import Iterable


class UnsafeWorkspacePathError(OSError):
    """A tenant-controlled path could not be opened without following links."""


_DIRECTORY_FLAGS = (
    os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
)
_FILE_READ_FLAGS = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
_FILE_WRITE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
_MAX_REMOVAL_ENTRIES = 4096
_MAX_REMOVAL_DEPTH = 16


def _component(value: str) -> str:
    normalized = str(value or '').strip()
    if (
        not normalized
        or normalized in {'.', '..'}
        or '/' in normalized
        or '\\' in normalized
        or '\x00' in normalized
        or len(os.fsencode(normalized)) > 240
    ):
        raise UnsafeWorkspacePathError('Unsafe Workspace path component')
    return normalized


def _unsafe(path: str, exc: BaseException | None = None) -> UnsafeWorkspacePathError:
    error = UnsafeWorkspacePathError(f'Workspace path is not a link-free directory: {path}')
    if exc is not None:
        error.__cause__ = exc
    return error


@contextlib.contextmanager
def _root_fd(root: str):
    try:
        fd = os.open(root, _DIRECTORY_FLAGS)
    except OSError as exc:
        raise _unsafe(root, exc)
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise _unsafe(root)
        yield fd
    finally:
        os.close(fd)


def _open_dir_at(parent_fd: int, name: str, *, create: bool) -> int:
    name = _component(name)
    if create:
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
    try:
        fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
    except OSError as exc:
        raise _unsafe(name, exc)
    if not stat.S_ISDIR(os.fstat(fd).st_mode):
        os.close(fd)
        raise _unsafe(name)
    return fd


def _remove_entry(
    parent_fd: int,
    name: str,
    *,
    budget: list[int] | None = None,
    depth: int = 0,
) -> None:
    """Remove an entry recursively without following a symlink at any depth."""

    name = _component(name)
    budget = budget if budget is not None else [_MAX_REMOVAL_ENTRIES]
    if depth > _MAX_REMOVAL_DEPTH or budget[0] <= 0:
        raise UnsafeWorkspacePathError('Workspace cleanup exceeded its inode budget')
    budget[0] -= 1
    for _ in range(4):
        try:
            child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
        except FileNotFoundError:
            return
        except OSError as exc:
            if exc.errno not in {errno.ELOOP, errno.ENOTDIR, errno.EACCES}:
                raise
            try:
                os.unlink(name, dir_fd=parent_fd)
                return
            except FileNotFoundError:
                return
            except IsADirectoryError:
                continue
        else:
            try:
                _clear_dir(child_fd, budget=budget, depth=depth + 1)
            finally:
                os.close(child_fd)
            try:
                os.rmdir(name, dir_fd=parent_fd)
                return
            except FileNotFoundError:
                return
            except NotADirectoryError:
                continue
    raise UnsafeWorkspacePathError('Workspace entry changed while it was being removed')


def _clear_dir(directory_fd: int, *, budget: list[int], depth: int) -> None:
    # ``scandir(fd)`` enumerates the already-open directory. Names are then
    # resolved relative to the same fd, so a tenant cannot redirect the walk by
    # swapping an ancestor symlink between validation and use.
    # Do not materialize the whole directory: an attacker-controlled outbox
    # may contain an inode bomb even when its byte size is tiny. Removal is
    # deliberately budgeted and fails closed once the per-operation cap is
    # reached; hard filesystem/inode quota remains a Cloud readiness gate.
    with os.scandir(directory_fd) as iterator:
        for entry in iterator:
            _remove_entry(directory_fd, entry.name, budget=budget, depth=depth)


@contextlib.contextmanager
def _query_fd(root: str, subdir: str, query_key: str, *, create: bool, reset: bool = False):
    subdir = _component(subdir)
    query_key = _component(query_key)
    with _root_fd(root) as root_fd:
        subdir_fd = _open_dir_at(root_fd, subdir, create=create)
        try:
            if reset:
                _remove_entry(subdir_fd, query_key)
            query_fd = _open_dir_at(subdir_fd, query_key, create=create)
            try:
                yield query_fd
            finally:
                os.close(query_fd)
        finally:
            os.close(subdir_fd)


def write_files(
    root: str,
    subdir: str,
    query_key: str,
    files: Iterable[tuple[str, bytes]],
) -> None:
    """Atomically recreate one query directory and write regular files only."""

    with _query_fd(root, subdir, query_key, create=True, reset=True) as query_fd:
        for raw_name, data in files:
            name = _component(raw_name)
            try:
                file_fd = os.open(name, _FILE_WRITE_FLAGS, 0o600, dir_fd=query_fd)
            except OSError as exc:
                raise UnsafeWorkspacePathError(f'Could not create a link-free Workspace file: {name}') from exc
            with os.fdopen(file_fd, 'wb') as file_obj:
                file_obj.write(data)


def _read_directory(
    directory_fd: int,
    *,
    prefix: str,
    max_file_bytes: int,
    max_files: int,
    max_total_bytes: int,
    output: list[tuple[str, bytes]],
    total: list[int],
    remaining_entries: list[int],
    remaining_directories: list[int],
    depth: int,
) -> None:
    if depth > 8:
        return
    with os.scandir(directory_fd) as iterator:
        for entry in iterator:
            if len(output) >= max_files or total[0] >= max_total_bytes:
                return
            if remaining_entries[0] <= 0:
                raise UnsafeWorkspacePathError('Sandbox outbox exceeds the directory-entry limit')
            remaining_entries[0] -= 1
            name = _component(entry.name)
            relative = f'{prefix}/{name}' if prefix else name
            if entry.is_symlink():
                continue
            if entry.is_dir(follow_symlinks=False):
                if remaining_directories[0] <= 0:
                    raise UnsafeWorkspacePathError('Sandbox outbox exceeds the directory limit')
                remaining_directories[0] -= 1
                try:
                    child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=directory_fd)
                except OSError:
                    continue
                try:
                    _read_directory(
                        child_fd,
                        prefix=relative,
                        max_file_bytes=max_file_bytes,
                        max_files=max_files,
                        max_total_bytes=max_total_bytes,
                        output=output,
                        total=total,
                        remaining_entries=remaining_entries,
                        remaining_directories=remaining_directories,
                        depth=depth + 1,
                    )
                finally:
                    os.close(child_fd)
                continue
            try:
                file_fd = os.open(name, _FILE_READ_FLAGS, dir_fd=directory_fd)
            except OSError:
                continue
            try:
                metadata = os.fstat(file_fd)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > max_file_bytes:
                    continue
                remaining = max_total_bytes - total[0]
                if metadata.st_size > remaining:
                    continue
                with os.fdopen(file_fd, 'rb', closefd=False) as file_obj:
                    data = file_obj.read(max_file_bytes + 1)
                if len(data) > max_file_bytes or len(data) > remaining:
                    continue
                output.append((relative, data))
                total[0] += len(data)
            finally:
                os.close(file_fd)


def read_regular_files(
    root: str,
    subdir: str,
    query_key: str,
    *,
    max_file_bytes: int,
    max_files: int,
    max_total_bytes: int,
    max_entries: int = 512,
    max_directories: int = 64,
) -> list[tuple[str, bytes]]:
    """Read bounded regular files without following tenant-created links."""

    output: list[tuple[str, bytes]] = []
    try:
        with _query_fd(root, subdir, query_key, create=False) as query_fd:
            _read_directory(
                query_fd,
                prefix='',
                max_file_bytes=max_file_bytes,
                max_files=max_files,
                max_total_bytes=max_total_bytes,
                output=output,
                total=[0],
                remaining_entries=[max_entries],
                remaining_directories=[max_directories],
                depth=0,
            )
    except (FileNotFoundError, UnsafeWorkspacePathError):
        # A missing directory is an empty outbox. An unsafe existing path is
        # deliberately surfaced to the caller rather than followed.
        if os.path.lexists(os.path.join(root, subdir, query_key)):
            raise
    return output


def reset_directory(root: str, subdir: str, query_key: str) -> None:
    with _query_fd(root, subdir, query_key, create=True, reset=True):
        return


def purge_subdirectory(root: str, subdir: str) -> None:
    """Remove one known subtree without following a hostile replacement link."""

    with _root_fd(root) as root_fd:
        _remove_entry(root_fd, _component(subdir))
