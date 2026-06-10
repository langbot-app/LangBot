"""Tests for AgentRunner history/event pull API authorization."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.agent.runner.event_log_store import EventLogStore
from langbot.pkg.agent.runner.session_registry import AgentRunSessionRegistry
from langbot.pkg.entity.persistence import event_log as event_log_model
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.plugin.handler import RuntimeConnectionHandler
from langbot_plugin.api.entities.builtin.agent_runner.page_results import (
    AgentEventRecord,
    EventPage,
)
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
    assert event_log_model.EventLog.__tablename__ == 'event_log'
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
    available_apis=None,
):
    await session_registry.register(
        run_id=run_id,
        runner_id='plugin:test/runner/default',
        query_id=None,
        plugin_identity='test/runner',
        resources=make_resources(),
        conversation_id=conversation_id,
        available_apis=available_apis or {},
    )


@pytest.mark.asyncio
async def test_history_page_requires_runtime_capability(session_registry, db_engine):
    await _register_session(session_registry, available_apis={'history_page': False})
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
    await _register_session(session_registry, available_apis={'history_page': True})
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
    await _register_session(session_registry, available_apis={'history_search': True})
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
async def test_event_page_requires_runtime_capability(session_registry, db_engine):
    await _register_session(session_registry, available_apis={'event_page': False})
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
    await _register_session(session_registry, available_apis={'event_page': True})
    handler = _handler(db_engine, session_registry)
    event_page = handler.actions[PluginToRuntimeAction.EVENT_PAGE.value]

    result = await event_page({
        'run_id': 'run_1',
        'conversation_id': 'conv_other',
        'caller_plugin_identity': 'test/runner',
    })

    assert result.code != 0
    assert 'not accessible' in result.message.lower()


@pytest.mark.asyncio
async def test_event_get_returns_sdk_record_projection(session_registry, db_engine):
    await _register_session(session_registry, available_apis={'event_get': True})
    store = EventLogStore(db_engine)
    event_id = await store.append_event(
        event_id='evt_projection_1',
        event_type='message.received',
        source='platform',
        conversation_id='conv_1',
        actor_type='user',
        actor_id='user_1',
        input_summary='hello',
        input_json={'internal': 'not part of AgentEventRecord'},
        run_id='run_1',
        runner_id='plugin:test/runner/default',
    )
    handler = _handler(db_engine, session_registry)
    event_get = handler.actions[PluginToRuntimeAction.EVENT_GET.value]

    result = await event_get({
        'run_id': 'run_1',
        'event_id': event_id,
        'caller_plugin_identity': 'test/runner',
    })

    assert result.code == 0
    AgentEventRecord.model_validate(result.data)
    assert 'id' not in result.data
    assert 'input_json' not in result.data
    assert 'run_id' not in result.data
    assert 'runner_id' not in result.data
    assert result.data['seq'] is not None
    assert result.data['cursor'] == str(result.data['seq'])


@pytest.mark.asyncio
async def test_event_page_returns_sdk_page_projection(session_registry, db_engine):
    await _register_session(session_registry, available_apis={'event_page': True})
    store = EventLogStore(db_engine)
    await store.append_event(
        event_id='evt_projection_page_1',
        event_type='message.received',
        source='platform',
        conversation_id='conv_1',
        input_json={'internal': 'not part of AgentEventRecord'},
        run_id='run_other',
        runner_id='plugin:test/runner/default',
    )
    handler = _handler(db_engine, session_registry)
    event_page = handler.actions[PluginToRuntimeAction.EVENT_PAGE.value]

    result = await event_page({
        'run_id': 'run_1',
        'caller_plugin_identity': 'test/runner',
    })

    assert result.code == 0
    page = EventPage.model_validate(result.data)
    assert len(page.items) == 1
    item = result.data['items'][0]
    assert 'id' not in item
    assert 'input_json' not in item
    assert 'run_id' not in item
    assert 'runner_id' not in item
