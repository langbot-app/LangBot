"""Bounded, descriptor-relative file IO for a sandbox workspace."""

from __future__ import annotations

import contextlib
import os
import posixpath
import stat
import uuid


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


@contextlib.contextmanager
def _parent_directory(root: str, relative: str, *, create: bool):
    if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
        raise ValueError("Workspace file transfer requires descriptor-relative file IO")
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


def write_workspace_file(
    root: str, relative: str, content: bytes, max_bytes: int
) -> None:
    if len(content) > max_bytes:
        raise ValueError("Workspace file exceeds the transfer size limit")
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
