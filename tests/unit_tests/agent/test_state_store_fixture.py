"""Regression guard against unrelated schema setup in state-store tests."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from unit_tests.agent import test_state_store as state_tests
from langbot.pkg.entity.persistence.runner_state import RunnerState


@pytest.mark.asyncio
async def test_state_store_fixture_creates_only_its_owned_table(monkeypatch):
    created_tables = []

    async def run_sync(create_all, **kwargs):
        created_tables.extend(kwargs.get('tables', create_all.__self__.sorted_tables))

    @asynccontextmanager
    async def begin():
        yield SimpleNamespace(run_sync=run_sync)

    engine = SimpleNamespace(begin=begin, dispose=AsyncMock())
    monkeypatch.setattr(state_tests, 'create_async_engine', lambda *args, **kwargs: engine)
    fixture = state_tests.TestPersistentStateStore.db_engine.__wrapped__(state_tests.TestPersistentStateStore())
    try:
        assert await anext(fixture) is engine
        assert created_tables == [RunnerState.__table__]
    finally:
        await fixture.aclose()
