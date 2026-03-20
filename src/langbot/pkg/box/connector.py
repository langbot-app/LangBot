from __future__ import annotations

import asyncio
import os
import sys
from typing import TYPE_CHECKING

from .errors import BoxRuntimeUnavailableError
from .client import create_box_runtime_client, resolve_box_runtime_url
from ..utils import platform

if TYPE_CHECKING:
    from ..core import app as core_app


class BoxRuntimeConnector:
    """Build and initialize the Box runtime-facing service for the app."""

    _HEALTH_CHECK_RETRY_COUNT = 40
    _HEALTH_CHECK_RETRY_INTERVAL_SEC = 0.25

    def __init__(self, ap: 'core_app.Application'):
        self.ap = ap
        self.configured_runtime_url = self._load_configured_runtime_url()
        self.runtime_url = self.configured_runtime_url or resolve_box_runtime_url(ap)
        self.manages_local_runtime = self._should_manage_local_runtime()
        self.client = create_box_runtime_client(ap, runtime_url=self.runtime_url)
        self.runtime_subprocess: asyncio.subprocess.Process | None = None
        self.runtime_subprocess_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        if not self.manages_local_runtime:
            await self.client.initialize()
            return

        try:
            await self.client.initialize()
            return
        except BoxRuntimeUnavailableError:
            self.ap.logger.info(
                'Local Box runtime is not running, starting an embedded Box runtime server...'
            )

        await self._start_local_runtime_process()
        await self._wait_until_runtime_ready()

    def dispose(self) -> None:
        if self.runtime_subprocess is not None and self.runtime_subprocess.returncode is None:
            self.ap.logger.info('Terminating local Box runtime process...')
            self.runtime_subprocess.terminate()

        if self.runtime_subprocess_task is not None:
            self.runtime_subprocess_task.cancel()
            self.runtime_subprocess_task = None

    def _load_configured_runtime_url(self) -> str:
        box_config = getattr(self.ap, 'instance_config', None)
        box_config_data = getattr(box_config, 'data', {}) if box_config is not None else {}
        return str(box_config_data.get('box', {}).get('runtime_url', '')).strip()

    def _should_manage_local_runtime(self) -> bool:
        return not self.configured_runtime_url and platform.get_platform() != 'docker'

    async def _start_local_runtime_process(self) -> None:
        if self.runtime_subprocess is not None and self.runtime_subprocess.returncode is None:
            return

        python_path = sys.executable
        env = os.environ.copy()
        self.runtime_subprocess = await asyncio.create_subprocess_exec(
            python_path,
            '-m',
            'langbot.pkg.box.server',
            env=env,
        )
        self.runtime_subprocess_task = asyncio.create_task(self.runtime_subprocess.wait())

    async def _wait_until_runtime_ready(self) -> None:
        last_exc: BoxRuntimeUnavailableError | None = None
        for _ in range(self._HEALTH_CHECK_RETRY_COUNT):
            if self.runtime_subprocess is not None and self.runtime_subprocess.returncode is not None:
                raise BoxRuntimeUnavailableError(
                    f'local box runtime exited before becoming ready (code {self.runtime_subprocess.returncode})'
                )

            try:
                await self.client.initialize()
                self.ap.logger.info(f'Local Box runtime is ready at {self.runtime_url}.')
                return
            except BoxRuntimeUnavailableError as exc:
                last_exc = exc
                await asyncio.sleep(self._HEALTH_CHECK_RETRY_INTERVAL_SEC)

        if last_exc is not None:
            raise last_exc
        raise BoxRuntimeUnavailableError('local box runtime did not become ready')
