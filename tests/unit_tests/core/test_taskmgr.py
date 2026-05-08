"""
Unit tests for AsyncTaskManager and TaskWrapper.

Tests cover async task lifecycle management:
- Task scheduling and tracking
- Task completion
- Task exception handling
- Task cancellation
- Multiple task isolation

Uses module pre-mocking to break circular import chain.
"""

from __future__ import annotations

import pytest
import asyncio
import sys
import enum
from unittest.mock import MagicMock
from importlib import import_module


# Pre-mock app module BEFORE importing taskmgr to break circular chain:
#   taskmgr → app → http_controller → groups/knowledge/migration → taskmgr (partial)
class FakeMinimalApp:
    """Minimal app that only provides event_loop."""

    def __init__(self, event_loop):
        self.event_loop = event_loop
        self.instance_config = MagicMock()
        self.instance_config.data = {}

# Pre-register mock app module
_mock_app_module = MagicMock()
_mock_app_module.Application = FakeMinimalApp
sys.modules['langbot.pkg.core.app'] = _mock_app_module

# Pre-register mock entities module - use proper Enum
class LifecycleControlScope(enum.Enum):
    APPLICATION = 'application'
    PLATFORM = 'platform'
    PLUGIN = 'plugin'
    PROVIDER = 'provider'

_mock_entities_module = MagicMock()
_mock_entities_module.LifecycleControlScope = LifecycleControlScope
sys.modules['langbot.pkg.core.entities'] = _mock_entities_module


def get_taskmgr():
    """Import taskmgr after pre-mocking."""
    return import_module('langbot.pkg.core.taskmgr')


def get_entities():
    """Get pre-registered mock entities module."""
    return sys.modules['langbot.pkg.core.entities']


class TestTaskContextReal:
    """Tests for real TaskContext class (no circular import)."""

    @pytest.mark.asyncio
    async def test_task_context_new(self):
        """TaskContext.new() creates instance."""
        taskmgr = get_taskmgr()

        ctx = taskmgr.TaskContext.new()

        assert ctx.current_action == 'default'
        assert ctx.log == ''
        assert ctx.metadata == {}

    @pytest.mark.asyncio
    async def test_task_context_trace(self):
        """TaskContext.trace adds formatted log."""
        taskmgr = get_taskmgr()

        ctx = taskmgr.TaskContext.new()
        ctx.trace('test message', action='test_action')

        assert ctx.current_action == 'test_action'
        assert 'test message' in ctx.log
        assert 'test_action' in ctx.log
        # Contains timestamp format
        assert '|' in ctx.log

    @pytest.mark.asyncio
    async def test_task_context_multiple_traces(self):
        """TaskContext accumulates multiple traces."""
        taskmgr = get_taskmgr()

        ctx = taskmgr.TaskContext.new()
        ctx.trace('first')
        ctx.trace('second')

        assert 'first' in ctx.log
        assert 'second' in ctx.log

    @pytest.mark.asyncio
    async def test_task_context_to_dict(self):
        """TaskContext.to_dict returns all fields."""
        taskmgr = get_taskmgr()

        ctx = taskmgr.TaskContext.new()
        ctx.trace('log entry')

        result = ctx.to_dict()

        assert 'current_action' in result
        assert 'log' in result
        assert 'metadata' in result
        assert result['log'] == ctx.log

    @pytest.mark.asyncio
    async def test_task_context_set_current_action(self):
        """set_current_action updates action."""
        taskmgr = get_taskmgr()

        ctx = taskmgr.TaskContext.new()
        ctx.set_current_action('new_action')

        assert ctx.current_action == 'new_action'

    @pytest.mark.asyncio
    async def test_task_context_metadata(self):
        """TaskContext metadata can be set."""
        taskmgr = get_taskmgr()

        ctx = taskmgr.TaskContext.new()
        ctx.metadata['key'] = 'value'

        assert ctx.metadata['key'] == 'value'
        assert ctx.to_dict()['metadata']['key'] == 'value'

    def test_task_context_placeholder_singleton(self):
        """placeholder returns same instance."""
        taskmgr = get_taskmgr()

        ctx1 = taskmgr.TaskContext.placeholder()
        ctx2 = taskmgr.TaskContext.placeholder()

        assert ctx1 is ctx2


class TestTaskWrapperReal:
    """Tests for real TaskWrapper class."""

    @pytest.mark.asyncio
    async def test_task_wrapper_creates_task(self):
        """TaskWrapper creates and wraps asyncio.Task."""
        taskmgr = get_taskmgr()

        loop = asyncio.get_running_loop()
        app = FakeMinimalApp(loop)

        async def simple_coro():
            return 42

        wrapper = taskmgr.TaskWrapper(app, simple_coro(), name='test')

        assert wrapper.name == 'test'
        assert wrapper.task is not None
        assert isinstance(wrapper.task, asyncio.Task)

        result = await wrapper.task
        assert result == 42

    @pytest.mark.asyncio
    async def test_task_wrapper_with_custom_context(self):
        """TaskWrapper uses provided TaskContext."""
        taskmgr = get_taskmgr()

        loop = asyncio.get_running_loop()
        app = FakeMinimalApp(loop)

        ctx = taskmgr.TaskContext.new()
        ctx.set_current_action('custom')

        async def coro():
            return 'done'

        wrapper = taskmgr.TaskWrapper(app, coro(), context=ctx)

        assert wrapper.task_context.current_action == 'custom'

        await wrapper.task

    @pytest.mark.asyncio
    async def test_task_wrapper_exception_capture(self):
        """TaskWrapper captures exception from failed task."""
        taskmgr = get_taskmgr()

        loop = asyncio.get_running_loop()
        app = FakeMinimalApp(loop)

        async def failing_coro():
            raise ValueError('test error')

        wrapper = taskmgr.TaskWrapper(app, failing_coro())

        # Let task complete with exception
        await asyncio.sleep(0.01)

        exception = wrapper.assume_exception()
        assert exception is not None
        assert isinstance(exception, ValueError)
        assert 'test error' in str(exception)

    @pytest.mark.asyncio
    async def test_task_wrapper_result_capture(self):
        """TaskWrapper captures result from completed task."""
        taskmgr = get_taskmgr()

        loop = asyncio.get_running_loop()
        app = FakeMinimalApp(loop)

        async def coro():
            return 'result_value'

        wrapper = taskmgr.TaskWrapper(app, coro())

        await wrapper.task

        result = wrapper.assume_result()
        assert result == 'result_value'

    @pytest.mark.asyncio
    async def test_task_wrapper_cancel(self):
        """TaskWrapper.cancel cancels the task."""
        taskmgr = get_taskmgr()

        loop = asyncio.get_running_loop()
        app = FakeMinimalApp(loop)

        async def long_coro():
            await asyncio.sleep(10)
            return 'done'

        wrapper = taskmgr.TaskWrapper(app, long_coro())

        wrapper.cancel()

        await asyncio.sleep(0.01)

        assert wrapper.task.cancelled() or wrapper.task.done()

    @pytest.mark.asyncio
    async def test_task_wrapper_to_dict(self):
        """TaskWrapper.to_dict serializes task info."""
        taskmgr = get_taskmgr()

        loop = asyncio.get_running_loop()
        app = FakeMinimalApp(loop)

        async def coro():
            return 42

        wrapper = taskmgr.TaskWrapper(app, coro(), name='dict_test', label='Test')

        await wrapper.task

        result = wrapper.to_dict()

        assert result['name'] == 'dict_test'
        assert result['label'] == 'Test'
        assert 'runtime' in result
        assert result['runtime']['done'] is True

    @pytest.mark.asyncio
    async def test_task_wrapper_id_increment(self):
        """TaskWrapper IDs increment."""
        taskmgr = get_taskmgr()

        loop = asyncio.get_running_loop()
        app = FakeMinimalApp(loop)

        async def coro():
            return 1

        wrapper1 = taskmgr.TaskWrapper(app, coro())
        wrapper2 = taskmgr.TaskWrapper(app, coro())

        assert wrapper2.id > wrapper1.id


class TestAsyncTaskManagerReal:
    """Tests for real AsyncTaskManager class."""

    @pytest.mark.asyncio
    async def test_manager_create_task(self):
        """AsyncTaskManager creates and tracks tasks."""
        taskmgr = get_taskmgr()

        loop = asyncio.get_running_loop()
        app = FakeMinimalApp(loop)

        manager = taskmgr.AsyncTaskManager(app)

        async def coro():
            return 'result'

        wrapper = manager.create_task(coro(), name='test')

        assert wrapper in manager.tasks
        assert wrapper.name == 'test'

        await wrapper.task

    @pytest.mark.asyncio
    async def test_manager_create_user_task(self):
        """create_user_task creates user-type task."""
        taskmgr = get_taskmgr()

        loop = asyncio.get_running_loop()
        app = FakeMinimalApp(loop)

        manager = taskmgr.AsyncTaskManager(app)

        async def coro():
            return 'user_result'

        wrapper = manager.create_user_task(coro())

        assert wrapper.task_type == 'user'

        await wrapper.task

    @pytest.mark.asyncio
    async def test_manager_multiple_tasks_isolated(self):
        """Multiple tasks run independently."""
        taskmgr = get_taskmgr()

        loop = asyncio.get_running_loop()
        app = FakeMinimalApp(loop)

        manager = taskmgr.AsyncTaskManager(app)

        results = []

        async def task_a():
            results.append('a')

        async def task_b():
            results.append('b')

        w1 = manager.create_task(task_a(), name='a')
        w2 = manager.create_task(task_b(), name='b')

        await asyncio.gather(w1.task, w2.task)

        assert 'a' in results
        assert 'b' in results

    @pytest.mark.asyncio
    async def test_manager_get_task_by_id(self):
        """get_task_by_id finds task."""
        taskmgr = get_taskmgr()

        loop = asyncio.get_running_loop()
        app = FakeMinimalApp(loop)

        manager = taskmgr.AsyncTaskManager(app)

        async def coro():
            return 1

        wrapper = manager.create_task(coro())

        found = manager.get_task_by_id(wrapper.id)
        assert found is wrapper

        not_found = manager.get_task_by_id(99999)
        assert not_found is None

    @pytest.mark.asyncio
    async def test_manager_cancel_task(self):
        """cancel_task cancels specific task."""
        taskmgr = get_taskmgr()

        loop = asyncio.get_running_loop()
        app = FakeMinimalApp(loop)

        manager = taskmgr.AsyncTaskManager(app)

        async def long():
            await asyncio.sleep(10)

        wrapper = manager.create_task(long())

        manager.cancel_task(wrapper.id)

        await asyncio.sleep(0.01)

        assert wrapper.task.cancelled() or wrapper.task.done()

    @pytest.mark.asyncio
    async def test_manager_cancel_by_scope(self):
        """cancel_by_scope cancels matching scope tasks."""
        taskmgr = get_taskmgr()
        entities = get_entities()

        loop = asyncio.get_running_loop()
        app = FakeMinimalApp(loop)

        manager = taskmgr.AsyncTaskManager(app)

        async def long():
            await asyncio.sleep(10)

        async def app_long():
            await asyncio.sleep(10)

        # Create task with PLATFORM scope
        platform_wrapper = manager.create_task(
            long(),
            scopes=[entities.LifecycleControlScope.PLATFORM],
        )

        # Create task with APPLICATION scope
        manager.create_task(
            app_long(),
            scopes=[entities.LifecycleControlScope.APPLICATION],
        )

        manager.cancel_by_scope(entities.LifecycleControlScope.PLATFORM)

        await asyncio.sleep(0.01)

        # Platform task cancelled
        assert platform_wrapper.task.cancelled() or platform_wrapper.task.done()

    @pytest.mark.asyncio
    async def test_manager_get_stats(self):
        """get_stats returns task counts."""
        taskmgr = get_taskmgr()

        loop = asyncio.get_running_loop()
        app = FakeMinimalApp(loop)

        manager = taskmgr.AsyncTaskManager(app)

        async def quick():
            return 1

        for _ in range(3):
            w = manager.create_task(quick())
            await w.task

        stats = manager.get_stats()

        assert stats['total'] >= 3
        assert stats['completed'] >= 3

    @pytest.mark.asyncio
    async def test_manager_get_tasks_dict(self):
        """get_tasks_dict filters by type."""
        taskmgr = get_taskmgr()

        loop = asyncio.get_running_loop()
        app = FakeMinimalApp(loop)

        manager = taskmgr.AsyncTaskManager(app)

        async def coro():
            return 1

        system_w = manager.create_task(coro(), task_type='system')
        user_w = manager.create_user_task(coro())

        await asyncio.gather(system_w.task, user_w.task)

        system_tasks = manager.get_tasks_dict(type='system')
        assert all(t['task_type'] == 'system' for t in system_tasks['tasks'])

    @pytest.mark.asyncio
    async def test_manager_wait_all(self):
        """wait_all waits for all tasks."""
        taskmgr = get_taskmgr()

        loop = asyncio.get_running_loop()
        app = FakeMinimalApp(loop)

        manager = taskmgr.AsyncTaskManager(app)

        async def delayed():
            await asyncio.sleep(0.05)

        for _ in range(3):
            manager.create_task(delayed())

        await manager.wait_all()

        stats = manager.get_stats()
        assert stats['running'] == 0


class TestTaskPruningReal:
    """Tests for real task pruning behavior."""

    @pytest.mark.asyncio
    async def test_prune_completed_tasks(self):
        """Completed tasks are pruned when exceeding limit."""
        taskmgr = get_taskmgr()

        loop = asyncio.get_running_loop()
        app = FakeMinimalApp(loop)
        app.instance_config.data = {'system': {'task_retention': {'completed_limit': 3}}}

        manager = taskmgr.AsyncTaskManager(app)

        async def quick():
            return 1

        # Create more than limit
        for _ in range(5):
            w = manager.create_task(quick())
            await w.task
            await asyncio.sleep(0.01)

        # Completed count should be <= limit
        completed = sum(1 for w in manager.tasks if w.task.done())
        assert completed <= 3