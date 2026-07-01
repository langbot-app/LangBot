"""
Unit tests for QueryPool.

Tests query management, ID generation, and async context handling.
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch

from langbot.pkg.pipeline.pool import QueryPool


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
        pool = QueryPool()

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
            assert pool.cached_queries[0] is mock_query
            assert mock_query.query_id == 0

    async def test_add_query_increments_counter(self):
        """Each add_query increments the counter."""
        pool = QueryPool()

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
        pool = QueryPool()

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
        pool = QueryPool()

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

            assert 0 in pool.cached_queries
            assert pool.cached_queries[0] is mock_query

    async def test_add_query_with_pipeline_uuid(self):
        """Query can have pipeline_uuid set."""
        pool = QueryPool()

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
        pool = QueryPool()

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
        pool = QueryPool()

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
        pool = QueryPool()

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
        pool = QueryPool()

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
                assert pool.cached_queries[i] is mock_queries[i]
