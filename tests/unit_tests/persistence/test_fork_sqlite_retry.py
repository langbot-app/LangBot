from importlib import import_module
from unittest.mock import AsyncMock, Mock, patch

import pytest
import sqlalchemy


@pytest.mark.asyncio
async def test_unscoped_sqlite_locked_write_retries_without_committing_failure():
    manager = import_module('langbot.pkg.persistence.mgr').PersistenceManager(Mock())
    connection = AsyncMock()
    result = Mock()
    locked = sqlalchemy.exc.OperationalError('INSERT', {}, Exception('database is locked'))
    connection.execute.side_effect = [locked, result]
    context = AsyncMock()
    context.__aenter__.return_value = connection
    manager.db = Mock()
    manager.db.get_engine.return_value.connect.return_value = context
    with patch('langbot.pkg.persistence.mgr.asyncio.sleep', new_callable=AsyncMock) as sleep:
        assert await manager.execute_async(sqlalchemy.text('SELECT 1')) is result
    assert connection.execute.await_count == 2
    connection.commit.assert_awaited_once()
    sleep.assert_awaited_once_with(0.1)


@pytest.mark.asyncio
async def test_sqlite_retry_stops_at_limit_and_other_database_errors_propagate():
    manager = import_module('langbot.pkg.persistence.mgr').PersistenceManager(Mock())
    connection = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = connection
    manager.db = Mock()
    manager.db.get_engine.return_value.connect.return_value = context
    for message, attempts in [('database is locked', 5), ('syntax error', 1)]:
        connection.execute.reset_mock()
        connection.execute.side_effect = sqlalchemy.exc.OperationalError('INSERT', {}, Exception(message))
        with patch('langbot.pkg.persistence.mgr.asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(sqlalchemy.exc.OperationalError):
                await manager.execute_async(sqlalchemy.text('SELECT 1'))
        assert connection.execute.await_count == attempts
    connection.commit.assert_not_awaited()
