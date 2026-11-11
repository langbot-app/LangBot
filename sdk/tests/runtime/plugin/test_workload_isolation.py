"""Individual worker lifecycle changes must not stop the Runtime workload."""

from __future__ import annotations

import asyncio

import pytest

from langbot_plugin.entities.io.context import ActionContext
from langbot_plugin.runtime.context import RuntimeContext
from langbot_plugin.runtime.plugin.mgr import PluginManager


def manager_with_no_legacy_directories(monkeypatch):
    context = RuntimeContext()
    context.ws_debug_port = 18080
    manager = PluginManager(context)
    context.plugin_mgr = manager
    context.bind_workspace(
        ActionContext(
            instance_uuid="test-instance",
            workspace_uuid="test-workspace",
            placement_generation=1,
        )
    )
    monkeypatch.setattr("langbot_plugin.runtime.plugin.mgr.glob.glob", lambda _: [])
    return manager


@pytest.mark.asyncio
@pytest.mark.parametrize("worker_exit", ["cancel", "raise"])
async def test_worker_exit_does_not_abort_startup_workload(monkeypatch, worker_exit):
    manager = manager_with_no_legacy_directories(monkeypatch)
    exit_first = asyncio.Event()
    finish_sibling = asyncio.Event()

    async def first_worker():
        await exit_first.wait()
        raise RuntimeError("isolated worker failure")

    first = asyncio.create_task(first_worker())
    sibling = asyncio.create_task(finish_sibling.wait())
    manager.plugin_run_tasks.extend([first, sibling])
    workload = asyncio.create_task(manager.launch_all_plugins())
    try:
        for _ in range(3):
            await asyncio.sleep(0)
        if worker_exit == "cancel":
            first.cancel()
        else:
            exit_first.set()
        await asyncio.gather(first, return_exceptions=True)
        for _ in range(3):
            await asyncio.sleep(0)
        assert not workload.done(), "One worker stopped the entire Runtime workload"
        assert not sibling.done(), "Sibling worker must stay alive"
        finish_sibling.set()
        await asyncio.wait_for(workload, 1)
        assert not workload.cancelled()
    finally:
        for task in [workload, first, sibling]:
            task.cancel()
        await asyncio.gather(workload, first, sibling, return_exceptions=True)


@pytest.mark.asyncio
async def test_parent_workload_cancellation_still_cancels_all_children(monkeypatch):
    manager = manager_with_no_legacy_directories(monkeypatch)
    children = [asyncio.create_task(asyncio.Event().wait()) for _ in range(2)]
    manager.plugin_run_tasks.extend(children)
    workload = asyncio.create_task(manager.launch_all_plugins())
    try:
        for _ in range(3):
            await asyncio.sleep(0)
        workload.cancel()
        with pytest.raises(asyncio.CancelledError):
            await workload
        assert all(task.done() and task.cancelled() for task in children)
    finally:
        for task in [workload, *children]:
            task.cancel()
        await asyncio.gather(workload, *children, return_exceptions=True)
