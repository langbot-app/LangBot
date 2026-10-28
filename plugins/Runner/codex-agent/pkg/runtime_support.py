"""Installation-local writable defaults and awaited native process lifecycle."""

from __future__ import annotations

import asyncio
import contextlib
import functools
import hashlib
import os
import signal
from pathlib import Path

SHARED_DATA_ROOT = Path("/data")


class ProcessCleanupUnconfirmed(BaseException):
    """Do not translate an unconfirmed cleanup into a successful daemon ack."""


def local_workspace(configured: str = "") -> str:
    if os.environ.get("LANGBOT_PLUGIN_RUNTIME_PROFILE") != "shared":
        return configured or os.getcwd()
    path = Path(configured).expanduser() if configured else SHARED_DATA_ROOT / "workspace"
    try:
        if not configured:
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not path.is_dir() or not os.access(path, os.W_OK | os.X_OK):
            raise OSError("directory is missing or not writable")
    except OSError as exc:
        raise ValueError(
            f"Native workspace {path} must be a writable jail-visible directory; default is /data/workspace"
        ) from exc
    return str(path.resolve())


def _group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    # Linux may retain orphan zombies until namespace init reaps them. Zombies
    # cannot execute; do not confuse them with a still-running child.
    if Path("/proc").is_dir():
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                fields = (entry / "stat").read_text().rsplit(") ", 1)[1].split()
                if int(fields[2]) == pgid and fields[0] not in ("Z", "X"):
                    return True
            except (FileNotFoundError, ProcessLookupError):
                continue
        return False
    return True


async def _terminate(process):
    if os.name == "nt":
        if process.returncode is None:
            process.kill()
        await asyncio.wait_for(process.wait(), timeout=2)
        return
    for sig, grace in ((signal.SIGTERM, 1.0), (signal.SIGKILL, 2.0)):
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, sig)
        deadline = asyncio.get_running_loop().time() + grace
        while _group_alive(process.pid):
            if asyncio.get_running_loop().time() >= deadline:
                break
            await asyncio.sleep(0.02)
        if not _group_alive(process.pid):
            await asyncio.wait_for(process.wait(), timeout=2)
            return
    raise ProcessCleanupUnconfirmed(f"process group {process.pid} did not stop; target must remain fenced")


async def terminate_process_group(process):
    """Shield reap/kill through repeated cancellation, then restore cancellation."""
    task = asyncio.create_task(_terminate(process))
    interrupted = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            interrupted = True
        except Exception:
            break  # classify cleanup errors below, never report a terminal ack
    try:
        task.result()
    except Exception as exc:
        raise ProcessCleanupUnconfirmed("native cleanup could not be confirmed") from exc
    if interrupted:
        raise asyncio.CancelledError


@contextlib.asynccontextmanager
async def session_guard(home: str, session_id: str):
    """Serialize writes to the same vendor session, including separate daemons."""
    if not session_id:
        yield
        return
    # fcntl is available in the supported Linux shared workers. Dedicated Windows
    # keeps its existing behavior; no POSIX process-tree guarantee is asserted.
    if os.name == "nt":
        yield
        return
    import fcntl

    lockdir = Path(home).expanduser().resolve() / ".langbot-session-locks"
    lockdir.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = hashlib.sha256(session_id.encode()).hexdigest()
    fd = os.open(lockdir / name, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                await asyncio.sleep(0.05)
        yield
    finally:
        os.close(fd)


def serialize_codex_session(function):
    @functools.wraps(function)
    async def wrapped(*args, **kwargs):
        env = kwargs.get("env") or {}
        home = Path(env.get("CODEX_HOME") or os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        # Per-run homes link to the installation's common sessions directory.
        async with session_guard(str((home / "sessions").resolve()), kwargs.get("resume_session_id") or ""):
            async with contextlib.aclosing(function(*args, **kwargs)) as stream:
                async for event in stream:
                    yield event

    return wrapped
