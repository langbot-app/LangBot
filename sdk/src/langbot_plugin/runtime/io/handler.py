from __future__ import annotations

import abc
import asyncio
import json
from typing import (
    Callable,
    Any,
    Coroutine,
    AsyncGenerator,
    Union,
    AsyncIterator,
)
import random
import os
import errno
import hashlib
import base64
import uuid
import contextlib
import contextvars
import concurrent.futures
import re
import logging
import stat
import threading
import weakref
from dataclasses import dataclass
from contextlib import contextmanager
from langbot_plugin.runtime.io import connection
from langbot_plugin.entities.io.req import ActionRequest
from langbot_plugin.entities.io.context import (
    ActionEnvelopeContext,
    InstallationBinding,
    parse_action_envelope_context,
)
from langbot_plugin.entities.io.resp import ActionResponse, ChunkStatus
from langbot_plugin.entities.io.errors import (
    ConnectionClosedError,
    ActionCallTimeoutError,
    ActionCallError,
)
from langbot_plugin.entities.io.actions.enums import ActionType, CommonAction
from langbot_plugin.runtime.security import (
    PLUGIN_FILE_STORAGE_DIR_ENV,
    PLUGIN_RUNTIME_PROFILE_ENV,
)
from langbot_plugin.runtime.bounded_executor import (
    TRANSPORT_CONTROL_SCOPE,
    blocking_work_scope,
    run_blocking_cleanup,
    run_blocking_with_backpressure,
    run_transport_control_work,
)

logger = logging.getLogger(__name__)
_ORIGINAL_ASYNCIO_TO_THREAD = asyncio.to_thread

FILE_STORAGE_DIR = "data/temp/lbp"
SHARED_WORKER_FILE_STORAGE_DIR = "/tmp/lbp-rpc"
FILE_CHUNK_LENGTH = 1024 * 16  # 16KB
MAX_INFLIGHT_ACTIONS = 128
MAX_RESERVED_ACTIONS = 4
MAX_STREAM_QUEUE_SIZE = 128
STREAM_WINDOW = 8
MAX_STREAM_FRAME_BYTES = 1024 * 1024
MAX_STREAM_BUFFER_BYTES = STREAM_WINDOW * MAX_STREAM_FRAME_BYTES
MAX_ACTIVE_FILE_TRANSFERS = 128
MAX_PROTOCOL_ERROR_CHARS = 4096
MAX_INLINE_REGISTRATION_BYTES = 16 * 1024 * 1024
_SAFE_FILE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")
_SAFE_FILE_EXTENSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
_TRANSFER_CAPABILITY_PATTERN = re.compile(
    r"^ft1_[0-9a-f]{64}(?:\.[A-Za-z0-9][A-Za-z0-9_-]{0,31})?$"
)
_TRANSFER_OWNER_DIR = ".transfer-owners"

_TRANSFER_LOCKS_GUARD = threading.Lock()
_TRANSFER_LOCKS: dict[tuple[str, str], tuple[threading.RLock, int]] = {}
_ACTIVE_TRANSFER_HANDLERS: dict[tuple[str, str], weakref.ReferenceType[Any]] = {}


class _StreamQueue(asyncio.Queue):
    """Bound legacy and negotiated streams by bytes as well as frame count."""

    def __init__(self):
        super().__init__(maxsize=MAX_STREAM_QUEUE_SIZE)
        self.buffer_bytes = 0
        self._next_size = 0

    def put_response(self, response, size):
        if (
            size > MAX_STREAM_FRAME_BYTES
            or self.buffer_bytes + size > MAX_STREAM_BUFFER_BYTES
        ):
            raise asyncio.QueueFull
        self._next_size = size
        try:
            self.put_nowait(response)
        finally:
            self._next_size = 0

    def _put(self, item):
        self.buffer_bytes += self._next_size
        super()._put((item, self._next_size))

    def _get(self):
        item, size = super()._get()
        self.buffer_bytes -= size
        return item


@dataclass
class _StreamSender:
    context: ActionEnvelopeContext | None
    ready: asyncio.Event
    sent: int = 0
    acknowledged: int = 0


@dataclass
class _TransferStage:
    namespace: str
    temp_name: str
    descriptor: int | None
    file_stat: os.stat_result
    transfer_context: ActionEnvelopeContext | None
    claim_id: str | None
    chunk_amount: int
    next_index: int = 0
    size: int = 0
    payload_published: bool = False
    owner_published: bool = False


async def _run_small_protocol_work(fn: Callable[..., Any], *args: Any) -> Any:
    if asyncio.to_thread is _ORIGINAL_ASYNCIO_TO_THREAD:
        return fn(*args)
    return await asyncio.to_thread(fn, *args)


def _validate_file_key(file_key: str) -> str:
    if not isinstance(file_key, str):
        raise ValueError("Invalid file transfer key")
    key = file_key.strip()
    if (
        not key
        or key != file_key
        or os.path.isabs(key)
        or "/" in key
        or "\\" in key
        or ".." in key
        or os.path.basename(key) != key
        or _SAFE_FILE_KEY_PATTERN.fullmatch(key) is None
    ):
        raise ValueError("Invalid file transfer key")
    return key


def _transfer_namespace(action_context: ActionEnvelopeContext | None) -> str:
    if action_context is None:
        return "unbound"
    serialized_context = json.dumps(
        action_context.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized_context).hexdigest()


def _transfer_owner_record_name(file_key: str) -> str | None:
    if _TRANSFER_CAPABILITY_PATTERN.fullmatch(file_key) is None:
        return None
    return hashlib.sha256(file_key.encode("ascii")).hexdigest() + ".json"


@contextmanager
def _locked_transfer(root: str, file_key: str):
    """Serialize one capability across every handler sharing a process/root."""

    lock_key = (root, file_key)
    with _TRANSFER_LOCKS_GUARD:
        entry = _TRANSFER_LOCKS.get(lock_key)
        if entry is None:
            lock = threading.RLock()
            references = 0
        else:
            lock, references = entry
        _TRANSFER_LOCKS[lock_key] = (lock, references + 1)
    lock.acquire()
    try:
        yield lock_key
    finally:
        lock.release()
        with _TRANSFER_LOCKS_GUARD:
            current_lock, references = _TRANSFER_LOCKS[lock_key]
            if current_lock is lock and references == 1:
                del _TRANSFER_LOCKS[lock_key]
            else:
                _TRANSFER_LOCKS[lock_key] = (current_lock, references - 1)


def _active_transfer_handler(lock_key: tuple[str, str]) -> Handler | None:
    with _TRANSFER_LOCKS_GUARD:
        reference = _ACTIVE_TRANSFER_HANDLERS.get(lock_key)
        active = None if reference is None else reference()
        if reference is not None and active is None:
            _ACTIVE_TRANSFER_HANDLERS.pop(lock_key, None)
        return active


def _is_active_transfer_handler(lock_key: tuple[str, str], handler: Any) -> bool:
    return _active_transfer_handler(lock_key) is handler


def _set_active_transfer_handler(lock_key: tuple[str, str], active: Any | None) -> None:
    with _TRANSFER_LOCKS_GUARD:
        if active is None:
            _ACTIVE_TRANSFER_HANDLERS.pop(lock_key, None)
        else:
            _ACTIVE_TRANSFER_HANDLERS[lock_key] = weakref.ref(active)


def _clear_active_transfer_handler(lock_key: tuple[str, str], expected: Any) -> None:
    with _TRANSFER_LOCKS_GUARD:
        reference = _ACTIVE_TRANSFER_HANDLERS.get(lock_key)
        if reference is not None and reference() is expected:
            del _ACTIVE_TRANSFER_HANDLERS[lock_key]


def _write_all(descriptor: int, data: bytes) -> None:
    """Write all bytes, failing instead of spinning when the OS makes no progress."""

    remaining = memoryview(data)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError(errno.EIO, "file transfer write made no progress")
        if written > len(remaining):
            raise OSError(errno.EIO, "invalid file transfer write result")
        remaining = remaining[written:]


_DIRECTORY_HANDLE_SUPPORTED = bool(getattr(os, "supports_dir_fd", ())) and all(
    operation in os.supports_dir_fd
    for operation in (os.open, os.mkdir, os.stat, os.unlink, os.rename, os.link)
)
"""Whether the platform binds directories to descriptors (POSIX only)."""

if not _DIRECTORY_HANDLE_SUPPORTED:  # pragma: no cover - platform dependent
    logger.warning(
        "File transfer runs without descriptor-relative isolation on this platform "
        "(no os dir_fd support); deploy shared Runtime on POSIX hosts."
    )


class _PathDirectoryHandle:
    """Absolute-path directory handle for platforms without ``dir_fd`` support.

    Windows cannot open a directory as a descriptor and has no ``dir_fd``
    argument, so no descriptor-relative walk exists there.  This fallback keeps
    the namespace containment checks and the directory/regular-file checks, but
    loses the check-to-use atomicity that only descriptors provide.  It is for
    local development hosts; the POSIX descriptor path remains the isolation
    boundary for shared Runtime deployments.
    """

    __slots__ = ("path", "identity")

    def __init__(self, path: str, identity: tuple[int, int]) -> None:
        self.path = path
        self.identity = identity

    @property
    def resolved(self) -> str:
        return os.path.realpath(self.path)


def _directory_handle_path(handle: int | _PathDirectoryHandle) -> str | None:
    """Return the backing path for a path-backed handle, otherwise ``None``."""

    return handle.path if isinstance(handle, _PathDirectoryHandle) else None


def _join_directory_entry(
    handle: int | _PathDirectoryHandle,
    name: str,
) -> str:
    """Resolve one single path component beneath a path-backed handle."""

    path = _directory_handle_path(handle)
    if path is None:  # pragma: no cover - POSIX callers never reach this
        raise ValueError("Invalid file transfer capability")
    if (
        not name
        or name in {".", ".."}
        or os.sep in name
        or (os.altsep is not None and os.altsep in name)
        or os.path.isabs(name)
        or os.path.splitdrive(name)[0]
    ):
        raise ValueError("Invalid file transfer capability")
    candidate = os.path.join(path, name)
    resolved = os.path.realpath(candidate)
    root = os.path.realpath(path)
    if resolved != root and not resolved.startswith(root + os.sep):
        # A junction/symlink swapped in between the walk steps would escape.
        raise ValueError("Invalid file transfer capability")
    return candidate


def _directory_stat(handle: int | _PathDirectoryHandle) -> os.stat_result:
    if _DIRECTORY_HANDLE_SUPPORTED:
        return os.fstat(handle)
    path = _directory_handle_path(handle)
    assert path is not None
    return os.stat(path, follow_symlinks=False)


def _close_directory(handle: int | _PathDirectoryHandle) -> None:
    if _DIRECTORY_HANDLE_SUPPORTED:
        os.close(handle)


def _chmod_directory(handle: int | _PathDirectoryHandle, mode: int) -> None:
    if _DIRECTORY_HANDLE_SUPPORTED:
        os.fchmod(handle, mode)
        return
    path = _directory_handle_path(handle)
    assert path is not None
    with contextlib.suppress(OSError):
        os.chmod(path, mode)


def _sync_directory(handle: int | _PathDirectoryHandle) -> None:
    """Persist directory metadata where the platform can express it."""

    if _DIRECTORY_HANDLE_SUPPORTED:
        os.fsync(handle)


def _open_relative_file(
    handle: int | _PathDirectoryHandle,
    file_name: str,
    flags: int,
    mode: int = 0o777,
) -> int:
    """Open one file entry beneath a directory handle."""

    # Windows CRT text mode translates bytes, corrupting transferred archives.
    flags |= getattr(os, "O_BINARY", 0)
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    if _DIRECTORY_HANDLE_SUPPORTED:
        return os.open(file_name, flags | no_follow, mode, dir_fd=handle)
    path = _join_directory_entry(handle, file_name)
    if os.path.islink(path):
        raise ValueError("Invalid file transfer capability")
    return os.open(path, flags, mode)


def _remove_relative(handle: int | _PathDirectoryHandle, name: str) -> None:
    if _DIRECTORY_HANDLE_SUPPORTED:
        os.remove(name, dir_fd=handle)
        return
    os.remove(_join_directory_entry(handle, name))


def _rename_relative(
    handle: int | _PathDirectoryHandle,
    source: str,
    target: str,
) -> None:
    if _DIRECTORY_HANDLE_SUPPORTED:
        os.rename(source, target, src_dir_fd=handle, dst_dir_fd=handle)
        return
    os.rename(
        _join_directory_entry(handle, source),
        _join_directory_entry(handle, target),
    )


def _link_relative(
    handle: int | _PathDirectoryHandle,
    source: str,
    target: str,
) -> None:
    if _DIRECTORY_HANDLE_SUPPORTED:
        os.link(
            source,
            target,
            src_dir_fd=handle,
            dst_dir_fd=handle,
            follow_symlinks=False,
        )
        return
    source_path = _join_directory_entry(handle, source)
    if os.path.islink(source_path):
        raise ValueError("Invalid file transfer capability")
    os.link(source_path, _join_directory_entry(handle, target))


def _open_transfer_directory(
    root_handle: int | _PathDirectoryHandle,
    directory_name: str,
    *,
    create: bool,
) -> int | _PathDirectoryHandle:
    """Open one child directory beneath the bound transfer root handle."""

    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    try:
        if not _DIRECTORY_HANDLE_SUPPORTED:
            child = _join_directory_entry(root_handle, directory_name)
            if create:
                os.makedirs(child, mode=0o700, exist_ok=True)
            if os.path.islink(child):
                raise ValueError("Invalid file transfer capability")
            child_stat = os.stat(child, follow_symlinks=False)
            if not stat.S_ISDIR(child_stat.st_mode):
                raise ValueError("Invalid file transfer capability")
            return _PathDirectoryHandle(
                os.path.realpath(child),
                (child_stat.st_dev, child_stat.st_ino),
            )
        try:
            directory_fd = os.open(
                directory_name,
                directory_flags | no_follow,
                dir_fd=root_handle,
            )
        except FileNotFoundError:
            if not create:
                raise
            try:
                os.mkdir(directory_name, mode=0o700, dir_fd=root_handle)
            except FileExistsError:
                pass
            directory_fd = os.open(
                directory_name,
                directory_flags | no_follow,
                dir_fd=root_handle,
            )
        directory_stat = os.fstat(directory_fd)
        if not stat.S_ISDIR(directory_stat.st_mode):
            os.close(directory_fd)
            raise ValueError("Invalid file transfer capability")
        return directory_fd
    except OSError as exc:
        if isinstance(exc, FileNotFoundError):
            raise
        raise ValueError("Invalid file transfer capability") from None


_TRANSFER_ROOT_DENIED_ERRNOS = frozenset({errno.EACCES, errno.EPERM})
"""Denials that only mean this process may not inspect an ancestor.

Deployments such as fnOS applications keep the storage root itself reachable
while refusing the walk above it: opening ``/vol2`` read-only is denied even
though the application's own ``data`` directory inside that volume works.
Only these two errors may relax the walk; a symlink, a regular file, or a
missing path keeps the strict verdict.
"""


def _open_transfer_root_entry(
    name: str,
    parent_fd: int | None,
    *,
    readable: bool,
) -> int:
    """Open one entry of the transfer root's own ancestor chain.

    ``readable`` marks the root directory itself, which transfers really read
    and therefore has to open as a plain read-only descriptor.  The components
    above it only have to prove that the chain contains no symlink, so a
    denied read open retries once with ``O_PATH``: that resolves the same
    chain, refuses the same links (the descriptor is still checked to be a
    directory), and needs search permission instead of read permission.
    """

    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(name, directory_flags | no_follow, dir_fd=parent_fd)
    except OSError as exc:
        path_only_flags = getattr(os, "O_PATH", None)
        if (
            readable
            or path_only_flags is None
            or exc.errno not in _TRANSFER_ROOT_DENIED_ERRNOS
        ):
            raise
    descriptor = os.open(
        name,
        path_only_flags | no_follow,
        dir_fd=parent_fd,
    )
    # The descriptor decides what was really opened: ``O_PATH`` without
    # ``O_DIRECTORY`` hands back a link or a regular file instead of failing,
    # and that explicit check does not depend on the kernel honouring
    # ``O_DIRECTORY`` together with ``O_PATH``.
    if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise OSError(errno.ENOTDIR, "transfer root component is not a directory", name)
    return descriptor


def _create_transfer_root_component(component: str, parent_fd: int) -> None:
    """Create one missing component; the open that follows owns the verdict.

    A component that already exists reports ``FileExistsError`` before the
    permission check, so a denied ``mkdir`` only ever happens on something the
    walk is about to open anyway; denying here instead of failing keeps
    unreadable-but-existing ancestors from breaking the walk.
    """

    try:
        os.mkdir(component, mode=0o700, dir_fd=parent_fd)
    except FileExistsError:
        pass
    except OSError as exc:
        if exc.errno not in _TRANSFER_ROOT_DENIED_ERRNOS:
            raise


def _walk_transfer_root(anchor_fd: int, components: list[str]) -> int:
    """Create and open ``components`` beneath ``anchor_fd``.

    Takes ownership of ``anchor_fd`` and always closes it; the returned
    descriptor is the deepest component and belongs to the caller.
    """

    current_fd = anchor_fd
    try:
        for index, component in enumerate(components):
            _create_transfer_root_component(component, current_fd)
            next_fd = _open_transfer_root_entry(
                component,
                current_fd,
                readable=index == len(components) - 1,
            )
            os.close(current_fd)
            current_fd = next_fd
    except BaseException:
        os.close(current_fd)
        raise
    return current_fd


def _reject_symlinked_root_prefixes(components: list[str], anchor: int) -> None:
    """Reject the ancestors above ``anchor`` that this process can inspect."""

    for inspected in range(1, anchor):
        prefix = os.sep + os.path.join(*components[:inspected])
        try:
            prefix_stat = os.lstat(prefix)
        except OSError:
            # Inspecting this ancestor is exactly what the confinement
            # profile denies, which is why the walk re-anchored below it.
            continue
        if stat.S_ISLNK(prefix_stat.st_mode):
            raise ValueError("Invalid file transfer root")


def _bind_transfer_root_under_sandboxed_ancestors(components: list[str]) -> int:
    """Bind the root when an ancestor refuses even a path-only open.

    A confinement profile that grants the application only its own subtree
    (instead of relying on UNIX permissions) denies the walk above that
    subtree completely, so that part of the chain cannot be inspected at all.
    Everything transfers actually depend on still holds: the root is opened
    ``O_NOFOLLOW`` at the inode the configured path names, every component
    below the deepest reachable ancestor is opened relative to its parent
    without following links, and every later operation runs on the bound
    descriptor.  What is lost is only the "no symlink above the root" proof,
    which the profile denies; ancestors that can be inspected are still
    refused when they are symlinks.
    """

    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    for anchor in range(len(components), 0, -1):
        prefix = os.sep + os.path.join(*components[:anchor])
        try:
            anchor_fd = os.open(prefix, directory_flags | no_follow)
        except OSError:
            continue
        break
    else:
        raise ValueError("Invalid file transfer root")
    try:
        _reject_symlinked_root_prefixes(components, anchor)
    except BaseException:
        os.close(anchor_fd)
        raise
    return _walk_transfer_root(anchor_fd, components[anchor:])


def _transfer_root_path_stat(lexical_root: str) -> os.stat_result:
    """Identify the directory the configured path currently names.

    A plain ``lstat`` needs search permission on every ancestor; a profile
    that denies it still answers through a path-only open of the same path,
    which cannot follow a symlink either.
    """

    try:
        return os.stat(lexical_root, follow_symlinks=False)
    except OSError as exc:
        path_only_flags = getattr(os, "O_PATH", None)
        if path_only_flags is None or exc.errno not in _TRANSFER_ROOT_DENIED_ERRNOS:
            raise
    descriptor = os.open(
        lexical_root,
        path_only_flags | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        return os.fstat(descriptor)
    finally:
        os.close(descriptor)


def _prepare_transfer_root(
    root: str,
) -> tuple[str, int | _PathDirectoryHandle, os.stat_result]:
    """Create and bind the configured root to one exact directory inode."""

    lexical_root = os.path.abspath(root)
    components = [component for component in lexical_root.split(os.sep) if component]
    if not components:
        raise ValueError("Invalid file transfer root")
    if not _DIRECTORY_HANDLE_SUPPORTED:
        # Windows-style fallback: create the root and keep an absolute-path
        # handle.  The regular-directory and identity checks stay; only the
        # descriptor-relative binding cannot be expressed on this platform.
        try:
            os.makedirs(lexical_root, mode=0o700, exist_ok=True)
            root_stat = os.stat(lexical_root, follow_symlinks=False)
        except OSError:
            raise ValueError("Invalid file transfer root") from None
        if not stat.S_ISDIR(root_stat.st_mode) or os.path.islink(lexical_root):
            raise ValueError("Invalid file transfer root")
        handle = _PathDirectoryHandle(
            os.path.realpath(lexical_root),
            (root_stat.st_dev, root_stat.st_ino),
        )
        _chmod_directory(handle, 0o700)
        return lexical_root, handle, root_stat
    try:
        root_fd = _walk_transfer_root(
            _open_transfer_root_entry(os.sep, None, readable=False), components
        )
    except OSError as exc:
        if exc.errno not in _TRANSFER_ROOT_DENIED_ERRNOS:
            raise ValueError("Invalid file transfer root") from None
        # The platform refuses to let this process inspect an ancestor of the
        # storage root, so the walk cannot start at '/' here.
        logger.debug(
            "Transfer root %s re-anchored below an unreadable ancestor", lexical_root
        )
        try:
            root_fd = _bind_transfer_root_under_sandboxed_ancestors(components)
        except OSError:
            raise ValueError("Invalid file transfer root") from None
    try:
        root_stat = os.fstat(root_fd)
        if not stat.S_ISDIR(root_stat.st_mode):
            raise ValueError("Invalid file transfer root")
        os.fchmod(root_fd, 0o700)
        path_stat = _transfer_root_path_stat(lexical_root)
        if (
            not stat.S_ISDIR(path_stat.st_mode)
            or path_stat.st_dev != root_stat.st_dev
            or path_stat.st_ino != root_stat.st_ino
        ):
            raise ValueError("Invalid file transfer root")
    except OSError:
        os.close(root_fd)
        raise ValueError("Invalid file transfer root") from None
    except BaseException:
        os.close(root_fd)
        raise
    return lexical_root, root_fd, root_stat


def _read_regular_at(
    root_handle: int | _PathDirectoryHandle,
    directory_name: str,
    file_name: str,
    *,
    private: bool = False,
    max_bytes: int | None = None,
) -> tuple[bytes, os.stat_result]:
    directory_handle = _open_transfer_directory(
        root_handle, directory_name, create=False
    )
    try:
        try:
            descriptor = _open_relative_file(
                directory_handle,
                file_name,
                os.O_RDONLY,
            )
        except OSError as exc:
            if isinstance(exc, FileNotFoundError):
                raise
            raise ValueError("Invalid file transfer capability") from None
        try:
            file_stat = os.fstat(descriptor)
            if not stat.S_ISREG(file_stat.st_mode):
                raise ValueError("Invalid file transfer capability")
            # POSIX ownership bits are the only honest signal for a private
            # entry; platforms whose stat() synthesizes mode bits (Windows) are
            # governed by ACLs instead and skip this check.
            if private and _DIRECTORY_HANDLE_SUPPORTED and file_stat.st_mode & 0o077:
                raise ValueError("Invalid file transfer capability")
            if max_bytes is not None and file_stat.st_size > max_bytes:
                raise ValueError("File transfer exceeds the configured size limit")
            with os.fdopen(descriptor, "rb", closefd=False) as file:
                content = file.read(max_bytes + 1 if max_bytes is not None else -1)
            return content, file_stat
        finally:
            os.close(descriptor)
    finally:
        _close_directory(directory_handle)


def _file_storage_path(
    file_key: str,
    file_storage_dir: str | os.PathLike[str] = FILE_STORAGE_DIR,
    *,
    action_context: ActionEnvelopeContext | None = None,
    create_namespace: bool = False,
) -> str:
    """Resolve one opaque key inside its durable authority namespace."""

    key = _validate_file_key(file_key)
    namespace = _transfer_namespace(action_context)
    namespace_path = os.path.join(os.fspath(file_storage_dir), namespace)
    if create_namespace:
        _root, root_handle, _root_stat = _prepare_transfer_root(
            os.fspath(file_storage_dir)
        )
        try:
            namespace_handle = _open_transfer_directory(
                root_handle, namespace, create=True
            )
            _close_directory(namespace_handle)
        finally:
            _close_directory(root_handle)
    return os.path.join(namespace_path, key)


def _transfer_owner_record_path(
    file_key: str,
    file_storage_dir: str | os.PathLike[str],
) -> str | None:
    """Return the exact durable owner record for an opaque transfer capability."""

    if not isinstance(file_key, str):
        return None
    record_name = _transfer_owner_record_name(file_key)
    if record_name is None:
        return None
    return os.path.join(os.fspath(file_storage_dir), _TRANSFER_OWNER_DIR, record_name)


class Handler(abc.ABC):
    """The abstract base class for all handlers."""

    name: str = "Handler"

    conn: connection.Connection

    actions: dict[str, Callable[[dict[str, Any]], Coroutine[Any, Any, ActionResponse]]]

    resp_waiters: dict[int, asyncio.Future[ActionResponse]] = {}
    resp_queues: dict[int, asyncio.Queue[ActionResponse | BaseException]] = {}

    seq_id_index: int = 0

    _disconnect_callback: Callable[[Handler], Coroutine[Any, Any, bool]] | None

    _bound_action_context: ActionEnvelopeContext | None
    _current_action_context: contextvars.ContextVar[ActionEnvelopeContext | None]

    def __init__(
        self,
        connection: connection.Connection,
        disconnect_callback: Callable[[Handler], Coroutine[Any, Any, bool]]
        | None = None,
        *,
        file_storage_dir: str | os.PathLike[str] | None = None,
        max_file_bytes: int | None = None,
        cancel_active_tasks_on_close: bool = False,
    ):
        if max_file_bytes is not None and (
            isinstance(max_file_bytes, bool)
            or not isinstance(max_file_bytes, int)
            or max_file_bytes <= 0
        ):
            raise ValueError("max_file_bytes must be a positive integer")
        self.conn = connection
        self.actions = {}
        self.seq_id_index = random.randint(0, 100000)
        self.requests_total = 0
        self.resp_waiters = {}
        self.resp_queues = {}
        self._stream_senders: dict[int, _StreamSender] = {}
        self._stream_contexts: dict[int, ActionEnvelopeContext | None] = {}
        self._stream_cancellations: dict[int, asyncio.Task] = {}
        self._action_tasks: set[asyncio.Task[None]] = set()
        self._action_tasks_by_seq: dict[int, asyncio.Task[None]] = {}
        self._action_task_contexts: dict[
            asyncio.Task[None], ActionEnvelopeContext | None
        ] = {}
        self._action_cancel_callbacks: dict[asyncio.Task[None], Callable[[], None]] = {}
        self._pending_action_cancellations: dict[
            asyncio.Task[None], ActionEnvelopeContext | None
        ] = {}
        self._active_tasks: set[asyncio.Task[None]] = set()
        # Reserved tasks remain in the common set for cancellation and accounting.
        self._reserved_action_tasks: set[asyncio.Task[None]] = set()
        self._stream_ack_tasks: set[asyncio.Task[None]] = set()
        # Kept for source compatibility; every connection-owned action is
        # cancelled when the transport terminates.
        self._cancel_active_tasks_on_close = cancel_active_tasks_on_close
        self._closed = False
        self._file_transfer_closing = False
        self._file_transfer_state_lock = threading.RLock()
        self._close_lock = asyncio.Lock()
        self._close_error: ConnectionClosedError | None = None
        self._bound_action_context = None
        self._current_action_context = contextvars.ContextVar(
            f"{self.__class__.__name__}_{id(self)}_action_context",
            default=None,
        )
        self._registration_codec_executor: (
            concurrent.futures.ThreadPoolExecutor | None
        ) = None

        if file_storage_dir is None:
            runtime_profile = os.environ.get(PLUGIN_RUNTIME_PROFILE_ENV, "oss_dev")
            file_storage_dir = os.environ.get(PLUGIN_FILE_STORAGE_DIR_ENV) or (
                SHARED_WORKER_FILE_STORAGE_DIR
                if runtime_profile == "shared"
                else FILE_STORAGE_DIR
            )
        (
            self.file_storage_dir,
            self._file_storage_root_fd,
            root_stat,
        ) = _prepare_transfer_root(os.fspath(file_storage_dir))
        self._file_storage_root_identity = (root_stat.st_dev, root_stat.st_ino)
        self._file_storage_root_fd_closed = False
        self.max_file_bytes = max_file_bytes
        self._file_transfer_lock = asyncio.Lock()
        self._owned_transfer_files: set[str] = set()
        self._owned_transfer_records: set[str] = set()
        self._owned_transfer_contexts: dict[str, ActionEnvelopeContext | None] = {}
        self._owned_transfer_claims: dict[str, str | None] = {}
        self._owned_transfer_identities: dict[str, tuple[int, int]] = {}
        self._transfer_stages: dict[str, _TransferStage] = {}
        self._deleted_transfer_payloads: set[str] = set()

        self._disconnect_callback = disconnect_callback

        @self.action(CommonAction.FILE_CHUNK)
        async def file_chunk(data: dict[str, Any]) -> ActionResponse:
            chunk_base64 = data["chunk_base64"]
            chunk_index = data["chunk_index"]
            chunk_amount = data["chunk_amount"]
            if (
                not isinstance(chunk_base64, str)
                or len(chunk_base64) > ((FILE_CHUNK_LENGTH + 2) // 3) * 4
            ):
                raise ValueError("File transfer chunk exceeds the protocol limit")
            if (
                isinstance(chunk_index, bool)
                or not isinstance(chunk_index, int)
                or isinstance(chunk_amount, bool)
                or not isinstance(chunk_amount, int)
                or chunk_amount <= 0
                or chunk_index < 0
                or chunk_index >= chunk_amount
            ):
                raise ValueError("Invalid file chunk position")
            chunk_bytes = base64.b64decode(chunk_base64, validate=True)
            if len(chunk_bytes) > FILE_CHUNK_LENGTH:
                raise ValueError("File transfer chunk exceeds the protocol limit")
            async with self._file_transfer_lock:
                transfer_context = self.resolve_effective_action_context()
                file_key = _validate_file_key(data["file_key"])
                worker = asyncio.create_task(
                    _run_small_protocol_work(
                        self._write_file_chunk,
                        file_key,
                        transfer_context,
                        chunk_bytes,
                        chunk_index,
                        chunk_amount,
                    )
                )
                try:
                    await asyncio.shield(worker)
                except asyncio.CancelledError:
                    while not worker.done():
                        try:
                            await asyncio.shield(worker)
                        except asyncio.CancelledError:
                            continue
                        except BaseException:
                            pass
                    try:
                        self._rollback_cancelled_file_chunk(file_key, transfer_context)
                    except BaseException:
                        logger.exception(
                            "Failed to roll back cancelled file transfer %s",
                            file_key,
                        )
                    raise
            return ActionResponse.success({})

        @self.action(CommonAction.STREAM_ACK)
        async def stream_ack(data: dict[str, Any]) -> ActionResponse:
            target_seq_id, index = data.get("seq_id"), data.get("index")
            if type(target_seq_id) is not int or type(index) is not int:
                raise ValueError(
                    "Stream acknowledgement requires integer sequence and index"
                )
            sender = self._stream_senders.get(target_seq_id)
            if sender is None or sender.context != self.current_action_context:
                return ActionResponse.success({"accepted": False})
            if index < sender.acknowledged or index > sender.sent:
                raise ValueError("Invalid stream acknowledgement index")
            sender.acknowledged = index
            sender.ready.set()
            return ActionResponse.success({"accepted": True})

        @self.action(CommonAction.CANCEL_ACTION)
        async def cancel_action(data: dict[str, Any]) -> ActionResponse:
            target_seq_id = data.get("seq_id")
            if isinstance(target_seq_id, bool) or not isinstance(target_seq_id, int):
                raise ValueError("Cancellation requires an integer seq_id")
            target = self._action_tasks_by_seq.get(target_seq_id)
            current = asyncio.current_task()
            request_context = self.current_action_context
            target_context_known = (
                target is not None and target in self._action_task_contexts
            )
            target_context = (
                self._action_task_contexts[target] if target_context_known else None
            )
            can_request_cancel = (
                target is not None
                and target is not current
                and (not target_context_known or target_context == request_context)
            )
            if can_request_cancel:
                cancel_callback = self._action_cancel_callbacks.get(target)
                if target_context_known and target_context == request_context:
                    if cancel_callback is not None:
                        cancel_callback()
                    target.cancel()
                else:
                    self._pending_action_cancellations[target] = request_context
            return ActionResponse.success({"cancelled": can_request_cancel})

    def _message_blocking_scope(
        self,
        action_context: ActionEnvelopeContext | None = None,
    ) -> str | None:
        context = (
            action_context
            or self._current_action_context.get()
            or self._bound_action_context
        )
        return getattr(context, "workspace_uuid", None)

    async def _decode_message(
        self,
        message: str,
        *,
        blocking_scope: str | None = None,
    ) -> Any:
        """Parse peer JSON outside the shared event loop with tenant fairness."""

        if blocking_scope == TRANSPORT_CONTROL_SCOPE:
            return await run_transport_control_work(json.loads, message)
        with blocking_work_scope(blocking_scope or self._message_blocking_scope()):
            return await run_blocking_with_backpressure(json.loads, message)

    async def _encode_message(
        self,
        payload: Any,
        *,
        action_context: ActionEnvelopeContext | None = None,
        blocking_scope: str | None = None,
    ) -> str:
        """Serialize protocol JSON outside the shared event loop."""

        serialize = lambda: json.dumps(  # noqa: E731
            payload.model_dump() if hasattr(payload, "model_dump") else payload
        )
        if blocking_scope == TRANSPORT_CONTROL_SCOPE:
            return await run_transport_control_work(serialize)
        with blocking_work_scope(
            blocking_scope or self._message_blocking_scope(action_context),
        ):
            return await run_blocking_with_backpressure(serialize)

    async def _validate_message_model(
        self,
        model_type: Any,
        payload: Any,
        *,
        blocking_scope: str | None = None,
    ) -> Any:
        """Run potentially deep Pydantic validation outside the event loop."""

        if blocking_scope == TRANSPORT_CONTROL_SCOPE:
            return await run_transport_control_work(model_type.model_validate, payload)
        with blocking_work_scope(blocking_scope or self._message_blocking_scope()):
            return await run_blocking_with_backpressure(
                model_type.model_validate, payload
            )

    async def _send_message(
        self,
        payload: Any,
        *,
        action_context: ActionEnvelopeContext | None = None,
        blocking_scope: str | None = None,
    ) -> None:
        """Keep serialization and transport chunking in one tenant scope."""

        inline = bool(getattr(self.conn, "_first_message_send_inline", False))
        if inline:
            # Production stdio plugin workers must be able to emit their
            # launch-scoped registration even when their bounded executor is
            # occupied by imports. The connection consumes the same one-shot
            # flag when it writes the encoded frame.
            encoded = json.dumps(
                payload.model_dump() if hasattr(payload, "model_dump") else payload
            )
            await self.conn.send(encoded)
            return
        with blocking_work_scope(
            blocking_scope or self._message_blocking_scope(action_context),
        ):
            encoded = await self._encode_message(
                payload,
                action_context=action_context,
                blocking_scope=blocking_scope,
            )
            if (
                isinstance(payload, ActionResponse)
                and payload.stream_index is not None
                and len(encoded.encode("utf-8")) > MAX_STREAM_FRAME_BYTES
            ):
                raise ActionCallError(
                    f"Streaming response exceeds frame byte limit ({MAX_STREAM_FRAME_BYTES} bytes). "
                    "Return smaller chunks or pass attachments by reference instead of inline base64."
                )
            await self.conn.send(encoded)

    async def _format_protocol_error(
        self,
        exc: BaseException,
        *,
        blocking_scope: str | None = None,
    ) -> str:
        def render() -> str:
            message = str(exc)
            if len(message) > MAX_PROTOCOL_ERROR_CHARS:
                message = (
                    message[:MAX_PROTOCOL_ERROR_CHARS]
                    + "... [protocol error truncated]"
                )
            return f"{exc.__class__.__name__}: {message}"

        if blocking_scope == TRANSPORT_CONTROL_SCOPE:
            return await run_transport_control_work(render)
        with blocking_work_scope(blocking_scope or self._message_blocking_scope()):
            return await run_blocking_with_backpressure(render)

    def set_disconnect_callback(
        self,
        disconnect_callback: Callable[[Handler], Coroutine[Any, Any, bool]]
        | None = None,
    ):
        self._disconnect_callback = disconnect_callback

    async def run(self) -> None:
        disconnect_error = ConnectionClosedError("Connection closed")
        try:
            while True:
                try:
                    message = await self.conn.receive()
                except ConnectionClosedError as exc:
                    disconnect_error = exc
                    # Requests sent on the old transport cannot be completed by
                    # a replacement connection, even when the handler itself is
                    # reused by a reconnect callback.
                    self._fail_pending(exc)
                    # Do not let old inbound work reply on a replacement transport
                    # when this handler owns connection-scoped task cancellation.
                    if self._cancel_active_tasks_on_close:
                        await self._cancel_action_tasks()
                    if self._disconnect_callback is not None:
                        reconnected = await self._disconnect_callback(self)
                        if reconnected:
                            continue
                    break
                if message is None:
                    continue

                control_candidate = self._uses_reserved_decode_capacity(message)
                try:
                    if control_candidate:
                        # Certified shared stdio registration must not depend on
                        # either the ordinary or transport-control pool. Preserve
                        # the existing 16 MiB wire contract while isolating its
                        # one-shot codec work from the event loop.
                        if len(message.encode("utf-8")) > MAX_INLINE_REGISTRATION_BYTES:
                            raise ValueError(
                                "Registration frame exceeds inline size limit"
                            )
                        if self._registration_codec_executor is None:
                            self._registration_codec_executor = (
                                concurrent.futures.ThreadPoolExecutor(
                                    max_workers=1,
                                    thread_name_prefix="plugin-registration-codec",
                                )
                            )
                        req_data = await asyncio.get_running_loop().run_in_executor(
                            self._registration_codec_executor,
                            json.loads,
                            message,
                        )
                    else:
                        req_data = await self._decode_message(message)
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    logger.warning("Ignored malformed runtime message: %s", exc)
                    continue
                if not isinstance(req_data, dict):
                    logger.warning("Ignored non-object runtime message")
                    continue

                seq_id = req_data.get("seq_id", -1)
                if "code" in req_data:
                    await self._route_response(
                        seq_id, req_data, wire_size=len(message.encode("utf-8"))
                    )
                    continue

                if "action" not in req_data:
                    logger.warning("Ignored runtime message without action or code")
                    continue

                reserved = self._uses_reserved_admission(req_data)
                stream_ack = req_data.get("action") == CommonAction.STREAM_ACK.value
                if stream_ack:
                    inflight = len(self._stream_ack_tasks)
                    limit = MAX_INFLIGHT_ACTIONS
                elif reserved:
                    inflight = len(self._reserved_action_tasks)
                    limit = MAX_RESERVED_ACTIONS
                else:
                    inflight = (
                        len(self._action_tasks)
                        - len(self._reserved_action_tasks)
                        - len(self._stream_ack_tasks)
                    )
                    limit = MAX_INFLIGHT_ACTIONS
                if inflight >= limit:
                    await self._send_overloaded_response(seq_id, limit=limit)
                    continue

                effective_registration = self._uses_reserved_action_capacity(req_data)
                task = asyncio.create_task(
                    self._handle_action(
                        req_data,
                        control_scope=(
                            TRANSPORT_CONTROL_SCOPE
                            if control_candidate and effective_registration
                            else None
                        ),
                    )
                )
                self._action_tasks.add(task)
                self._action_tasks_by_seq[seq_id] = task
                if stream_ack:
                    self._stream_ack_tasks.add(task)
                elif reserved:
                    self._reserved_action_tasks.add(task)
                task.add_done_callback(
                    lambda completed, owned_seq_id=seq_id: self._action_task_done(
                        completed,
                        owned_seq_id,
                    )
                )
                if self._cancel_active_tasks_on_close:
                    self._active_tasks.add(task)
                    task.add_done_callback(self._active_tasks.discard)
        finally:
            if self._registration_codec_executor is not None:
                self._registration_codec_executor.shutdown(
                    wait=False,
                    cancel_futures=True,
                )
                self._registration_codec_executor = None
            self._begin_file_transfer_close()
            self._close_error = disconnect_error
            self._fail_pending(disconnect_error)
            if self._cancel_active_tasks_on_close:
                await self._cancel_action_tasks()
            async with self._file_transfer_lock:
                self._closed = True
                await self._cleanup_owned_transfers_locked(close_root=True)

    async def close(self) -> None:
        """Close the transport and deterministically release connection-owned work."""
        self._begin_file_transfer_close()
        error = ConnectionClosedError("Connection closed by local runtime")
        async with self._close_lock:
            async with self._file_transfer_lock:
                if self._closed:
                    await self._cleanup_owned_transfers_locked(close_root=True)
                    return
                self._closed = True
                self._close_error = error
                self._fail_pending(error)
            try:
                await self.conn.close()
            finally:
                if self._cancel_active_tasks_on_close:
                    await self._cancel_action_tasks()
                await self._cleanup_owned_transfers(close_root=True)

    async def _route_response(
        self, seq_id: int, req_data: dict[str, Any], *, wire_size: int | None = None
    ) -> None:
        try:
            response = await self._validate_message_model(
                ActionResponse,
                req_data,
            )
        except Exception as exc:
            logger.warning(
                "Ignored malformed runtime response: %s",
                exc.__class__.__name__,
            )
            return
        waiter = self.resp_waiters.get(seq_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(response)

        queue = self.resp_queues.get(seq_id)
        if queue is not None:
            try:
                if isinstance(queue, _StreamQueue):
                    queue.put_response(
                        response,
                        wire_size
                        if wire_size is not None
                        else len(json.dumps(req_data).encode("utf-8")),
                    )
                else:
                    queue.put_nowait(response)
            except asyncio.QueueFull:
                # A stalled stream consumer must not block response routing for
                # every other action sharing this connection.
                self.resp_queues.pop(seq_id, None)
                while not queue.empty():
                    with contextlib.suppress(asyncio.QueueEmpty):
                        queue.get_nowait()
                queue.put_nowait(
                    ActionCallError(
                        "Streaming action consumer is too slow; response buffer full"
                    )
                )
                if (
                    seq_id in self._stream_contexts
                    and seq_id not in self._stream_cancellations
                ):
                    # Stop legacy producers even while the caller is paused at
                    # yield and has not yet observed the local overflow error.
                    self._stream_cancellations[seq_id] = asyncio.create_task(
                        self._cancel_peer_action(seq_id, self._stream_contexts[seq_id])
                    )

    async def _handle_action(
        self,
        req_data: dict[str, Any],
        *,
        control_scope: str | None = None,
    ) -> None:
        seq_id = req_data.get("seq_id", -1)
        action_name = str(req_data.get("action", ""))
        context_token = None
        try:
            request = (
                ActionRequest.model_validate(req_data)
                if control_scope == TRANSPORT_CONTROL_SCOPE
                else await self._validate_message_model(ActionRequest, req_data)
            )
            action_name = request.action
            if action_name not in self.actions:
                raise ValueError(f"Action {action_name} not found")

            action_context = self.validate_inbound_action_context(
                action_name,
                request.context,
            )
            context_token = self._current_action_context.set(action_context)
            current_task = asyncio.current_task()
            if current_task is not None:
                self._action_task_contexts[current_task] = action_context
                pending_context = self._pending_action_cancellations.get(current_task)
                if pending_context is not None and pending_context != action_context:
                    self._pending_action_cancellations.pop(current_task, None)

            from langbot_plugin.api.proxies.invocation import (
                AUDIT_CORRELATION_FIELD,
                audit_correlation_scope,
            )

            with (
                audit_correlation_scope(
                    request.data.pop(AUDIT_CORRELATION_FIELD, None)
                ),
                self.action_invocation_scope(action_name, action_context),
            ):
                with blocking_work_scope(
                    getattr(action_context, "workspace_uuid", None)
                ):
                    response = self.actions[action_name](request.data)
                    if not isinstance(response, AsyncGenerator):
                        if isinstance(response, Coroutine):
                            response = await response
                        response.seq_id = seq_id
                        if control_scope == TRANSPORT_CONTROL_SCOPE:
                            encoded = json.dumps(response.model_dump())
                            await self.conn.send(encoded)
                        else:
                            await self._send_message(response)
                    else:
                        sender = None
                        if request.stream_flow_control == 1:
                            sender = _StreamSender(action_context, asyncio.Event())
                            self._stream_senders[seq_id] = sender
                        try:
                            while True:
                                if sender is not None:
                                    while (
                                        sender.sent - sender.acknowledged
                                        >= STREAM_WINDOW
                                    ):
                                        sender.ready.clear()
                                        await sender.ready.wait()
                                try:
                                    chunk = await anext(response)
                                except StopAsyncIteration:
                                    break
                                assert isinstance(chunk, ActionResponse)
                                chunk.seq_id = seq_id
                                chunk.chunk_status = ChunkStatus.CONTINUE
                                if sender is not None:
                                    sender.sent += 1
                                    chunk.stream_index = sender.sent
                                await self._send_message(chunk)
                        finally:
                            self._stream_senders.pop(seq_id, None)
                            await response.aclose()

                        end_response = ActionResponse.success({})
                        end_response.seq_id = seq_id
                        end_response.chunk_status = ChunkStatus.END
                        await self._send_message(end_response)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "Runtime action %s failed with %s",
                action_name or "<unknown>",
                exc.__class__.__name__,
            )
            if control_scope == TRANSPORT_CONTROL_SCOPE:
                message = str(exc)
                if len(message) > MAX_PROTOCOL_ERROR_CHARS:
                    message = (
                        message[:MAX_PROTOCOL_ERROR_CHARS]
                        + "... [protocol error truncated]"
                    )
                protocol_error = f"{exc.__class__.__name__}: {message}"
            else:
                protocol_error = await self._format_protocol_error(exc)
            error_response = ActionResponse.error(
                protocol_error,
                data=exc.data if isinstance(exc, ActionCallError) else None,
            )
            error_response.seq_id = seq_id
            with contextlib.suppress(ConnectionClosedError):
                if control_scope == TRANSPORT_CONTROL_SCOPE:
                    await self.conn.send(json.dumps(error_response.model_dump()))
                else:
                    await self._send_message(error_response)
        finally:
            if context_token is not None:
                self._current_action_context.reset(context_token)
            current_task = asyncio.current_task()
            if current_task is not None:
                self._action_task_contexts.pop(current_task, None)
                self._action_cancel_callbacks.pop(current_task, None)
                self._pending_action_cancellations.pop(current_task, None)
            if action_name and not action_name.startswith("__"):
                logger.debug("[Action] %s", action_name)

    def set_current_action_cancel_callback(self, callback: Callable[[], None]) -> None:
        """Run a synchronous fence before peer cancellation reaches action code."""

        current_task = asyncio.current_task()
        if current_task is None or current_task not in self._action_task_contexts:
            raise RuntimeError("No tracked action task is active")
        self._action_cancel_callbacks[current_task] = callback
        pending_context = self._pending_action_cancellations.pop(current_task, None)
        if pending_context == self._action_task_contexts[current_task]:
            callback()
            raise asyncio.CancelledError

    def _uses_reserved_admission(self, req_data: dict[str, Any]) -> bool:
        """Opt in to bounded control capacity, not validation or authorization."""
        return req_data.get("action") in {
            CommonAction.CANCEL_ACTION.value,
            CommonAction.STREAM_ACK.value,
        }

    def _uses_reserved_action_capacity(self, req_data: dict[str, Any]) -> bool:
        """Confirm the decoded top-level control action before isolation."""
        return False

    def _uses_reserved_decode_capacity(self, message: str) -> bool:
        """Opt in to reserved executor capacity before JSON decoding."""
        return False

    async def _send_overloaded_response(
        self, seq_id: int, *, limit: int = MAX_INFLIGHT_ACTIONS
    ) -> None:
        response = ActionResponse.error(
            f"Runtime connection is busy (max {limit} concurrent actions)"
        )
        response.seq_id = seq_id
        with contextlib.suppress(ConnectionClosedError):
            await self._send_message(response)

    def _action_task_done(
        self,
        task: asyncio.Task[None],
        seq_id: int | None = None,
    ) -> None:
        self._action_tasks.discard(task)
        self._reserved_action_tasks.discard(task)
        self._stream_ack_tasks.discard(task)
        if seq_id is not None and self._action_tasks_by_seq.get(seq_id) is task:
            self._action_tasks_by_seq.pop(seq_id, None)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(
                "Runtime action task failed",
                exc_info=(type(exc), exc, exc.__traceback__),
            )

    def _fail_pending(self, error: ConnectionClosedError) -> None:
        for waiter in list(self.resp_waiters.values()):
            if not waiter.done():
                waiter.set_exception(error)

        for queue in list(self.resp_queues.values()):
            while queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(error)

    async def _cancel_action_tasks(self) -> None:
        tasks = list(self._action_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._action_tasks.clear()
        self._action_tasks_by_seq.clear()
        self._reserved_action_tasks.clear()
        self._stream_ack_tasks.clear()
        self._active_tasks.clear()

    def cancel_inflight_messages(self) -> None:
        """Cancel peer requests already accepted by this handler."""

        for action_task in tuple(self._action_tasks):
            action_task.cancel()

    def cancel_inflight_messages_for_context(
        self,
        action_context: ActionEnvelopeContext,
    ) -> None:
        """Cancel only requests owned by one exact installation revision."""

        for action_task, owned_context in tuple(self._action_task_contexts.items()):
            if owned_context == action_context:
                action_task.cancel()

    async def call_action(
        self,
        action: ActionType,
        data: dict[str, Any],
        timeout: float | None = 15.0,
        action_context: ActionEnvelopeContext | dict[str, Any] | None = None,
        cancel_peer_on_cancel: bool = False,
    ) -> dict[str, Any]:
        """Actively call an action provided by the peer, and wait for the response."""
        from langbot_plugin.api.proxies.invocation import invocation_capability

        invocation = invocation_capability(self)
        self.seq_id_index += 1
        self.requests_total += 1
        this_seq_id = self.seq_id_index
        request = ActionRequest.make_request(
            this_seq_id,
            getattr(action, "value", str(action)),
            self._outbound_action_data(data),
            self.resolve_outbound_action_context(action_context),
        )
        return await self._call_action_request(
            request,
            timeout,
            invocation=invocation,
            cancel_peer_on_cancel=cancel_peer_on_cancel,
        )

    async def _call_action_request(
        self,
        request: ActionRequest,
        timeout: float | None,
        *,
        invocation=None,
        cancel_peer_on_cancel: bool = False,
    ) -> dict[str, Any]:
        this_seq_id = request.seq_id
        resolved_context = request.context
        # wait for response
        if self._closed:
            raise self._close_error or ConnectionClosedError("Connection closed")
        future = asyncio.get_running_loop().create_future()
        self.resp_waiters[this_seq_id] = future
        try:
            if invocation is not None:
                invocation.require_active()
            await self._send_message(
                request,
                action_context=resolved_context,
            )
            response = await asyncio.wait_for(future, timeout)
            if invocation is not None:
                invocation.require_active()
            if response.code != 0:
                raise ActionCallError(f"{response.message}", response.data)
            return response.data
        except asyncio.CancelledError:
            if cancel_peer_on_cancel:
                await self._cancel_peer_action(this_seq_id, resolved_context)
            raise
        except asyncio.TimeoutError:
            if cancel_peer_on_cancel:
                await self._cancel_peer_action(this_seq_id, resolved_context)
            raise ActionCallTimeoutError(f"Action {request.action} call timed out")
        except ActionCallError:
            raise
        except ConnectionClosedError:
            raise
        except Exception as e:
            raise ActionCallError(f"{e.__class__.__name__}: {str(e)}")
        finally:
            if this_seq_id in self.resp_waiters:
                del self.resp_waiters[this_seq_id]
            if this_seq_id in self.resp_queues:
                del self.resp_queues[this_seq_id]

    async def _cancel_peer_action(
        self,
        seq_id: int,
        action_context: ActionEnvelopeContext | None,
    ) -> None:
        """Finish bounded cleanup using the original request's authority."""

        self.seq_id_index += 1
        self.requests_total += 1
        request = ActionRequest.make_request(
            self.seq_id_index,
            CommonAction.CANCEL_ACTION.value,
            {"seq_id": seq_id},
            action_context,
        )
        # Cleanup may outlive invocation revocation and repeated cancellation;
        # it can only cancel this request under its captured immutable context.
        cancellation = asyncio.create_task(
            asyncio.wait_for(self._call_action_request(request, None), timeout=5.0)
        )
        interrupted = False
        try:
            while not cancellation.done():
                try:
                    await asyncio.shield(cancellation)
                except asyncio.CancelledError:
                    interrupted = True
            cancellation.result()
        except (
            ActionCallError,
            ActionCallTimeoutError,
            ConnectionClosedError,
            asyncio.TimeoutError,
        ):
            logger.debug("Failed to cancel peer action %s", seq_id, exc_info=True)
        finally:
            if interrupted:
                raise asyncio.CancelledError

    async def call_action_generator(
        self,
        action: ActionType,
        data: dict[str, Any],
        timeout: float | None = 15.0,
        action_context: ActionEnvelopeContext | dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        from langbot_plugin.api.proxies.invocation import invocation_capability

        invocation = invocation_capability(self)
        self.seq_id_index += 1
        self.requests_total += 1
        this_seq_id = self.seq_id_index
        request = ActionRequest.make_request(
            this_seq_id,
            getattr(action, "value", str(action)),
            self._outbound_action_data(data),
            resolved_context := self.resolve_outbound_action_context(action_context),
        )
        request.stream_flow_control = 1

        # Create a queue for streaming responses
        if self._closed:
            raise self._close_error or ConnectionClosedError("Connection closed")
        queue = _StreamQueue()
        self.resp_queues[this_seq_id] = queue
        self._stream_contexts[this_seq_id] = resolved_context
        completed = False
        consumed = 0
        try:
            if invocation is not None:
                invocation.require_active()
            await self._send_message(
                request,
                action_context=resolved_context,
            )
            while True:
                try:
                    response = await asyncio.wait_for(queue.get(), timeout)
                    if invocation is not None:
                        invocation.require_active()
                    if isinstance(response, BaseException):
                        raise response
                    if response.code != 0:
                        raise ActionCallError(f"{response.message}", response.data)

                    if response.chunk_status == ChunkStatus.CONTINUE:
                        if response.stream_index is not None:
                            if response.stream_index != consumed + 1:
                                raise ActionCallError("Out-of-order streaming response")
                            consumed = response.stream_index
                        yield response.data
                        # Acknowledge only after the caller has processed the
                        # value; never block the shared transport router.
                        if (
                            response.stream_index is not None
                            and consumed % (STREAM_WINDOW // 2) == 0
                        ):
                            await self.call_action(
                                CommonAction.STREAM_ACK,
                                {"seq_id": this_seq_id, "index": consumed},
                                timeout=timeout,
                                action_context=resolved_context,
                            )
                    elif response.chunk_status == ChunkStatus.END:
                        completed = True
                        break
                except asyncio.CancelledError:
                    raise
                except asyncio.TimeoutError:
                    raise ActionCallTimeoutError(
                        f"Action {action.value} call timed out"
                    )
                except ActionCallError:
                    raise
                except ConnectionClosedError:
                    raise
                except Exception as e:
                    raise ActionCallError(f"{e.__class__.__name__}: {str(e)}")
        finally:
            if this_seq_id in self.resp_queues:
                del self.resp_queues[this_seq_id]
            self._stream_contexts.pop(this_seq_id, None)
            cancellation = self._stream_cancellations.pop(this_seq_id, None)
            if cancellation is not None:
                await cancellation
            elif not completed and not self._closed:
                await self._cancel_peer_action(this_seq_id, resolved_context)

    @property
    def bound_action_context(self) -> ActionEnvelopeContext | None:
        """Trusted context permanently associated with this connection."""

        return self._bound_action_context

    @property
    def current_action_context(self) -> ActionEnvelopeContext | None:
        """Context of the request currently executing in this asyncio task."""

        return self._current_action_context.get()

    @contextlib.contextmanager
    def action_invocation_scope(
        self,
        action: str,
        action_context: ActionEnvelopeContext | None,
    ):
        """Bind implementation-specific task-local state for one action."""

        del action
        del action_context
        yield

    def _outbound_action_data(self, data: dict[str, Any]) -> dict[str, Any]:
        from langbot_plugin.api.proxies.invocation import relay_audit_correlation

        return relay_audit_correlation(data)

    def bind_action_context(
        self,
        action_context: ActionEnvelopeContext | dict[str, Any],
    ) -> ActionEnvelopeContext:
        """Bind this connection once to a fenced Workspace.

        The installation capability may be added once after LangBot resolves
        the installation from its trusted settings store.  Changing the
        Workspace, generation, or an existing installation is rejected.
        """

        context = parse_action_envelope_context(action_context)
        current = self._bound_action_context
        if current is not None:
            if not current.same_workspace(context):
                raise ValueError(
                    "Action connection cannot be rebound to another Workspace"
                )
            if (
                current.installation_uuid is not None
                and context.installation_uuid is None
            ):
                raise ValueError("Plugin installation binding cannot be removed")
            if (
                current.installation_uuid is not None
                and current.installation_uuid != context.installation_uuid
            ):
                raise ValueError(
                    "Action connection cannot be rebound to another plugin installation"
                )
            if isinstance(current, InstallationBinding) and (
                not isinstance(context, InstallationBinding) or context != current
            ):
                raise ValueError(
                    "Action connection cannot change installation revision or artifact"
                )

        self._bound_action_context = context
        return context

    def require_bound_action_context(self) -> ActionEnvelopeContext:
        """Return the trusted binding or fail instead of choosing a default."""

        if self._bound_action_context is None:
            raise ValueError("Plugin Runtime is not bound to a Workspace")
        return self._bound_action_context

    def validate_inbound_action_context(
        self,
        action: str,
        action_context: ActionEnvelopeContext | None,
    ) -> ActionEnvelopeContext | None:
        """Validate an inbound envelope against the connection binding.

        A bound connection remains compatible with old peers that omit the
        envelope: the connection binding supplies the context.  A peer cannot
        switch Workspace or placement generation by sending a new envelope.
        """

        del action
        bound = self._bound_action_context
        if bound is None:
            return action_context
        if action_context is not None:
            if not bound.same_workspace(action_context):
                raise ValueError("Action context does not match connection Workspace")
            if (
                bound.installation_uuid is not None
                and action_context.installation_uuid != bound.installation_uuid
            ):
                raise ValueError(
                    "Action context does not match connection plugin installation"
                )
            if isinstance(bound, InstallationBinding) and action_context != bound:
                raise ValueError(
                    "Action context does not match installation revision or artifact"
                )
        return bound

    def resolve_outbound_action_context(
        self,
        action_context: ActionEnvelopeContext | dict[str, Any] | None,
    ) -> ActionEnvelopeContext | None:
        """Resolve and validate the envelope for an outbound request."""

        if action_context is None:
            return self._current_action_context.get() or self._bound_action_context

        context = parse_action_envelope_context(action_context)
        bound = self._bound_action_context
        if bound is not None:
            if not bound.same_workspace(context):
                raise ValueError(
                    "Outbound action context does not match connection Workspace"
                )
            if (
                bound.installation_uuid is not None
                and context.installation_uuid != bound.installation_uuid
            ):
                raise ValueError(
                    "Outbound action context does not match plugin installation"
                )
            if isinstance(bound, InstallationBinding) and context != bound:
                raise ValueError(
                    "Outbound action context does not match installation revision or artifact"
                )
        return context

    def resolve_effective_action_context(
        self,
        action_context: ActionEnvelopeContext | dict[str, Any] | None = None,
    ) -> ActionEnvelopeContext | None:
        """Resolve explicit, task-local, then connection-bound authority."""

        if action_context is not None:
            return self.resolve_outbound_action_context(action_context)
        return self._current_action_context.get() or self._bound_action_context

    # decorator to register an action
    def action(
        self, name: ActionType
    ) -> Callable[
        [
            Callable[
                [dict[str, Any]],
                Coroutine[
                    Any,
                    Any,
                    Union[ActionResponse, AsyncGenerator[ActionResponse, None]],
                ],
            ]
        ],
        Callable[
            [dict[str, Any]],
            Coroutine[
                Any, Any, Union[ActionResponse, AsyncGenerator[ActionResponse, None]]
            ],
        ],
    ]:
        def decorator(
            func: Callable[
                [dict[str, Any]],
                Coroutine[
                    Any,
                    Any,
                    Union[ActionResponse, AsyncGenerator[ActionResponse, None]],
                ],
            ],
        ) -> Callable[
            [dict[str, Any]],
            Coroutine[
                Any, Any, Union[ActionResponse, AsyncGenerator[ActionResponse, None]]
            ],
        ]:
            self.actions[name.value] = func
            return func

        return decorator

    # ====== file transfer ======
    def _transfer_race_hook(self, event: str, **details: Any) -> None:
        """Deterministic no-op hook used by filesystem race regression tests."""

        del event, details

    def _require_file_transfer_open(self) -> None:
        with self._file_transfer_state_lock:
            if self._file_transfer_closing or self._closed:
                raise self._close_error or ConnectionClosedError("Connection closed")

    def _begin_file_transfer_close(self) -> None:
        with self._file_transfer_state_lock:
            self._file_transfer_closing = True

    def _require_transfer_root(self) -> int | _PathDirectoryHandle:
        if self._file_storage_root_fd_closed:
            raise ValueError("Invalid file transfer root")
        try:
            path_stat = _transfer_root_path_stat(self.file_storage_dir)
        except OSError:
            raise ValueError("Invalid file transfer root") from None
        if (
            not stat.S_ISDIR(path_stat.st_mode)
            or (path_stat.st_dev, path_stat.st_ino) != self._file_storage_root_identity
        ):
            raise ValueError("Invalid file transfer root")
        self._transfer_race_hook("after_root_validation")
        return self._file_storage_root_fd

    def _bound_transfer_root(self) -> int | _PathDirectoryHandle:
        if self._file_storage_root_fd_closed:
            raise ValueError("Invalid file transfer root")
        return self._file_storage_root_fd

    def _close_transfer_root_if_clean(self) -> None:
        if (
            self._file_storage_root_fd_closed
            or self._owned_transfer_files
            or self._transfer_stages
        ):
            return
        _close_directory(self._file_storage_root_fd)
        self._file_storage_root_fd_closed = True

    def _read_regular(
        self,
        directory_name: str,
        file_name: str,
        *,
        private: bool = False,
        max_bytes: int | None = None,
    ) -> tuple[bytes, os.stat_result]:
        return _read_regular_at(
            self._require_transfer_root(),
            directory_name,
            file_name,
            private=private,
            max_bytes=max_bytes,
        )

    def _read_regular_bound(
        self,
        directory_name: str,
        file_name: str,
        *,
        private: bool = False,
        max_bytes: int | None = None,
    ) -> tuple[bytes, os.stat_result]:
        return _read_regular_at(
            self._bound_transfer_root(),
            directory_name,
            file_name,
            private=private,
            max_bytes=max_bytes,
        )

    def _quarantine_expected_regular(
        self,
        directory_name: str,
        file_name: str,
        expected_stat: os.stat_result,
        *,
        role: str,
        expected_bytes: bytes | None = None,
        missing_ok: bool,
    ) -> bool:
        root_handle = self._bound_transfer_root()
        try:
            directory_handle = _open_transfer_directory(
                root_handle, directory_name, create=False
            )
        except FileNotFoundError:
            if missing_ok:
                return False
            raise
        quarantine_name = f".quarantine-{uuid.uuid4().hex}"
        try:
            self._transfer_race_hook(
                "before_quarantine_rename",
                role=role,
                directory_name=directory_name,
                file_name=file_name,
            )
            try:
                _rename_relative(directory_handle, file_name, quarantine_name)
            except FileNotFoundError:
                if missing_ok:
                    return False
                raise

            verified = False
            try:
                descriptor = _open_relative_file(
                    directory_handle,
                    quarantine_name,
                    os.O_RDONLY,
                )
                try:
                    quarantined_stat = os.fstat(descriptor)
                    if (
                        not stat.S_ISREG(quarantined_stat.st_mode)
                        or quarantined_stat.st_dev != expected_stat.st_dev
                        or quarantined_stat.st_ino != expected_stat.st_ino
                    ):
                        raise ValueError("Invalid file transfer capability")
                    if expected_bytes is not None:
                        with os.fdopen(descriptor, "rb", closefd=False) as file:
                            if file.read(len(expected_bytes) + 1) != expected_bytes:
                                raise ValueError("Invalid file transfer capability")
                    verified = True
                finally:
                    os.close(descriptor)
                _remove_relative(directory_handle, quarantine_name)
                return True
            except BaseException:
                # Never restore or remove a name that resolved to a mismatching
                # inode. Retaining it and the owner record makes retries fail
                # closed instead of deleting a same-UID mutator's replacement.
                if verified:
                    with contextlib.suppress(OSError, ValueError):
                        _link_relative(directory_handle, quarantine_name, file_name)
                    with contextlib.suppress(OSError):
                        _remove_relative(directory_handle, quarantine_name)
                raise
        finally:
            _close_directory(directory_handle)

    @classmethod
    def _serialize_transfer_record(
        cls,
        transfer_context: ActionEnvelopeContext | None,
        claim_id: str,
        payload_identity: tuple[int, int],
    ) -> bytes:
        return json.dumps(
            {
                "claim_id": claim_id,
                "payload_dev": payload_identity[0],
                "payload_ino": payload_identity[1],
                "owner": None
                if transfer_context is None
                else transfer_context.model_dump(mode="json"),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @staticmethod
    def _parse_transfer_record(
        raw_owner: bytes,
    ) -> tuple[ActionEnvelopeContext | None, str | None, tuple[int, int] | None]:
        stored_data = json.loads(raw_owner)
        if (
            isinstance(stored_data, dict)
            and set(stored_data) == {"claim_id", "owner", "payload_dev", "payload_ino"}
            and isinstance(stored_data["claim_id"], str)
            and stored_data["claim_id"]
            and isinstance(stored_data["payload_dev"], int)
            and isinstance(stored_data["payload_ino"], int)
        ):
            owner_data = stored_data["owner"]
            return (
                None
                if owner_data is None
                else parse_action_envelope_context(owner_data),
                stored_data["claim_id"],
                (stored_data["payload_dev"], stored_data["payload_ino"]),
            )
        if (
            isinstance(stored_data, dict)
            and set(stored_data) == {"claim_id", "owner"}
            and isinstance(stored_data["claim_id"], str)
            and stored_data["claim_id"]
        ):
            owner_data = stored_data["owner"]
            return (
                None
                if owner_data is None
                else parse_action_envelope_context(owner_data),
                stored_data["claim_id"],
                None,
            )
        return (
            None if stored_data is None else parse_action_envelope_context(stored_data),
            None,
            None,
        )

    @staticmethod
    def _context_can_access_transfer(
        effective_context: ActionEnvelopeContext | None,
        stored_context: ActionEnvelopeContext | None,
    ) -> bool:
        return (
            effective_context is None
            or effective_context == stored_context
            or (
                isinstance(stored_context, InstallationBinding)
                and not isinstance(effective_context, InstallationBinding)
                and stored_context.model_dump(
                    exclude={"runtime_revision", "artifact_digest"}
                )
                == effective_context.model_dump()
            )
        )

    def _read_private_file(self, path: str) -> tuple[bytes, os.stat_result]:
        return self._read_regular(
            os.path.basename(os.path.dirname(path)),
            os.path.basename(path),
            private=True,
        )

    def _read_private_file_bound(self, path: str) -> tuple[bytes, os.stat_result]:
        return self._read_regular_bound(
            os.path.basename(os.path.dirname(path)),
            os.path.basename(path),
            private=True,
        )

    def _create_transfer_stage(
        self,
        file_key: str,
        transfer_context: ActionEnvelopeContext | None,
        chunk_amount: int,
    ) -> _TransferStage:
        namespace = _transfer_namespace(transfer_context)
        namespace_handle = _open_transfer_directory(
            self._bound_transfer_root(), namespace, create=True
        )
        temp_name = f".payload-{uuid.uuid4().hex}.tmp"
        try:
            record_name = _transfer_owner_record_name(file_key)
            if record_name is not None:
                try:
                    owner_dir_handle = _open_transfer_directory(
                        self._bound_transfer_root(), _TRANSFER_OWNER_DIR, create=False
                    )
                except FileNotFoundError:
                    owner_dir_handle = None
                if owner_dir_handle is not None:
                    try:
                        try:
                            owner_fd = _open_relative_file(
                                owner_dir_handle,
                                record_name,
                                os.O_RDONLY,
                            )
                        except FileNotFoundError:
                            owner_fd = None
                        except OSError:
                            raise ValueError(
                                "Invalid file transfer capability"
                            ) from None
                        if owner_fd is not None:
                            os.close(owner_fd)
                            raise ValueError("Invalid file transfer capability")
                    finally:
                        _close_directory(owner_dir_handle)
            # Published names are immutable.  Opening them for write (especially
            # with O_TRUNC) would let a raced replacement be modified.
            try:
                existing_fd = _open_relative_file(
                    namespace_handle,
                    file_key,
                    os.O_RDONLY,
                )
            except FileNotFoundError:
                existing_fd = None
            except OSError:
                raise ValueError("Invalid file transfer capability") from None
            if existing_fd is not None:
                os.close(existing_fd)
                raise ValueError("Invalid file transfer capability")
            descriptor = _open_relative_file(
                namespace_handle,
                temp_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            file_stat = os.fstat(descriptor)
            if not stat.S_ISREG(file_stat.st_mode):
                os.close(descriptor)
                raise ValueError("Invalid file transfer capability")
            return _TransferStage(
                namespace=namespace,
                temp_name=temp_name,
                descriptor=descriptor,
                file_stat=file_stat,
                transfer_context=transfer_context,
                claim_id=(
                    uuid.uuid4().hex
                    if _transfer_owner_record_name(file_key) is not None
                    else None
                ),
                chunk_amount=chunk_amount,
            )
        except OSError:
            raise ValueError("Invalid file transfer capability") from None
        finally:
            _close_directory(namespace_handle)

    def _discard_transfer_stage(
        self,
        file_key: str,
        stage: _TransferStage,
        *,
        clear_active: bool = False,
    ) -> bool:
        if stage.descriptor is not None:
            descriptor = stage.descriptor
            stage.descriptor = None
            with contextlib.suppress(OSError):
                os.close(descriptor)
        try:
            namespace_handle = _open_transfer_directory(
                self._bound_transfer_root(), stage.namespace, create=False
            )
        except FileNotFoundError:
            namespace_handle = None
        except (OSError, ValueError):
            return False
        if namespace_handle is not None:
            try:
                try:
                    _remove_relative(namespace_handle, stage.temp_name)
                except FileNotFoundError:
                    pass
                except OSError:
                    return False
            finally:
                _close_directory(namespace_handle)
        self._transfer_stages.pop(file_key, None)
        if clear_active:
            lock_key = (self.file_storage_dir, file_key)
            _clear_active_transfer_handler(lock_key, self)
        return True

    def _publish_owner_record(
        self,
        file_key: str,
        stage: _TransferStage,
        file_path: str,
    ) -> None:
        record_name = _transfer_owner_record_name(file_key)
        if record_name is None or stage.claim_id is None:
            return
        owner_dir_handle = _open_transfer_directory(
            self._bound_transfer_root(), _TRANSFER_OWNER_DIR, create=True
        )
        temp_name = f".owner-{uuid.uuid4().hex}.tmp"
        serialized = self._serialize_transfer_record(
            stage.transfer_context,
            stage.claim_id,
            (stage.file_stat.st_dev, stage.file_stat.st_ino),
        )
        descriptor: int | None = None
        try:
            descriptor = _open_relative_file(
                owner_dir_handle,
                temp_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            _write_all(descriptor, serialized)
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            self._transfer_race_hook(
                "before_owner_link", file_key=file_key, record_name=record_name
            )
            _link_relative(owner_dir_handle, temp_name, record_name)
            stage.owner_published = True
            owner_path = os.path.join(
                self.file_storage_dir, _TRANSFER_OWNER_DIR, record_name
            )
            # Track before durability can fail: close can now clean the exact
            # payload/owner pair instead of silently orphaning a sidecar.
            self._owned_transfer_files.add(file_path)
            self._owned_transfer_records.add(owner_path)
            self._owned_transfer_contexts[file_path] = stage.transfer_context
            self._owned_transfer_claims[file_path] = stage.claim_id
            self._owned_transfer_identities[file_path] = (
                stage.file_stat.st_dev,
                stage.file_stat.st_ino,
            )
            _sync_directory(owner_dir_handle)
        finally:
            if descriptor is not None:
                os.close(descriptor)
            with contextlib.suppress(OSError):
                _remove_relative(owner_dir_handle, temp_name)
            _close_directory(owner_dir_handle)

    def _write_file_chunk(
        self,
        file_key: str,
        transfer_context: ActionEnvelopeContext | None,
        chunk_bytes: bytes,
        chunk_index: int,
        chunk_amount: int,
    ) -> None:
        root = self.file_storage_dir
        file_path = os.path.join(root, _transfer_namespace(transfer_context), file_key)
        self._require_transfer_root()

        with _locked_transfer(root, file_key) as lock_key:
            self._require_file_transfer_open()
            active = _active_transfer_handler(lock_key)
            if active is not None and active is not self:
                raise ValueError("Invalid file transfer capability")
            stage = self._transfer_stages.get(file_key)
            if chunk_index == 0:
                if stage is not None or file_path in self._owned_transfer_files:
                    raise ValueError("Invalid file transfer capability")
                if (
                    len(self._owned_transfer_files) + len(self._transfer_stages)
                    >= MAX_ACTIVE_FILE_TRANSFERS
                ):
                    raise ValueError("Active file transfer capacity reached")
                if (
                    self.max_file_bytes is not None
                    and len(chunk_bytes) > self.max_file_bytes
                ):
                    raise ValueError("File transfer exceeds the configured size limit")
                stage = self._create_transfer_stage(
                    file_key, transfer_context, chunk_amount
                )
                try:
                    self._transfer_race_hook(
                        "after_staging_create",
                        file_key=file_key,
                        descriptor=stage.descriptor,
                    )
                    self._require_file_transfer_open()
                    self._transfer_stages[file_key] = stage
                    _set_active_transfer_handler(lock_key, self)
                except BaseException:
                    if not self._discard_transfer_stage(file_key, stage):
                        self._transfer_stages[file_key] = stage
                    raise
            elif stage is None:
                raise ValueError("Invalid file transfer capability")

            assert stage is not None
            if (
                stage.transfer_context != transfer_context
                or stage.chunk_amount != chunk_amount
                or stage.next_index != chunk_index
            ):
                raise ValueError("Invalid file transfer capability")
            resulting_size = stage.size + len(chunk_bytes)
            if self.max_file_bytes is not None and resulting_size > self.max_file_bytes:
                self._discard_transfer_stage(file_key, stage)
                _clear_active_transfer_handler(lock_key, self)
                raise ValueError("File transfer exceeds the configured size limit")

            try:
                self._transfer_race_hook(
                    "before_staging_write", file_key=file_key, namespace=stage.namespace
                )
                self._require_file_transfer_open()
                assert stage.descriptor is not None
                current_stat = os.fstat(stage.descriptor)
                if (
                    current_stat.st_dev != stage.file_stat.st_dev
                    or current_stat.st_ino != stage.file_stat.st_ino
                ):
                    raise ValueError("Invalid file transfer capability")
                with self._file_transfer_state_lock:
                    self._require_file_transfer_open()
                    _write_all(stage.descriptor, chunk_bytes)
                stage.size = resulting_size
                stage.next_index += 1
                if chunk_index + 1 != chunk_amount:
                    return

                os.fsync(stage.descriptor)
                with self._file_transfer_state_lock:
                    self._require_file_transfer_open()
                    namespace_handle = _open_transfer_directory(
                        self._bound_transfer_root(), stage.namespace, create=False
                    )
                    try:
                        try:
                            _link_relative(
                                namespace_handle,
                                stage.temp_name,
                                file_key,
                            )
                        except FileExistsError:
                            raise ValueError(
                                "Invalid file transfer capability"
                            ) from None
                        stage.payload_published = True
                        _sync_directory(namespace_handle)
                    finally:
                        _close_directory(namespace_handle)

                    if stage.claim_id is not None:
                        self._publish_owner_record(file_key, stage, file_path)
                    else:
                        self._owned_transfer_files.add(file_path)
                        self._owned_transfer_contexts[file_path] = transfer_context
                        self._owned_transfer_claims[file_path] = None
                        self._owned_transfer_identities[file_path] = (
                            stage.file_stat.st_dev,
                            stage.file_stat.st_ino,
                        )
                self._discard_transfer_stage(file_key, stage)
            except BaseException:
                if stage.owner_published:
                    # Publication happened; keep all authority tracked for a
                    # truthful close/delete retry.
                    self._discard_transfer_stage(file_key, stage)
                else:
                    if stage.payload_published:
                        try:
                            self._quarantine_expected_regular(
                                stage.namespace,
                                file_key,
                                stage.file_stat,
                                role="payload",
                                missing_ok=False,
                            )
                        except (OSError, ValueError, FileNotFoundError):
                            # A raced replacement is not ours to delete.
                            pass
                    self._discard_transfer_stage(file_key, stage)
                    _clear_active_transfer_handler(lock_key, self)
                raise

    def _rollback_cancelled_file_chunk(
        self,
        file_key: str,
        transfer_context: ActionEnvelopeContext | None,
    ) -> None:
        file_path = os.path.join(
            self.file_storage_dir,
            _transfer_namespace(transfer_context),
            file_key,
        )
        with _locked_transfer(self.file_storage_dir, file_key) as lock_key:
            stage = self._transfer_stages.get(file_key)
            if stage is not None:
                self._discard_transfer_stage(file_key, stage)
                _clear_active_transfer_handler(lock_key, self)
            if file_path in self._owned_transfer_files:
                self._delete_transfer_sync(file_key, transfer_context, True)

    async def _resolve_transfer_context(
        self,
        file_key: str,
        action_context: ActionEnvelopeContext | dict[str, Any] | None,
    ) -> tuple[ActionEnvelopeContext | None, tuple[int, int] | None]:
        file_key = _validate_file_key(file_key)
        effective_context = self.resolve_effective_action_context(action_context)
        record_path = _transfer_owner_record_path(file_key, self.file_storage_dir)
        if record_path is None:
            return effective_context, None
        try:
            raw_owner, _owner_stat = await _run_small_protocol_work(
                self._read_private_file, record_path
            )
            stored_context, _claim_id, expected_payload = self._parse_transfer_record(
                raw_owner
            )
        except FileNotFoundError:
            raise FileNotFoundError(file_key) from None
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            raise ValueError("Invalid file transfer capability") from None
        if not self._context_can_access_transfer(
            effective_context,
            stored_context,
        ):
            raise FileNotFoundError(file_key)
        return stored_context, expected_payload

    async def send_file(
        self,
        file_bytes: bytes,
        file_extension: str,
        *,
        action_context: ActionEnvelopeContext | dict[str, Any] | None = None,
    ) -> str:
        """Send a file to the peer, chunk by chunk, in base64."""
        from langbot_plugin.api.proxies.invocation import invocation_capability

        invocation = invocation_capability(self)
        if self.max_file_bytes is not None and len(file_bytes) > self.max_file_bytes:
            raise ValueError("File transfer exceeds the configured size limit")
        if not isinstance(file_extension, str):
            raise ValueError("Invalid file transfer extension")
        extension = file_extension.strip(".")
        if extension and _SAFE_FILE_EXTENSION_PATTERN.fullmatch(extension) is None:
            raise ValueError("Invalid file transfer extension")
        suffix = f".{extension}" if extension else ""
        file_key = f"ft1_{uuid.uuid4().hex}{uuid.uuid4().hex}{suffix}"
        file_length = len(file_bytes)
        chunk_amount = max(
            1, (file_length + FILE_CHUNK_LENGTH - 1) // FILE_CHUNK_LENGTH
        )
        for i in range(chunk_amount):
            if invocation is not None:
                invocation.require_active()
            chunk_bytes = file_bytes[
                i * FILE_CHUNK_LENGTH : (i + 1) * FILE_CHUNK_LENGTH
            ]
            chunk_base64 = base64.b64encode(chunk_bytes).decode("utf-8")
            # response = await self.conn.send(json.dumps({
            #     "action": CommonAction.FILE_CHUNK.value,
            #     "data": {
            #         "file_key": file_key,
            #         "file_length": file_length,
            #         "chunk_base64": chunk_base64,
            #         "chunk_index": i,
            #         "chunk_amount": chunk_amount,
            #         "chunk_size": len(chunk_bytes),
            #     }
            # }))
            await self.call_action(
                CommonAction.FILE_CHUNK,
                {
                    "file_key": file_key,
                    "file_length": file_length,
                    "chunk_base64": chunk_base64,
                    "chunk_index": i,
                    "chunk_amount": chunk_amount,
                    "chunk_size": len(chunk_bytes),
                },
                action_context=action_context,
            )
        return file_key

    async def read_local_file(
        self,
        file_key: str,
        *,
        action_context: ActionEnvelopeContext | dict[str, Any] | None = None,
    ) -> bytes:
        from langbot_plugin.api.proxies.invocation import invocation_capability

        invocation = invocation_capability(self)
        if invocation is not None:
            invocation.require_active()
        transfer_context, expected_payload = await self._resolve_transfer_context(
            file_key, action_context
        )

        def read_file() -> bytes:
            with _locked_transfer(self.file_storage_dir, file_key):
                content, file_stat = self._read_regular(
                    _transfer_namespace(transfer_context),
                    file_key,
                    max_bytes=self.max_file_bytes,
                )
                if (
                    expected_payload is not None
                    and (
                        file_stat.st_dev,
                        file_stat.st_ino,
                    )
                    != expected_payload
                ):
                    raise ValueError("Invalid file transfer capability")
                return content

        content = await run_blocking_with_backpressure(read_file)
        if invocation is not None:
            invocation.require_active()
        if self.max_file_bytes is not None and len(content) > self.max_file_bytes:
            raise ValueError("File transfer exceeds the configured size limit")
        return content

    async def delete_local_file(
        self,
        file_key: str,
        *,
        action_context: ActionEnvelopeContext | dict[str, Any] | None = None,
    ) -> None:
        from langbot_plugin.api.proxies.invocation import invocation_capability

        invocation = invocation_capability(self)
        if invocation is not None:
            invocation.require_active()
        file_key = _validate_file_key(file_key)
        effective_context = self.resolve_effective_action_context(action_context)
        async with self._file_transfer_lock:
            if invocation is not None:
                invocation.require_active()
            await run_blocking_with_backpressure(
                self._delete_transfer_sync,
                file_key,
                effective_context,
                False,
            )

    def _delete_transfer_sync(
        self,
        file_key: str,
        transfer_context: ActionEnvelopeContext | None,
        cleanup: bool,
    ) -> bool:
        if not cleanup:
            self._require_transfer_root()
        owner_record = _transfer_owner_record_path(file_key, self.file_storage_dir)
        with _locked_transfer(self.file_storage_dir, file_key) as lock_key:
            stored_context, current_claim_id, expected_payload_identity = (
                transfer_context,
                None,
                None,
            )
            owner_stat: os.stat_result | None = None
            raw_owner: bytes | None = None
            if owner_record is not None:
                try:
                    raw_owner, owner_stat = self._read_private_file_bound(owner_record)
                    (
                        stored_context,
                        current_claim_id,
                        expected_payload_identity,
                    ) = self._parse_transfer_record(raw_owner)
                except FileNotFoundError:
                    return False
                except (OSError, TypeError, ValueError, json.JSONDecodeError):
                    raise ValueError("Invalid file transfer capability") from None
                if not self._context_can_access_transfer(
                    transfer_context,
                    stored_context,
                ):
                    return False

            namespace = _transfer_namespace(stored_context)
            file_path = os.path.join(self.file_storage_dir, namespace, file_key)
            if cleanup:
                expected_claim_id = self._owned_transfer_claims.get(file_path)
                if current_claim_id != expected_claim_id:
                    self._owned_transfer_files.discard(file_path)
                    self._owned_transfer_contexts.pop(file_path, None)
                    self._owned_transfer_claims.pop(file_path, None)
                    if owner_record is not None:
                        self._owned_transfer_records.discard(owner_record)
                    return False
                active = _active_transfer_handler(lock_key)
                if active is not None and active is not self:
                    self._owned_transfer_files.discard(file_path)
                    self._owned_transfer_contexts.pop(file_path, None)
                    self._owned_transfer_claims.pop(file_path, None)
                    if owner_record is not None:
                        self._owned_transfer_records.discard(owner_record)
                    return False
            try:
                _payload_bytes, payload_stat = self._read_regular_bound(
                    namespace,
                    file_key,
                )
            except FileNotFoundError:
                payload_stat = None
            if expected_payload_identity is not None:
                if payload_stat is None:
                    if file_path not in self._deleted_transfer_payloads:
                        # Durable owner authority outlives an externally missing
                        # or moved payload; this is corruption, not success.
                        raise ValueError("Invalid file transfer capability")
                elif (
                    payload_stat.st_dev,
                    payload_stat.st_ino,
                ) != expected_payload_identity:
                    raise ValueError("Invalid file transfer capability")
            try:
                if payload_stat is not None:
                    payload_removed = self._quarantine_expected_regular(
                        namespace,
                        file_key,
                        payload_stat,
                        role="payload",
                        missing_ok=False,
                    )
                    if payload_removed:
                        self._deleted_transfer_payloads.add(file_path)
            except (OSError, ValueError):
                if cleanup:
                    return False
                raise
            was_active = _is_active_transfer_handler(lock_key, self)

            if owner_record is not None:
                assert owner_stat is not None and raw_owner is not None
                try:
                    self._quarantine_expected_regular(
                        _TRANSFER_OWNER_DIR,
                        os.path.basename(owner_record),
                        owner_stat,
                        role="owner",
                        expected_bytes=raw_owner,
                        missing_ok=False,
                    )
                except (OSError, ValueError):
                    if cleanup:
                        return False
                    raise
                self._owned_transfer_records.discard(owner_record)
            self._owned_transfer_files.discard(file_path)
            self._owned_transfer_contexts.pop(file_path, None)
            self._owned_transfer_claims.pop(file_path, None)
            self._owned_transfer_identities.pop(file_path, None)
            self._deleted_transfer_payloads.discard(file_path)
            if not cleanup or was_active:
                _set_active_transfer_handler(lock_key, None)
            return True

    async def _cleanup_owned_transfers(self, *, close_root: bool = False) -> None:
        async with self._file_transfer_lock:
            await self._cleanup_owned_transfers_locked(close_root=close_root)

    async def _cleanup_owned_transfers_locked(
        self, *, close_root: bool = False
    ) -> None:
        stages = tuple(self._transfer_stages.items())
        for file_key, stage in stages:
            with _locked_transfer(self.file_storage_dir, file_key):
                if not self._discard_transfer_stage(
                    file_key,
                    stage,
                    clear_active=True,
                ):
                    logger.warning(
                        "Failed to clean runtime transfer staging file %s",
                        file_key,
                    )
        file_paths = tuple(self._owned_transfer_files)
        for file_path in file_paths:
            try:
                await run_blocking_cleanup(
                    self._delete_transfer_sync,
                    os.path.basename(file_path),
                    self._owned_transfer_contexts[file_path],
                    True,
                )
            except OSError as exc:
                with _locked_transfer(
                    self.file_storage_dir, os.path.basename(file_path)
                ) as lock_key:
                    _clear_active_transfer_handler(lock_key, self)
                logger.warning(
                    "Failed to clean runtime transfer file %s: %s",
                    os.path.basename(file_path),
                    exc,
                )
        if close_root:
            self._close_transfer_root_if_clean()
