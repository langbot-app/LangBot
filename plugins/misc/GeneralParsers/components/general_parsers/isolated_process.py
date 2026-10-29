"""Isolated process boundary for parsers that drive non-thread-safe native code.

PyMuPDF documents that it is not thread-safe, and its table finder keeps
module-level page state (``EDGES`` / ``CHARS`` in ``pymupdf.table``) that every
``find_tables()`` / ``Table.extract()`` call rewrites.  Driving that from the
shared worker's thread pool let two installations' parses interleave inside the
dependency, so one request could pick up another request's page text, and a
native fault could take the whole shared process down.

Every such parse therefore runs in a dedicated, short-lived interpreter process
that owns the complete dependency lifecycle (open -> table detection ->
extraction -> close) and hands back only its result.  The boundary is released
- and the worker reaped - before the caller resumes, so a hard timeout, a
cancellation or a native crash can never leave dependency work running while a
later request starts.

The worker is started with a fresh interpreter (never through ``fork`` /
``spawn`` inheritance), so no module state, configuration or tenant data from
the shared process is visible inside it.
"""

from __future__ import annotations

import asyncio
import logging
import os
import pickle
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

#: Hard upper bound on a single isolated parse.
DEFAULT_TIMEOUT_SECONDS = 300.0
#: Grace period after ``terminate()`` before the worker is killed outright.
_TERMINATE_GRACE_SECONDS = 2.0
#: Grace period after ``kill()`` - a killed process is expected to be gone at once.
_KILL_GRACE_SECONDS = 5.0

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]
_WORKER_SCRIPT = Path(__file__).resolve().with_name('process_worker.py')
_CREATION_FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
#: The worker resolves its target the same way this process would, so the
#: caller's import roots are handed over explicitly (a child interpreter does
#: not inherit runtime ``sys.path`` additions).
_WORKER_SEARCH_PATH_ENV = 'GENERAL_PARSERS_WORKER_SEARCH_PATH'
_WORKER_SEARCH_PATH_LIMIT = 16384

_live_workers: set[subprocess.Popen] = set()
_live_workers_lock = threading.Lock()


class IsolatedWorkerError(RuntimeError):
    """The isolated worker failed, crashed or returned no usable result."""


class IsolatedWorkerTimeout(IsolatedWorkerError):
    """The isolated worker exceeded its hard lifetime bound and was torn down."""


def active_worker_count() -> int:
    """Number of worker processes the boundary currently has running."""
    with _live_workers_lock:
        return len(_live_workers)


def active_worker_pids() -> tuple[int, ...]:
    """Pids of the worker processes the boundary currently has running.

    A virtual environment may start its interpreter through a launcher, so these
    are the processes this boundary spawned; the interpreter the target runs in
    can report a different pid of its own.
    """
    with _live_workers_lock:
        return tuple(sorted(worker.pid for worker in _live_workers))


def _register(worker: subprocess.Popen) -> None:
    with _live_workers_lock:
        _live_workers.add(worker)


def _unregister(worker: subprocess.Popen) -> None:
    with _live_workers_lock:
        _live_workers.discard(worker)


class _Exchange:
    """Background transport for one worker: send the arguments, collect stdout.

    The worker reads all of stdin before it writes its result, so a single
    thread can safely write the payload first and read the answer afterwards;
    nothing in the shared event loop is blocked while that happens.
    """

    def __init__(self, worker: subprocess.Popen, payload: bytes, loop: asyncio.AbstractEventLoop) -> None:
        self._worker = worker
        self._payload = payload
        self._loop = loop
        self._done = asyncio.Event()
        self.stdout = b''
        self.transport_error: str | None = None

    def start(self) -> None:
        thread = threading.Thread(
            target=self._run,
            name='general-parsers-worker-exchange',
            daemon=True,
        )
        thread.start()

    def _run(self) -> None:
        try:
            stdin, stdout = self._worker.stdin, self._worker.stdout
            if stdin is None or stdout is None:
                raise ValueError('worker pipes are unavailable')
            stdin.write(self._payload)
            stdin.close()
            self.stdout = stdout.read() or b''
        except (BrokenPipeError, OSError, ValueError) as error:
            self.transport_error = f'{type(error).__name__}: {error}'
        finally:
            try:
                self._loop.call_soon_threadsafe(self._done.set)
            except RuntimeError:
                # The event loop is gone (interpreter shutdown / closed test loop).
                logger.debug('Isolated worker result arrived after its event loop closed')

    async def wait(self, timeout: float) -> None:
        await asyncio.wait_for(self._done.wait(), timeout)


def _start_worker(reference: str, arguments: tuple, name: str) -> tuple[subprocess.Popen, bytes]:
    if not sys.executable:
        raise IsolatedWorkerError(f'{name} needs a Python interpreter to run out of process')
    if not _WORKER_SCRIPT.is_file():
        raise IsolatedWorkerError(f'{name} is missing its worker entry point: {_WORKER_SCRIPT}')
    payload = pickle.dumps(arguments, protocol=pickle.HIGHEST_PROTOCOL)
    environment = dict(os.environ)
    search_path = [entry for entry in sys.path if isinstance(entry, str) and entry]
    if search_path:
        # Keep the environment block small; the plugin root always travels as an
        # argument, so truncating only affects exotic extra import roots.
        environment[_WORKER_SEARCH_PATH_ENV] = os.pathsep.join(search_path)[:_WORKER_SEARCH_PATH_LIMIT]
    try:
        worker = subprocess.Popen(
            [sys.executable, str(_WORKER_SCRIPT), str(_PLUGIN_ROOT), reference],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=environment,
            creationflags=_CREATION_FLAGS,
        )
    except OSError as error:
        raise IsolatedWorkerError(f'{name} could not start its worker process: {error}') from error
    return worker, payload


def _decode_result(stdout: bytes, name: str) -> tuple[str, Any]:
    try:
        envelope = pickle.loads(stdout)
    except Exception as error:  # noqa: BLE001 - any malformed payload means no usable result
        raise IsolatedWorkerError(
            f'{name} worker returned an unreadable result ({type(error).__name__}: {error})'
        ) from error
    if not isinstance(envelope, tuple) or len(envelope) != 2:
        raise IsolatedWorkerError(f'{name} worker returned a malformed envelope')
    status, value = envelope
    if status == 'ok':
        return 'ok', value
    if status == 'error':
        return 'error', str(value)
    raise IsolatedWorkerError(f'{name} worker returned an unknown status: {status!r}')


def _reap(worker: subprocess.Popen) -> None:
    """Wait for the worker to be gone, escalating to SIGKILL/terminate-process."""
    try:
        worker.wait(timeout=_TERMINATE_GRACE_SECONDS)
        return
    except subprocess.TimeoutExpired:
        pass
    logger.warning('Isolated worker %s ignored termination; killing it', worker.pid)
    try:
        worker.kill()
    except OSError:
        pass
    try:
        worker.wait(timeout=_KILL_GRACE_SECONDS)
    except subprocess.TimeoutExpired:  # pragma: no cover - the OS has no stronger signal
        logger.error('Isolated worker %s could not be killed', worker.pid)


async def _release(worker: subprocess.Popen) -> None:
    """Tear the worker down completely before the boundary is released."""
    if worker.poll() is None:
        worker.terminate()
    try:
        await asyncio.to_thread(_reap, worker)
    finally:
        _unregister(worker)


async def run_isolated(
    reference: str,
    *arguments: Any,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    name: str = 'isolated parse',
) -> Any:
    """Run ``reference`` (``module:attribute``) in a dedicated worker process.

    Args:
        reference: Importable ``module:attribute`` resolved inside the worker.
        *arguments: Picklable positional arguments for the target.
        timeout: Hard lifetime bound for the worker process.
        name: Human readable label used in error messages and logs.

    Returns:
        Whatever the target returned.

    Raises:
        IsolatedWorkerTimeout: The worker outlived ``timeout`` and was killed.
        IsolatedWorkerError: The worker failed, crashed or returned no result.
    """
    worker, payload = _start_worker(reference, arguments, name)
    _register(worker)
    exchange = _Exchange(worker, payload, asyncio.get_running_loop())
    exchange.start()
    try:
        try:
            await exchange.wait(timeout)
        except (TimeoutError, asyncio.TimeoutError):
            raise IsolatedWorkerTimeout(
                f'{name} exceeded its {timeout:g}s lifetime bound and was terminated'
            ) from None

        if not exchange.stdout:
            detail = exchange.transport_error or 'no result was written'
            raise IsolatedWorkerError(
                f'{name} worker exited with code {worker.poll()} without returning a result ({detail})'
            )

        status, value = _decode_result(exchange.stdout, name)
        if status == 'error':
            raise IsolatedWorkerError(value)
        return value
    finally:
        # Reached on success, failure, timeout and cancellation alike: the worker
        # is terminated and reaped before the caller regains control, so no parse
        # can keep rewriting dependency state while a later request runs.
        await _release(worker)
