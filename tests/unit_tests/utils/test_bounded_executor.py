from __future__ import annotations

import asyncio
import threading

import pytest

from langbot.pkg.utils.bounded_executor import (
    BlockingWorkCapacityError,
    BoundedThreadPoolExecutor,
    blocking_work_scope,
    configure_bounded_default_executor,
    run_blocking_atomic,
    run_blocking_cleanup,
)


def test_bounded_executor_rejects_instead_of_queueing_without_limit():
    executor = BoundedThreadPoolExecutor(
        max_workers=1,
        max_pending=1,
        max_inflight_per_scope=1,
    )
    started = threading.Event()
    release = threading.Event()

    def block() -> str:
        started.set()
        release.wait(timeout=5)
        return 'done'

    first = executor.submit(block)
    assert started.wait(timeout=1)
    second = executor.submit(lambda: 'queued')

    with pytest.raises(
        BlockingWorkCapacityError,
        match='capacity reached',
    ):
        executor.submit(lambda: 'rejected')

    assert executor.snapshot() == {
        'max_workers': 1,
        'max_pending': 1,
        'max_inflight_per_scope': 1,
        'inflight': 2,
        'running': 1,
        'pending': 1,
        'active_scopes': 0,
        'submitted_total': 2,
        'completed_total': 0,
        'rejected_total': 1,
        'global_rejected_total': 1,
        'scope_rejected_total': 0,
    }

    release.set()
    assert first.result(timeout=1) == 'done'
    assert second.result(timeout=1) == 'queued'
    assert executor.snapshot()['inflight'] == 0
    executor.shutdown()


def test_workspace_scope_cannot_monopolize_global_workers():
    executor = BoundedThreadPoolExecutor(
        max_workers=2,
        max_pending=2,
        max_inflight_per_scope=1,
    )
    release = threading.Event()
    workspace_a_started = threading.Event()
    workspace_b_started = threading.Event()

    def block(started: threading.Event) -> str:
        started.set()
        release.wait(timeout=5)
        return 'done'

    try:
        with blocking_work_scope('workspace-a'):
            workspace_a = executor.submit(block, workspace_a_started)
            assert workspace_a_started.wait(timeout=1)
            with pytest.raises(
                BlockingWorkCapacityError,
                match='Workspace blocking executor capacity reached',
            ):
                executor.submit(lambda: 'rejected')

        with blocking_work_scope('workspace-b'):
            workspace_b = executor.submit(block, workspace_b_started)
            assert workspace_b_started.wait(timeout=1)

        snapshot = executor.snapshot()
        assert snapshot['inflight'] == 2
        assert snapshot['active_scopes'] == 2
        assert snapshot['scope_rejected_total'] == 1
        assert snapshot['global_rejected_total'] == 0
    finally:
        release.set()
        assert workspace_a.result(timeout=1) == 'done'
        assert workspace_b.result(timeout=1) == 'done'
        executor.shutdown()


def test_default_executor_bounds_asyncio_to_thread():
    loop = asyncio.new_event_loop()
    executor = configure_bounded_default_executor(
        loop,
        max_workers=2,
        max_pending=3,
    )
    try:
        assert loop.run_until_complete(asyncio.to_thread(lambda: 'bounded')) == 'bounded'
        assert executor.snapshot()['completed_total'] == 1
        assert (
            configure_bounded_default_executor(
                loop,
                max_workers=2,
                max_pending=3,
            )
            is executor
        )
    finally:
        executor.shutdown()
        loop.close()


def test_workspace_scope_is_enforced_for_asyncio_to_thread():
    loop = asyncio.new_event_loop()
    executor = configure_bounded_default_executor(
        loop,
        max_workers=2,
        max_pending=2,
        max_inflight_per_scope=1,
    )
    started = threading.Event()
    release = threading.Event()

    def block() -> str:
        started.set()
        release.wait(timeout=5)
        return 'workspace-a'

    async def exercise() -> None:
        with blocking_work_scope('workspace-a'):
            workspace_a = asyncio.create_task(asyncio.to_thread(block))
        try:
            while not started.is_set():
                await asyncio.sleep(0)

            with blocking_work_scope('workspace-a'):
                with pytest.raises(
                    BlockingWorkCapacityError,
                    match='Workspace blocking executor capacity reached',
                ):
                    await asyncio.to_thread(lambda: 'rejected')

            with blocking_work_scope('workspace-b'):
                assert await asyncio.to_thread(lambda: 'workspace-b') == 'workspace-b'
        finally:
            release.set()
            assert await workspace_a == 'workspace-a'

    try:
        loop.run_until_complete(exercise())
    finally:
        executor.shutdown()
        loop.close()


def test_blocking_cleanup_waits_for_capacity_instead_of_leaking_work():
    loop = asyncio.new_event_loop()
    executor = configure_bounded_default_executor(
        loop,
        max_workers=1,
        max_pending=0,
        max_inflight_per_scope=1,
    )
    started = threading.Event()
    release = threading.Event()
    cleaned = threading.Event()

    def block() -> None:
        started.set()
        release.wait(timeout=5)

    async def exercise() -> None:
        blocker = asyncio.create_task(asyncio.to_thread(block))
        while not started.is_set():
            await asyncio.sleep(0)
        cleanup = asyncio.create_task(run_blocking_cleanup(cleaned.set))
        await asyncio.sleep(0.03)
        assert not cleanup.done()
        release.set()
        await blocker
        await cleanup

    try:
        loop.run_until_complete(exercise())
        assert cleaned.is_set()
        assert executor.snapshot()['global_rejected_total'] >= 1
    finally:
        release.set()
        executor.shutdown()
        loop.close()


def test_blocking_atomic_waits_for_thread_before_propagating_cancellation():
    loop = asyncio.new_event_loop()
    executor = configure_bounded_default_executor(
        loop,
        max_workers=1,
        max_pending=1,
        max_inflight_per_scope=1,
    )
    started = threading.Event()
    release = threading.Event()
    completed = threading.Event()

    def block() -> None:
        started.set()
        release.wait(timeout=5)
        completed.set()

    async def exercise() -> None:
        operation = asyncio.create_task(run_blocking_atomic(block))
        while not started.is_set():
            await asyncio.sleep(0)
        operation.cancel()
        await asyncio.sleep(0)
        assert not operation.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await operation

    try:
        loop.run_until_complete(exercise())
        assert completed.is_set()
    finally:
        release.set()
        executor.shutdown()
        loop.close()


@pytest.mark.parametrize(
    ('max_workers', 'max_pending'),
    [
        (0, 1),
        (65, 1),
        (1, -1),
        (1, 4097),
        (True, 1),
    ],
)
def test_bounded_executor_rejects_unsafe_limits(
    max_workers,
    max_pending,
):
    with pytest.raises(ValueError):
        BoundedThreadPoolExecutor(
            max_workers=max_workers,
            max_pending=max_pending,
        )


@pytest.mark.parametrize(
    ('max_workers', 'max_inflight_per_scope'),
    [(8, 0), (8, 4097), (8, True), (8, 5), (2, 2)],
)
def test_bounded_executor_rejects_unsafe_scope_limits(
    max_workers,
    max_inflight_per_scope,
):
    with pytest.raises(ValueError):
        BoundedThreadPoolExecutor(
            max_workers=max_workers,
            max_inflight_per_scope=max_inflight_per_scope,
        )
