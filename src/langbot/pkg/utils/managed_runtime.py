"""Base class for connectors that may manage a local runtime subprocess."""

from __future__ import annotations

import asyncio
import os
import sys
from typing import TYPE_CHECKING, Awaitable, Callable

if TYPE_CHECKING:
    from ..core import app as core_app


class ManagedRuntimeConnector:
    """Base class for connectors that may manage a local runtime subprocess.

    Provides shared lifecycle helpers: subprocess launch, health-check retry,
    and graceful termination.  Concrete connectors (plugin, box, …) inherit
    this and add their own protocol-specific logic.
    """

    ap: 'core_app.Application'
    runtime_subprocess: asyncio.subprocess.Process | None
    runtime_subprocess_task: asyncio.Task | None

    def __init__(self, ap: 'core_app.Application'):
        self.ap = ap
        self.runtime_subprocess = None
        self.runtime_subprocess_task = None

    async def _start_runtime_subprocess(self, *args: str) -> None:
        """Launch a local runtime as a subprocess of the current Python interpreter.

        If a subprocess is already running (no *returncode* yet), this is a no-op.
        """
        if self.runtime_subprocess is not None and self.runtime_subprocess.returncode is None:
            return

        python_path = sys.executable
        env = os.environ.copy()
        self.runtime_subprocess = await asyncio.create_subprocess_exec(
            python_path,
            *args,
            env=env,
        )
        self.runtime_subprocess_task = asyncio.create_task(self.runtime_subprocess.wait())

    async def _wait_until_ready(
        self,
        check: Callable[[], Awaitable[None]],
        retries: int = 40,
        interval: float = 0.25,
        runtime_name: str = 'runtime',
    ) -> None:
        """Repeatedly call *check* until it succeeds or retries are exhausted.

        Between attempts the method sleeps for *interval* seconds.  If the
        managed subprocess exits before readiness is confirmed, a
        ``RuntimeError`` is raised immediately.
        """
        last_exc: Exception | None = None
        for _ in range(retries):
            # Fast-fail if the process already died.
            if self.runtime_subprocess is not None and self.runtime_subprocess.returncode is not None:
                raise RuntimeError(
                    f'local {runtime_name} exited before becoming ready '
                    f'(code {self.runtime_subprocess.returncode})'
                )

            try:
                await check()
                return
            except Exception as exc:
                last_exc = exc
                await asyncio.sleep(interval)

        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f'local {runtime_name} did not become ready')

    def _dispose_subprocess(self) -> None:
        """Terminate the managed subprocess and cancel its wait task."""
        if self.runtime_subprocess is not None and self.runtime_subprocess.returncode is None:
            self.ap.logger.info('Terminating managed runtime process...')
            self.runtime_subprocess.terminate()

        if self.runtime_subprocess_task is not None:
            self.runtime_subprocess_task.cancel()
            self.runtime_subprocess_task = None
