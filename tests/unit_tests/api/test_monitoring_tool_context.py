"""Unit tests for MonitoringService._get_message_for_tool_context.

Tests cover:
- Fetching a MonitoringMessage by message_id (first query path)
- Falling back to session_id + role='user' query (second path)
- Falling back to session_id + any role query (third path)
- Returning None when no message is found (safe degradation)
- Returning None when neither message_id nor session_id is provided

The fix replaces the old ``result.first()`` + ``row[0]`` pattern with
``result.scalars().first()`` (SQLAlchemy 2.0 convention) so the ORM entity
is correctly retrieved on PostgreSQL/asyncpg.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from langbot.pkg.api.http.service.monitoring import MonitoringService
from langbot.pkg.entity.persistence.monitoring import MonitoringMessage

pytestmark = pytest.mark.asyncio


def _make_mock_message(
    msg_id: str = 'msg-1',
    bot_id: str = 'bot-1',
    bot_name: str = 'TestBot',
    pipeline_id: str = 'pipe-1',
    pipeline_name: str = 'TestPipeline',
    session_id: str = 'sess-1',
    role: str = 'user',
) -> MonitoringMessage:
    """Create a MonitoringMessage instance for testing."""
    return MonitoringMessage(
        id=msg_id,
        bot_id=bot_id,
        bot_name=bot_name,
        pipeline_id=pipeline_id,
        pipeline_name=pipeline_name,
        message_content='hello',
        session_id=session_id,
        status='success',
        level='info',
        role=role,
    )


def _make_scalars_result(obj=None):
    """Create a mock query result whose scalars().first() returns *obj*."""
    result = MagicMock()
    result.scalars.return_value.first.return_value = obj
    return result


def _make_ap(side_effect=None):
    """Create a mock Application with persistence_mgr.execute_async."""
    ap = SimpleNamespace()
    ap.persistence_mgr = SimpleNamespace()
    if side_effect is not None:
        ap.persistence_mgr.execute_async = AsyncMock(side_effect=side_effect)
    else:
        ap.persistence_mgr.execute_async = AsyncMock()
    return ap


class TestGetMessageForToolContextByMessageId:
    """Tests for the message_id lookup path."""

    async def test_returns_message_when_found_by_message_id(self):
        """Returns the MonitoringMessage when found by message_id."""
        msg = _make_mock_message(msg_id='msg-123')
        result = _make_scalars_result(msg)
        ap = _make_ap(side_effect=[result])

        service = MonitoringService(ap)
        found = await service._get_message_for_tool_context(message_id='msg-123')

        assert found is msg
        assert found.id == 'msg-123'
        ap.persistence_mgr.execute_async.assert_awaited_once()

    async def test_falls_through_when_message_id_not_found(self):
        """Falls through to session_id lookup when message_id yields nothing."""
        empty_result = _make_scalars_result(None)
        msg = _make_mock_message(session_id='sess-1', role='user')
        user_result = _make_scalars_result(msg)
        ap = _make_ap(side_effect=[empty_result, user_result])

        service = MonitoringService(ap)
        found = await service._get_message_for_tool_context(message_id='missing', session_id='sess-1')

        assert found is msg
        assert ap.persistence_mgr.execute_async.await_count == 2


class TestGetMessageForToolContextBySessionId:
    """Tests for the session_id lookup paths."""

    async def test_returns_user_message_when_found(self):
        """Returns the most recent user message for the session."""
        msg = _make_mock_message(session_id='sess-1', role='user')
        user_result = _make_scalars_result(msg)
        ap = _make_ap(side_effect=[user_result])

        service = MonitoringService(ap)
        found = await service._get_message_for_tool_context(session_id='sess-1')

        assert found is msg
        assert found.role == 'user'
        ap.persistence_mgr.execute_async.assert_awaited_once()

    async def test_falls_back_to_any_role_when_no_user_message(self):
        """Falls back to any-role query when no user message exists."""
        empty_user_result = _make_scalars_result(None)
        any_msg = _make_mock_message(session_id='sess-1', role='assistant')
        any_result = _make_scalars_result(any_msg)
        ap = _make_ap(side_effect=[empty_user_result, any_result])

        service = MonitoringService(ap)
        found = await service._get_message_for_tool_context(session_id='sess-1')

        assert found is any_msg
        assert found.role == 'assistant'
        assert ap.persistence_mgr.execute_async.await_count == 2


class TestGetMessageForToolContextNone:
    """Tests for None / degradation paths."""

    async def test_returns_none_when_no_message_id_and_no_session_id(self):
        """Returns None when neither message_id nor session_id is given."""
        ap = _make_ap()
        service = MonitoringService(ap)

        found = await service._get_message_for_tool_context()

        assert found is None
        ap.persistence_mgr.execute_async.assert_not_awaited()

    async def test_returns_none_when_message_id_missing_and_no_session_id(self):
        """Returns None when message_id yields nothing and session_id is absent."""
        empty_result = _make_scalars_result(None)
        ap = _make_ap(side_effect=[empty_result])

        service = MonitoringService(ap)
        found = await service._get_message_for_tool_context(message_id='missing')

        assert found is None

    async def test_returns_none_when_all_queries_empty(self):
        """Returns None when all three query paths return nothing."""
        empty1 = _make_scalars_result(None)
        empty2 = _make_scalars_result(None)
        empty3 = _make_scalars_result(None)
        ap = _make_ap(side_effect=[empty1, empty2, empty3])

        service = MonitoringService(ap)
        found = await service._get_message_for_tool_context(message_id='x', session_id='sess-1')

        assert found is None
        assert ap.persistence_mgr.execute_async.await_count == 3

    async def test_returns_none_when_session_only_and_all_empty(self):
        """Returns None when session_id queries all return nothing."""
        empty_user = _make_scalars_result(None)
        empty_any = _make_scalars_result(None)
        ap = _make_ap(side_effect=[empty_user, empty_any])

        service = MonitoringService(ap)
        found = await service._get_message_for_tool_context(session_id='empty-session')

        assert found is None
        assert ap.persistence_mgr.execute_async.await_count == 2


class TestGetMessageForToolContextUsesScalars:
    """Verify the method calls scalars().first(), not first() + row[0]."""

    async def test_uses_scalars_first_not_first(self):
        """Ensure result.scalars().first() is used, not result.first().

        This is the core regression test: the old code used result.first()
        and then row[0], which returned a raw string on PostgreSQL/asyncpg.
        The fix uses result.scalars().first() per SQLAlchemy 2.0 convention.
        """
        msg = _make_mock_message()
        result = _make_scalars_result(msg)
        ap = _make_ap(side_effect=[result])

        service = MonitoringService(ap)
        await service._get_message_for_tool_context(message_id='msg-1')

        # scalars() must have been called
        result.scalars.assert_called_once()
        # scalars().first() must have been called
        result.scalars.return_value.first.assert_called_once()
        # first() on the result directly should NOT have been called
        result.first.assert_not_called()
