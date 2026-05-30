"""Tests for AgentRunner history/event pull API authorization."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.agent.runner.session_registry import AgentRunSessionRegistry
from langbot.pkg.plugin.handler import RuntimeConnectionHandler
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction

from .conftest import make_resources


class FakeConnection:
    pass


class FakeApplication:
    def __init__(self, db_engine):
        self.logger = MagicMock()
        self.persistence_mgr = MagicMock()
        self.persistence_mgr.get_db_engine = MagicMock(return_value=db_engine)


@pytest.fixture
def session_registry(monkeypatch):
    registry = AgentRunSessionRegistry()
    monkeypatch.setattr(
        'langbot.pkg.agent.runner.session_registry._global_registry',
        registry,
    )
    return registry


@pytest.fixture
async def db_engine():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    yield engine
    await engine.dispose()


def _handler(db_engine, session_registry):
    async def fake_disconnect():
        return True

    fake_app = FakeApplication(db_engine)
    return RuntimeConnectionHandler(FakeConnection(), fake_disconnect, fake_app)


async def _register_session(
    session_registry,
    *,
    run_id='run_1',
    conversation_id='conv_1',
    permissions=None,
):
    await session_registry.register(
        run_id=run_id,
        runner_id='plugin:test/runner/default',
        query_id=None,
        plugin_identity='test/runner',
        resources=make_resources(),
        conversation_id=conversation_id,
        permissions=permissions or {},
    )


@pytest.mark.asyncio
async def test_history_page_requires_manifest_permission(session_registry, db_engine):
    await _register_session(session_registry, permissions={'history': []})
    handler = _handler(db_engine, session_registry)
    history_page = handler.actions[PluginToRuntimeAction.HISTORY_PAGE.value]

    result = await history_page({
        'run_id': 'run_1',
        'caller_plugin_identity': 'test/runner',
    })

    assert result.code != 0
    assert 'not authorized' in result.message.lower()


@pytest.mark.asyncio
async def test_history_page_rejects_cross_conversation(session_registry, db_engine):
    await _register_session(session_registry, permissions={'history': ['page']})
    handler = _handler(db_engine, session_registry)
    history_page = handler.actions[PluginToRuntimeAction.HISTORY_PAGE.value]

    result = await history_page({
        'run_id': 'run_1',
        'conversation_id': 'conv_other',
        'caller_plugin_identity': 'test/runner',
    })

    assert result.code != 0
    assert 'not accessible' in result.message.lower()


@pytest.mark.asyncio
async def test_history_search_rejects_filter_conversation_override(session_registry, db_engine):
    await _register_session(session_registry, permissions={'history': ['search']})
    handler = _handler(db_engine, session_registry)
    history_search = handler.actions[PluginToRuntimeAction.HISTORY_SEARCH.value]

    result = await history_search({
        'run_id': 'run_1',
        'query': 'hello',
        'filters': {'conversation_id': 'conv_other'},
        'caller_plugin_identity': 'test/runner',
    })

    assert result.code != 0
    assert 'not accessible' in result.message.lower()


@pytest.mark.asyncio
async def test_event_page_requires_manifest_permission(session_registry, db_engine):
    await _register_session(session_registry, permissions={'events': []})
    handler = _handler(db_engine, session_registry)
    event_page = handler.actions[PluginToRuntimeAction.EVENT_PAGE.value]

    result = await event_page({
        'run_id': 'run_1',
        'caller_plugin_identity': 'test/runner',
    })

    assert result.code != 0
    assert 'not authorized' in result.message.lower()


@pytest.mark.asyncio
async def test_event_page_rejects_cross_conversation(session_registry, db_engine):
    await _register_session(session_registry, permissions={'events': ['page']})
    handler = _handler(db_engine, session_registry)
    event_page = handler.actions[PluginToRuntimeAction.EVENT_PAGE.value]

    result = await event_page({
        'run_id': 'run_1',
        'conversation_id': 'conv_other',
        'caller_plugin_identity': 'test/runner',
    })

    assert result.code != 0
    assert 'not accessible' in result.message.lower()
