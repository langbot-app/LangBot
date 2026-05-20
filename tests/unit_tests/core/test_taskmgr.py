"""Unit tests for core TaskContext, TaskWrapper, and AsyncTaskManager.

Tests cover:
- TaskContext initialization, state tracking, serialization
- TaskWrapper ID generation, to_dict serialization
- AsyncTaskManager task creation, stats, pruning

Note: Uses import_isolation to break circular import chains.
"""
from __future__ import annotations

import pytest
import asyncio
import sys
from unittest.mock import Mock, MagicMock
from contextlib import contextmanager
from typing import Generator


class MockLifecycleControlScopeEnum:
    """Mock enum value for LifecycleControlScope with .value attribute."""
    def __init__(self, value: str):
        self.value = value

    def __repr__(self):
        return f"LifecycleControlScope.{self.value.upper()}"


class MockLifecycleControlScope:
    """Mock enum for LifecycleControlScope."""
    APPLICATION = MockLifecycleControlScopeEnum('application')
    PLATFORM = MockLifecycleControlScopeEnum('platform')
    PIPELINE = MockLifecycleControlScopeEnum('pipeline')
    PLUGIN = MockLifecycleControlScopeEnum('plugin')


@contextmanager
def isolated_taskmgr_import() -> Generator[None, None, None]:
    """Context manager to isolate circular imports for taskmgr testing."""
    # Mock modules that cause circular imports
    mock_entities = MagicMock()
    mock_entities.LifecycleControlScope = MockLifecycleControlScope
    
    mock_app = MagicMock()
    
    mock_importutil = MagicMock()
    mock_importutil.import_modules_in_pkg = lambda pkg: None
    mock_importutil.import_modules_in_pkgs = lambda pkgs: None
    
    mock_http_controller = MagicMock()
    
    mock_rag_mgr = MagicMock()
    
    mocks = {
        'langbot.pkg.core.entities': mock_entities,
        'langbot.pkg.core.app': mock_app,
        'langbot.pkg.api.http.controller.main': mock_http_controller,
        'langbot.pkg.rag.knowledge.kbmgr': mock_rag_mgr,
        'langbot.pkg.utils.importutil': mock_importutil,
    }
    
    # Save original state
    saved = {}
    for name in mocks:
        if name in sys.modules:
            saved[name] = sys.modules[name]
    
    # Clear taskmgr to force re-import
    taskmgr_name = 'langbot.pkg.core.taskmgr'
    if taskmgr_name in sys.modules:
        saved[taskmgr_name] = sys.modules[taskmgr_name]
    
    try:
        # Apply mocks
        for name, module in mocks.items():
            sys.modules[name] = module
        
        # Clear taskmgr
        sys.modules.pop(taskmgr_name, None)
        
        yield
    finally:
        # Restore
        for name in mocks:
            if name in saved:
                sys.modules[name] = saved[name]
            else:
                sys.modules.pop(name, None)
        
        if taskmgr_name in saved:
            sys.modules[taskmgr_name] = saved[taskmgr_name]
        else:
            sys.modules.pop(taskmgr_name, None)


def get_taskmgr_classes():
    """Get TaskContext, TaskWrapper, AsyncTaskManager classes."""
    with isolated_taskmgr_import():
        from langbot.pkg.core.taskmgr import TaskContext, TaskWrapper, AsyncTaskManager
        return TaskContext, TaskWrapper, AsyncTaskManager


def create_mock_app():
    """Create a mock Application for testing."""
    mock_app = Mock()
    mock_app.event_loop = asyncio.get_running_loop()
    mock_app.instance_config = Mock()
    mock_app.instance_config.data = {
        'system': {
            'task_retention': {
                'completed_limit': 200,
            }
        }
    }
    return mock_app


class TestTaskContext:
    """Tests for TaskContext class."""

    def test_init_default_values(self):
        """Test that TaskContext initializes with default values."""
        TaskContext, _, _ = get_taskmgr_classes()
        ctx = TaskContext()

        assert ctx.current_action == 'default'
        assert ctx.log == ''
        assert ctx.metadata == {}

    def test_set_current_action(self):
        """Test setting current action."""
        TaskContext, _, _ = get_taskmgr_classes()
        ctx = TaskContext()

        ctx.set_current_action('installing_plugin')
        assert ctx.current_action == 'installing_plugin'

    def test_trace_without_action(self):
        """Test trace method without action override."""
        TaskContext, _, _ = get_taskmgr_classes()
        ctx = TaskContext()

        ctx.trace('Starting process')
        assert 'Starting process' in ctx.log
        assert ctx.current_action == 'default'

    def test_trace_with_action_override(self):
        """Test trace method with action override."""
        TaskContext, _, _ = get_taskmgr_classes()
        ctx = TaskContext()

        ctx.trace('Downloading', action='download')
        assert 'Downloading' in ctx.log
        assert ctx.current_action == 'download'

    def test_trace_accumulates_logs(self):
        """Test that trace accumulates log entries."""
        TaskContext, _, _ = get_taskmgr_classes()
        ctx = TaskContext()

        ctx.trace('Step 1')
        ctx.trace('Step 2')
        ctx.trace('Step 3')

        assert 'Step 1' in ctx.log
        assert 'Step 2' in ctx.log
        assert 'Step 3' in ctx.log
        # Each trace adds a newline
        assert ctx.log.count('\n') == 3

    def test_to_dict_serialization(self):
        """Test to_dict serialization."""
        TaskContext, _, _ = get_taskmgr_classes()
        ctx = TaskContext()
        ctx.set_current_action('test_action')
        ctx.trace('Test message')
        ctx.metadata['key'] = 'value'

        result = ctx.to_dict()

        assert result['current_action'] == 'test_action'
        assert 'Test message' in result['log']
        assert result['metadata'] == {'key': 'value'}

    def test_static_new_factory(self):
        """Test TaskContext.new() factory method."""
        TaskContext, _, _ = get_taskmgr_classes()
        ctx = TaskContext.new()

        assert isinstance(ctx, TaskContext)
        assert ctx.current_action == 'default'

    def test_static_placeholder_singleton(self):
        """Test TaskContext.placeholder() returns singleton."""
        with isolated_taskmgr_import():
            from langbot.pkg.core.taskmgr import TaskContext
            
            # Reset global placeholder
            import langbot.pkg.core.taskmgr as taskmgr_module
            taskmgr_module.placeholder_context = None

            ctx1 = TaskContext.placeholder()
            ctx2 = TaskContext.placeholder()

            assert ctx1 is ctx2

    def test_metadata_is_mutable_dict(self):
        """Test that metadata is a mutable dict."""
        TaskContext, _, _ = get_taskmgr_classes()
        ctx = TaskContext()

        ctx.metadata['count'] = 5
        ctx.metadata['items'] = ['a', 'b', 'c']

        assert ctx.metadata['count'] == 5
        assert len(ctx.metadata['items']) == 3


class TestTaskWrapper:
    """Tests for TaskWrapper class."""

    @pytest.mark.asyncio
    async def test_id_auto_increment(self):
        """Test that task IDs auto-increment."""
        TaskContext, TaskWrapper, _ = get_taskmgr_classes()

        # Reset ID index
        TaskWrapper._id_index = 0

        mock_app = create_mock_app()

        async def dummy_coro():
            await asyncio.sleep(0.01)
            return 'done'

        wrapper1 = TaskWrapper(mock_app, dummy_coro())
        wrapper2 = TaskWrapper(mock_app, dummy_coro())

        assert wrapper1.id == 0
        assert wrapper2.id == 1

        # Clean up
        wrapper1.cancel()
        wrapper2.cancel()

    @pytest.mark.asyncio
    async def test_default_task_type_and_kind(self):
        """Test default task_type and kind values."""
        _, TaskWrapper, _ = get_taskmgr_classes()
        mock_app = create_mock_app()

        async def dummy_coro():
            return 'done'

        wrapper = TaskWrapper(mock_app, dummy_coro())

        assert wrapper.task_type == 'system'
        assert wrapper.kind == 'system_task'

        wrapper.cancel()

    @pytest.mark.asyncio
    async def test_to_dict_serialization(self):
        """Test TaskWrapper.to_dict serialization."""
        _, TaskWrapper, _ = get_taskmgr_classes()
        mock_app = create_mock_app()

        async def immediate_coro():
            return 'result'

        wrapper = TaskWrapper(
            mock_app, immediate_coro(),
            name='test_task',
            label='Test Task',
        )

        # Wait for task to complete
        await wrapper.task

        result = wrapper.to_dict()

        assert result['name'] == 'test_task'
        assert result['label'] == 'Test Task'
        assert result['task_type'] == 'system'
        assert result['runtime']['done'] == True
        assert result['runtime']['result'] == 'result'

    @pytest.mark.asyncio
    async def test_to_dict_with_exception(self):
        """Test TaskWrapper.to_dict when task has exception."""
        _, TaskWrapper, _ = get_taskmgr_classes()
        mock_app = create_mock_app()

        async def failing_coro():
            raise ValueError('Test error')

        wrapper = TaskWrapper(mock_app, failing_coro())

        # Wait for task to complete
        try:
            await wrapper.task
        except ValueError:
            pass

        result = wrapper.to_dict()

        assert result['runtime']['done'] == True
        assert result['runtime']['exception'] == 'Test error'
        assert 'exception_traceback' in result['runtime']

    @pytest.mark.asyncio
    async def test_cancel_task(self):
        """Test cancel method cancels the asyncio task."""
        _, TaskWrapper, _ = get_taskmgr_classes()
        mock_app = create_mock_app()

        async def long_coro():
            await asyncio.sleep(10)
            return 'done'

        wrapper = TaskWrapper(mock_app, long_coro())

        # Task should be running
        assert not wrapper.task.done()

        wrapper.cancel()

        # Give it a moment to be cancelled
        await asyncio.sleep(0.01)

        assert wrapper.task.done()
        assert wrapper.task.cancelled()


class TestAsyncTaskManager:
    """Tests for AsyncTaskManager class."""

    @pytest.mark.asyncio
    async def test_create_task_adds_to_list(self):
        """Test that create_task adds task to tasks list."""
        _, _, AsyncTaskManager = get_taskmgr_classes()
        mock_app = create_mock_app()

        manager = AsyncTaskManager(mock_app)

        async def dummy_coro():
            await asyncio.sleep(0.01)
            return 'done'

        wrapper = manager.create_task(dummy_coro())

        assert wrapper in manager.tasks
        assert len(manager.tasks) == 1

        wrapper.cancel()

    @pytest.mark.asyncio
    async def test_get_stats_counts_correctly(self):
        """Test get_stats returns correct counts."""
        _, _, AsyncTaskManager = get_taskmgr_classes()
        mock_app = create_mock_app()

        manager = AsyncTaskManager(mock_app)

        async def immediate_coro():
            return 'done'

        async def delayed_coro():
            await asyncio.sleep(0.1)
            return 'done'

        # Create tasks
        w1 = manager.create_task(immediate_coro())
        w2 = manager.create_task(delayed_coro())

        # Wait for first to complete
        await w1.task

        stats = manager.get_stats()

        assert stats['total'] == 2
        assert stats['completed'] == 1
        assert stats['running'] == 1

        w2.cancel()

    @pytest.mark.asyncio
    async def test_get_tasks_dict_filters_by_type(self):
        """Test get_tasks_dict filters by type."""
        _, _, AsyncTaskManager = get_taskmgr_classes()
        mock_app = create_mock_app()

        manager = AsyncTaskManager(mock_app)

        async def dummy_coro():
            await asyncio.sleep(0.01)

        # Create system and user tasks
        w1 = manager.create_task(dummy_coro(), task_type='system')
        w2 = manager.create_task(dummy_coro(), task_type='user')
        w3 = manager.create_task(dummy_coro(), task_type='user')

        result = manager.get_tasks_dict(type='user')

        assert len(result['tasks']) == 2
        for t in result['tasks']:
            assert t['task_type'] == 'user'

        w1.cancel()
        w2.cancel()
        w3.cancel()

    @pytest.mark.asyncio
    async def test_cancel_by_scope(self):
        """Test cancel_by_scope cancels matching tasks."""
        _, _, AsyncTaskManager = get_taskmgr_classes()
        
        mock_app = create_mock_app()
        manager = AsyncTaskManager(mock_app)

        async def long_coro():
            await asyncio.sleep(10)

        # Create task with APPLICATION scope
        w1 = manager.create_task(
            long_coro(),
            scopes=[MockLifecycleControlScope.APPLICATION]
        )

        # Create task with different scope
        w2 = manager.create_task(
            long_coro(),
            scopes=[MockLifecycleControlScope.PIPELINE]
        )

        manager.cancel_by_scope(MockLifecycleControlScope.APPLICATION)

        await asyncio.sleep(0.01)

        assert w1.task.cancelled() or w1.task.done()
        assert not w2.task.done()

        w2.cancel()

    @pytest.mark.asyncio
    async def test_cancel_task_by_id(self):
        """Test cancel_task cancels specific task by ID."""
        _, _, AsyncTaskManager = get_taskmgr_classes()
        mock_app = create_mock_app()

        manager = AsyncTaskManager(mock_app)

        async def long_coro():
            await asyncio.sleep(10)

        w1 = manager.create_task(long_coro())
        w2 = manager.create_task(long_coro())

        manager.cancel_task(w1.id)

        await asyncio.sleep(0.01)

        assert w1.task.done()
        assert not w2.task.done()

        w2.cancel()

    @pytest.mark.asyncio
    async def test_create_user_task_sets_user_type(self):
        """Test create_user_task sets task_type to 'user'."""
        _, _, AsyncTaskManager = get_taskmgr_classes()
        mock_app = create_mock_app()

        manager = AsyncTaskManager(mock_app)

        async def dummy_coro():
            await asyncio.sleep(0.01)

        wrapper = manager.create_user_task(dummy_coro())

        assert wrapper.task_type == 'user'

        wrapper.cancel()

    @pytest.mark.asyncio
    async def test_get_task_by_id(self):
        """Test get_task_by_id returns correct task."""
        _, _, AsyncTaskManager = get_taskmgr_classes()
        mock_app = create_mock_app()

        manager = AsyncTaskManager(mock_app)

        async def dummy_coro():
            await asyncio.sleep(0.01)

        w1 = manager.create_task(dummy_coro())
        w2 = manager.create_task(dummy_coro())

        found = manager.get_task_by_id(w1.id)
        assert found is w1

        not_found = manager.get_task_by_id(9999)
        assert not_found is None

        w1.cancel()
        w2.cancel()
