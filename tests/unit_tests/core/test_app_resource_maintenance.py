from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from langbot.pkg.core.app import Application


pytestmark = pytest.mark.asyncio


class _TaskManager:
    def __init__(self, stop: asyncio.Event) -> None:
        self.stop = stop
        self.tasks: list[asyncio.Task] = []

    def create_task(self, coro, *, name='', **_kwargs):
        task = asyncio.create_task(coro, name=name)
        self.tasks.append(task)
        return SimpleNamespace(task=task)

    async def wait_all(self) -> None:
        await self.stop.wait()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)


async def _wait_forever() -> None:
    await asyncio.Event().wait()


async def test_resource_maintenance_waits_and_shares_workspace_discovery() -> None:
    stop = asyncio.Event()
    completed = asyncio.Event()
    discovery_calls = 0
    job_calls: list[str] = []

    async def list_bindings():
        nonlocal discovery_calls
        discovery_calls += 1
        return [
            SimpleNamespace(
                instance_uuid='instance',
                workspace_uuid='workspace',
                placement_generation=1,
            )
        ]

    async def cleanup_monitoring(_context, _retention_days, *, batch_size):
        assert batch_size == 10
        job_calls.append('monitoring')
        return {}

    async def cleanup_storage(_context):
        job_calls.append('storage')
        completed.set()
        return {}

    application = Application()
    application.event_loop = asyncio.get_running_loop()
    application.event_loop_monitor = SimpleNamespace(start=lambda: None)
    application.task_mgr = _TaskManager(stop)
    application.plugin_connector = SimpleNamespace(initialize_plugins=lambda: asyncio.sleep(0))
    application.platform_mgr = SimpleNamespace(run=_wait_forever)
    application.ctrl = SimpleNamespace(run=_wait_forever)
    application.http_ctrl = SimpleNamespace(run=_wait_forever)
    application.telemetry = None
    application.workspace_collaboration_service = None
    application.workspace_service = SimpleNamespace(list_active_execution_bindings=list_bindings)
    application.monitoring_service = SimpleNamespace(cleanup_expired_records=cleanup_monitoring)
    application.maintenance_service = SimpleNamespace(cleanup_expired_files=cleanup_storage)
    application.instance_config = SimpleNamespace(
        data={
            'monitoring': {
                'auto_cleanup': {
                    'enabled': True,
                    'retention_days': 30,
                    'delete_batch_size': 10,
                    'check_interval_hours': 0.00002,
                }
            },
            'storage': {
                'cleanup': {
                    'enabled': True,
                    'check_interval_hours': 0.00002,
                }
            },
        }
    )
    application.logger = SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
        debug=lambda *_args, **_kwargs: None,
    )

    async def no_web_info() -> None:
        return None

    application.print_web_access_info = no_web_info
    run_task = asyncio.create_task(application.run())
    try:
        await asyncio.sleep(0.01)
        assert discovery_calls == 0
        await asyncio.wait_for(completed.wait(), timeout=1)
        assert discovery_calls == 1
        assert job_calls == ['monitoring', 'storage']
    finally:
        stop.set()
        await asyncio.wait_for(run_task, timeout=1)
