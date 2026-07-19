"""
Unit tests for QueryPool.

Tests query management, ID generation, and async context handling.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from unittest.mock import Mock, patch

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.pipeline.pool import (
    ExecutionContextMismatchError,
    ExecutionContextRequiredError,
    QueryNotFoundError,
    QueryPool,
    get_query_execution_context,
)


TEST_CONTEXT = ExecutionContext(
    instance_uuid='instance-test',
    workspace_uuid='workspace-test',
    placement_generation=1,
)


def oss_pool():
    """Build the explicit singleton resolver used by the OSS compatibility path."""
    return QueryPool(singleton_context_resolver=lambda: TEST_CONTEXT)


async def add_scoped_mock_query(pool, context, *, bot_uuid='bot-a'):
    """Create a Query through the real pool while keeping SDK details mocked."""
    query = Mock()
    query.bot_uuid = bot_uuid
    query.pipeline_uuid = None
    query.query_id = pool.query_id_counter
    with patch('langbot.pkg.pipeline.pool.pipeline_query.Query', return_value=query):
        return await pool.add_query(
            bot_uuid=bot_uuid,
            launcher_type=Mock(),
            launcher_id='launcher-1',
            sender_id='sender-1',
            message_event=Mock(),
            message_chain=Mock(),
            adapter=Mock(),
            execution_context=context,
        )


pytestmark = pytest.mark.asyncio


class TestQueryPoolInit:
    """Tests for QueryPool initialization."""

    def test_init_creates_empty_pool(self):
        """QueryPool initializes with empty lists."""
        pool = QueryPool()

        assert pool.queries == []
        assert pool.cached_queries == {}
        assert pool.query_id_counter == 0
        assert pool.pool_lock is not None
        assert pool.condition is not None

    def test_init_counter_starts_at_zero(self):
        """Counter starts at zero."""
        pool = QueryPool()
        assert pool.query_id_counter == 0


class TestQueryPoolAddQuery:
    """Tests for add_query method."""

    async def test_add_query_adds_query_with_id(self):
        """add_query creates, stores, and caches a Query with the correct ID."""
        pool = oss_pool()

        # Mock Query creation
        mock_query = Mock()
        mock_query.query_id = 0
        mock_query.bot_uuid = 'test-bot-uuid'
        mock_query.launcher_id = 12345

        with patch('langbot.pkg.pipeline.pool.pipeline_query.Query') as MockQuery:
            MockQuery.return_value = mock_query

            await pool.add_query(
                bot_uuid='test-bot-uuid',
                launcher_type=Mock(),
                launcher_id=12345,
                sender_id=12345,
                message_event=Mock(),
                message_chain=Mock(),
                adapter=Mock(),
            )

            # Query is added to list and cache
            assert pool.queries[0] is mock_query
            assert pool.cached_queries[('workspace-test', mock_query.query_uuid)] is mock_query
            assert mock_query.query_id == 0

    async def test_add_query_increments_counter(self):
        """Each add_query increments the counter."""
        pool = oss_pool()

        mock_query1 = Mock()
        mock_query1.query_id = 0
        mock_query2 = Mock()
        mock_query2.query_id = 1

        with patch('langbot.pkg.pipeline.pool.pipeline_query.Query') as MockQuery:
            MockQuery.side_effect = [mock_query1, mock_query2]

            await pool.add_query(
                bot_uuid='bot1',
                launcher_type=Mock(),
                launcher_id=1,
                sender_id=1,
                message_event=Mock(),
                message_chain=Mock(),
                adapter=Mock(),
            )

            await pool.add_query(
                bot_uuid='bot2',
                launcher_type=Mock(),
                launcher_id=2,
                sender_id=2,
                message_event=Mock(),
                message_chain=Mock(),
                adapter=Mock(),
            )

            assert pool.query_id_counter == 2
            assert pool.queries[0].query_id == 0
            assert pool.queries[1].query_id == 1

    async def test_add_query_appends_to_list(self):
        """Query is appended to queries list."""
        pool = oss_pool()

        mock_query = Mock()
        mock_query.query_id = 0

        with patch('langbot.pkg.pipeline.pool.pipeline_query.Query') as MockQuery:
            MockQuery.return_value = mock_query

            await pool.add_query(
                bot_uuid='bot1',
                launcher_type=Mock(),
                launcher_id=1,
                sender_id=1,
                message_event=Mock(),
                message_chain=Mock(),
                adapter=Mock(),
            )

            assert len(pool.queries) == 1
            assert pool.queries[0] is mock_query

    async def test_add_query_caches_query(self):
        """Query is cached by query_id."""
        pool = oss_pool()

        mock_query = Mock()
        mock_query.query_id = 0

        with patch('langbot.pkg.pipeline.pool.pipeline_query.Query') as MockQuery:
            MockQuery.return_value = mock_query

            await pool.add_query(
                bot_uuid='bot1',
                launcher_type=Mock(),
                launcher_id=1,
                sender_id=1,
                message_event=Mock(),
                message_chain=Mock(),
                adapter=Mock(),
            )

            cache_key = ('workspace-test', mock_query.query_uuid)
            assert cache_key in pool.cached_queries
            assert pool.cached_queries[cache_key] is mock_query

    async def test_add_query_with_pipeline_uuid(self):
        """Query can have pipeline_uuid set."""
        pool = oss_pool()

        mock_query = Mock()
        mock_query.query_id = 0
        mock_query.pipeline_uuid = 'test-pipeline-uuid'

        with patch('langbot.pkg.pipeline.pool.pipeline_query.Query') as MockQuery:
            MockQuery.return_value = mock_query

            await pool.add_query(
                bot_uuid='bot1',
                launcher_type=Mock(),
                launcher_id=1,
                sender_id=1,
                message_event=Mock(),
                message_chain=Mock(),
                adapter=Mock(),
                pipeline_uuid='test-pipeline-uuid',
            )

            # Verify pipeline_uuid was passed to Query constructor
            call_kwargs = MockQuery.call_args[1]
            assert call_kwargs['pipeline_uuid'] == 'test-pipeline-uuid'

    async def test_add_query_sets_routed_by_rule_variable(self):
        """Query has _routed_by_rule variable."""
        pool = oss_pool()

        mock_query = Mock()
        mock_query.query_id = 0
        mock_query.variables = {'_routed_by_rule': True}

        with patch('langbot.pkg.pipeline.pool.pipeline_query.Query') as MockQuery:
            MockQuery.return_value = mock_query

            await pool.add_query(
                bot_uuid='bot1',
                launcher_type=Mock(),
                launcher_id=1,
                sender_id=1,
                message_event=Mock(),
                message_chain=Mock(),
                adapter=Mock(),
                routed_by_rule=True,
            )

            # Verify variables includes _routed_by_rule
            call_kwargs = MockQuery.call_args[1]
            assert call_kwargs['variables']['_routed_by_rule'] is True

    async def test_add_query_notifier_condition(self):
        """add_query notifies waiting consumers."""
        pool = oss_pool()

        mock_query = Mock()
        mock_query.query_id = 0

        with patch('langbot.pkg.pipeline.pool.pipeline_query.Query') as MockQuery:
            MockQuery.return_value = mock_query

            # Track if notify_all was called
            original_notify = pool.condition.notify_all
            notify_called = []

            def mock_notify():
                notify_called.append(True)
                return original_notify()

            pool.condition.notify_all = mock_notify

            await pool.add_query(
                bot_uuid='bot1',
                launcher_type=Mock(),
                launcher_id=1,
                sender_id=1,
                message_event=Mock(),
                message_chain=Mock(),
                adapter=Mock(),
            )

            assert len(notify_called) == 1


class TestQueryPoolContext:
    """Tests for async context manager."""

    async def test_aenter_acquires_lock(self):
        """__aenter__ acquires the pool lock."""
        pool = oss_pool()

        async with pool as p:
            # Lock is acquired
            assert pool.pool_lock.locked()
            assert p is pool

    async def test_aexit_releases_lock(self):
        """__aexit__ releases the pool lock."""
        pool = QueryPool()

        async with pool:
            pass

        # Lock is released after context exit
        assert not pool.pool_lock.locked()


class TestQueryPoolEdgeCases:
    """Tests for edge cases."""

    async def test_multiple_queries_cached_correctly(self):
        """Multiple queries are cached separately."""
        pool = oss_pool()

        mock_queries = []
        for i in range(5):
            q = Mock()
            q.query_id = i
            mock_queries.append(q)

        with patch('langbot.pkg.pipeline.pool.pipeline_query.Query') as MockQuery:
            MockQuery.side_effect = mock_queries

            for i in range(5):
                await pool.add_query(
                    bot_uuid=f'bot{i}',
                    launcher_type=Mock(),
                    launcher_id=i,
                    sender_id=i,
                    message_event=Mock(),
                    message_chain=Mock(),
                    adapter=Mock(),
                )

            # All cached
            assert len(pool.cached_queries) == 5

            # Each query is cached by its ID
            for i in range(5):
                query = mock_queries[i]
                assert pool.cached_queries[('workspace-test', query.query_uuid)] is query


class TestQueryPoolWorkspaceIsolation:
    """Regression coverage for trusted scope and scoped cache indexes."""

    async def test_add_query_requires_execution_context_by_default(self):
        with pytest.raises(ExecutionContextRequiredError):
            await QueryPool().add_query(
                bot_uuid='bot-a',
                launcher_type=Mock(),
                launcher_id='launcher-1',
                sender_id='sender-1',
                message_event=Mock(),
                message_chain=Mock(),
                adapter=Mock(),
            )

    async def test_serialized_scope_fields_are_not_trusted_context(self):
        forged_query = SimpleNamespace(
            instance_uuid='instance-test',
            workspace_uuid='workspace-test',
            placement_generation=1,
            bot_uuid='bot-a',
            pipeline_uuid=None,
            query_uuid='forged-query',
        )

        with pytest.raises(ExecutionContextRequiredError):
            get_query_execution_context(forged_query)

    async def test_query_lookup_is_workspace_scoped(self):
        pool = QueryPool()
        query = await add_scoped_mock_query(pool, TEST_CONTEXT)

        uuid.UUID(query.query_uuid)
        assert await pool.get_query('workspace-test', query.query_uuid) is query
        assert await pool.get_query('workspace-other', query.query_uuid) is None
        assert await pool.get_query_by_legacy_id('workspace-test', 0) is query
        assert await pool.get_query_by_legacy_id('workspace-other', 0) is None
        with pytest.raises(QueryNotFoundError):
            await pool.require_query('workspace-other', query.query_uuid)

    async def test_cache_separates_same_opaque_id_between_workspaces(self, monkeypatch):
        fixed_uuid = uuid.UUID('11111111-1111-4111-8111-111111111111')
        monkeypatch.setattr('langbot.pkg.pipeline.pool.uuid.uuid4', lambda: fixed_uuid)
        pool = QueryPool()
        context_a = TEST_CONTEXT
        context_b = ExecutionContext(
            instance_uuid='instance-test',
            workspace_uuid='workspace-other',
            placement_generation=1,
        )

        query_a = await add_scoped_mock_query(pool, context_a)
        query_b = await add_scoped_mock_query(pool, context_b)

        assert query_a.query_uuid == query_b.query_uuid
        assert await pool.get_query('workspace-test', query_a.query_uuid) is query_a
        assert await pool.get_query('workspace-other', query_b.query_uuid) is query_b

    async def test_remove_query_cleans_both_scoped_indexes(self):
        pool = QueryPool()
        query = await add_scoped_mock_query(pool, TEST_CONTEXT)

        assert await pool.remove_query(query) is True
        assert await pool.get_query('workspace-test', query.query_uuid) is None
        assert await pool.get_query_by_legacy_id('workspace-test', query.query_id) is None
        assert await pool.remove_query(query) is False

    async def test_context_cannot_substitute_bot_identity(self):
        context = ExecutionContext(
            instance_uuid='instance-test',
            workspace_uuid='workspace-test',
            placement_generation=1,
            bot_uuid='bot-b',
        )

        with pytest.raises(ExecutionContextMismatchError):
            await add_scoped_mock_query(QueryPool(), context, bot_uuid='bot-a')

    async def test_query_counter_is_scoped_by_workspace_and_generation(self):
        pool = QueryPool()
        workspace_a = TEST_CONTEXT
        workspace_b = ExecutionContext(
            instance_uuid='instance-test',
            workspace_uuid='workspace-other',
            placement_generation=1,
        )
        next_generation = ExecutionContext(
            instance_uuid='instance-test',
            workspace_uuid='workspace-test',
            placement_generation=2,
        )

        await add_scoped_mock_query(pool, workspace_a)
        await add_scoped_mock_query(pool, workspace_a)
        await add_scoped_mock_query(pool, workspace_b)

        assert pool.get_query_count(workspace_a) == 2
        assert pool.get_query_count(workspace_b) == 1
        assert pool.get_query_count(next_generation) == 0
        assert pool.query_id_counter == 3
