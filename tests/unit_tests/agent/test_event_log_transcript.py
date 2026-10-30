"""Tests for EventLog, Transcript, and history/event APIs."""

from __future__ import annotations

import datetime

import pytest

from langbot.pkg.agent.runner.host_models import (
    AgentEventEnvelope,
    AgentBinding,
    BindingScope,
    ResourcePolicy,
    StatePolicy,
    DeliveryPolicy,
)
from langbot.pkg.agent.runner.event_log_store import EventLogStore
from langbot.pkg.agent.runner.transcript_store import TranscriptStore
from langbot_plugin.api.entities.builtin.runner.event import (
    ActorContext,
)
from langbot_plugin.api.entities.builtin.runner.input import AgentInput
from langbot_plugin.api.entities.builtin.runner.delivery import DeliveryContext


def make_event_envelope(
    event_id: str = 'evt_1',
    event_type: str = 'message.received',
    conversation_id: str | None = 'conv_1',
    actor_id: str | None = 'user_1',
    input_text: str = 'Hello',
) -> AgentEventEnvelope:
    """Create a test event envelope."""
    return AgentEventEnvelope(
        event_id=event_id,
        event_type=event_type,
        event_time=1700000000,
        source='platform',
        bot_id='bot_1',
        workspace_id=None,
        conversation_id=conversation_id,
        thread_id=None,
        actor=ActorContext(
            actor_type='user',
            actor_id=actor_id,
            actor_name='Test User',
        )
        if actor_id
        else None,
        subject=None,
        input=AgentInput(text=input_text),
        delivery=DeliveryContext(surface='test'),
    )


def make_binding(runner_id: str = 'plugin:test/plugin/runner') -> AgentBinding:
    """Create a test binding."""
    return AgentBinding(
        binding_id='binding_1',
        scope=BindingScope(scope_type='agent', scope_id='pipeline_1'),
        event_types=['message.received'],
        runner_id=runner_id,
        runner_config={},
        resource_policy=ResourcePolicy(),
        state_policy=StatePolicy(),
        delivery_policy=DeliveryPolicy(),
    )


class TestEventLogStore:
    """Test EventLogStore operations."""

    @pytest.mark.asyncio
    async def test_append_event(self, mock_db_engine):
        """Test appending an event to EventLog."""
        from unittest.mock import AsyncMock, MagicMock, patch

        store = EventLogStore(mock_db_engine)

        mock_session = AsyncMock()
        mock_db_engine.dialect.name = 'sqlite'
        mock_session.execute.return_value = MagicMock(rowcount=1)
        mock_session.commit = AsyncMock()

        with patch.object(store, '_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

            event_id = await store.append_event(
                event_id='evt_1',
                event_type='message.received',
                source='platform',
                bot_id='bot_1',
                conversation_id='conv_1',
                actor_type='user',
                actor_id='user_1',
                input_summary='Hello world',
                run_id='run_1',
                runner_id='plugin:test/plugin/runner',
            )

            assert event_id == 'evt_1'
            stored_event = mock_session.execute.call_args.args[0].compile().params
            assert stored_event['metadata_json'] is None

    @pytest.mark.asyncio
    async def test_append_event_stores_metadata_json(self, mock_db_engine):
        """EventLog metadata records steering dispatch/audit facts."""
        from unittest.mock import AsyncMock, MagicMock, patch

        store = EventLogStore(mock_db_engine)

        mock_session = AsyncMock()
        mock_db_engine.dialect.name = 'sqlite'
        mock_session.execute.return_value = MagicMock(rowcount=1)
        mock_session.commit = AsyncMock()

        with patch.object(store, '_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

            event_id = await store.append_event(
                event_id='evt_steering',
                event_type='message.received',
                source='platform',
                run_id='run_1',
                runner_id='plugin:test/plugin/runner',
                metadata={
                    'steering': {
                        'status': 'queued',
                        'claimed_by_run_id': 'run_1',
                    }
                },
            )

            assert event_id == 'evt_steering'
            stored_event = mock_session.execute.call_args.args[0].compile().params
            assert '"status": "queued"' in stored_event['metadata_json']
            assert '"claimed_by_run_id": "run_1"' in stored_event['metadata_json']


class TestTranscriptStore:
    """Test TranscriptStore operations."""

    @pytest.mark.asyncio
    async def test_append_transcript(self):
        """Test appending a transcript item."""
        from sqlalchemy.ext.asyncio import create_async_engine
        from langbot.pkg.entity.persistence.base import Base
        from uuid import UUID

        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            store = TranscriptStore(engine)
            transcript_id = await store.append_transcript(
                transcript_id=None,
                event_id='evt_1',
                conversation_id='conv_1',
                role='user',
                content='Hello',
            )
            assert UUID(transcript_id).version == 4
            items, _, _, _ = await store.page_transcript('conv_1')
            assert [(item['transcript_id'], item['event_id'], item['role'], item['content']) for item in items] == [
                (transcript_id, 'evt_1', 'user', 'Hello')
            ]
        finally:
            await engine.dispose()


class TestEventLogStoreRealSQLite:
    """Test EventLogStore with real SQLite database."""

    @pytest.fixture
    async def db_engine(self):
        """Create an in-memory SQLite database for testing."""
        from sqlalchemy.ext.asyncio import create_async_engine
        from langbot.pkg.entity.persistence.base import Base

        engine = create_async_engine('sqlite+aiosqlite:///:memory:')

        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield engine

        await engine.dispose()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(('summary', 'stored_summary'), [('x' * 1000, 'x' * 1000), ('x' * 1001, 'x' * 997 + '...')])
    async def test_append_get_event_round_trip(self, db_engine, summary, stored_summary):
        """Event fields and the summary length boundary survive a real DB round trip."""
        store = EventLogStore(db_engine)

        # Append event
        event_id = await store.append_event(
            event_id='evt_real_001',
            event_type='message.received',
            source='platform',
            bot_id='bot_001',
            conversation_id='conv_001',
            actor_type='user',
            actor_id='user_001',
            actor_name='Test User',
            input_summary=summary,
            run_id='run_001',
            runner_id='plugin:test/plugin/runner',
        )

        assert event_id == 'evt_real_001'

        # Get event
        event = await store.get_event(event_id)
        assert event is not None
        assert event['event_id'] == 'evt_real_001'
        assert event['event_type'] == 'message.received'
        assert event['source'] == 'platform'
        assert event['conversation_id'] == 'conv_001'
        assert event['actor_type'] == 'user'
        assert event['actor_id'] == 'user_001'
        assert event['input_summary'] == stored_summary

    @pytest.mark.asyncio
    async def test_page_events(self, db_engine):
        """Test page_events with real DB."""
        store = EventLogStore(db_engine)

        # Append multiple events
        for i in range(5):
            await store.append_event(
                event_id=f'evt_real_{i:03d}',
                event_type='message.received',
                source='platform',
                conversation_id='conv_001',
                input_summary=f'Message {i}',
            )
        await store.append_event(
            event_id='evt_other_conversation',
            event_type='message.received',
            source='platform',
            conversation_id='conv_other',
        )

        # Page events
        items, next_seq, has_more = await store.page_events(
            conversation_id='conv_001',
            limit=3,
        )

        assert [item['event_id'] for item in items] == ['evt_real_004', 'evt_real_003', 'evt_real_002']
        assert has_more is True
        assert next_seq == items[-1]['id']

        older, next_seq, has_more = await store.page_events(conversation_id='conv_001', before_seq=next_seq, limit=3)
        assert [item['event_id'] for item in older] == ['evt_real_001', 'evt_real_000']
        assert next_seq is None
        assert has_more is False

    @pytest.mark.asyncio
    async def test_get_latest_cursor(self, db_engine):
        """Test get_latest_cursor with real DB."""
        store = EventLogStore(db_engine)
        assert await store.get_latest_cursor('conv_cursor') is None

        # Append events
        for i in range(3):
            await store.append_event(
                event_id=f'evt_cursor_{i:03d}',
                event_type='message.received',
                source='platform',
                conversation_id='conv_cursor',
            )

        # Get latest cursor
        cursor = await store.get_latest_cursor('conv_cursor')
        assert cursor == '3'
        await store.append_event(
            event_id='other', event_type='message.received', source='platform', conversation_id='other'
        )
        assert await store.get_latest_cursor('conv_cursor') == '3'
        assert await store.get_latest_cursor('other') == '4'

    @pytest.mark.asyncio
    async def test_cleanup_events_older_than(self, db_engine):
        """EventLog cleanup removes only rows older than the cutoff."""
        import sqlalchemy
        from langbot.pkg.entity.persistence.event_log import EventLog

        store = EventLogStore(db_engine)
        cutoff = datetime.datetime.utcnow()
        await store.append_event(
            event_id='evt_cleanup_old',
            event_type='message.received',
            source='platform',
            conversation_id='conv_cleanup',
        )
        await store.append_event(
            event_id='evt_cleanup_new',
            event_type='message.received',
            source='platform',
            conversation_id='conv_cleanup',
        )
        async with store._session_factory() as session:
            await session.execute(
                sqlalchemy.update(EventLog)
                .where(EventLog.event_id == 'evt_cleanup_old')
                .values(created_at=cutoff - datetime.timedelta(days=2))
            )
            await session.execute(
                sqlalchemy.update(EventLog)
                .where(EventLog.event_id == 'evt_cleanup_new')
                .values(created_at=cutoff + datetime.timedelta(days=2))
            )
            await session.commit()

        removed = await store.cleanup_events_older_than(cutoff)

        assert removed == 1
        assert await store.get_event('evt_cleanup_old') is None
        assert await store.get_event('evt_cleanup_new') is not None


class TestTranscriptStoreRealSQLite:
    """Test TranscriptStore with real SQLite database."""

    @pytest.fixture
    async def db_engine(self):
        """Create an in-memory SQLite database for testing."""
        from sqlalchemy.ext.asyncio import create_async_engine
        from langbot.pkg.entity.persistence.base import Base

        engine = create_async_engine('sqlite+aiosqlite:///:memory:')

        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield engine

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_append_page_transcript_round_trip(self, db_engine):
        """Persist attachments and page backward without crossing conversations."""
        store = TranscriptStore(db_engine)
        attachments = [{'id': 'att_1', 'type': 'image', 'url': 'https://example.test/image.png'}]

        # Append transcript items
        for i in range(3):
            await store.append_transcript(
                transcript_id=f'trans_real_{i:03d}',
                event_id=f'evt_{i:03d}',
                conversation_id='conv_001',
                role='user' if i % 2 == 0 else 'assistant',
                content=f'Message {i}',
                attachment_refs=attachments if i == 2 else None,
            )
        await store.append_transcript(
            transcript_id='trans_other',
            event_id='evt_other',
            conversation_id='conv_other',
            role='user',
            content='Other conversation',
        )

        # Page transcript
        items, next_seq, prev_seq, has_more = await store.page_transcript(
            conversation_id='conv_001',
            limit=2,
            include_attachments=True,
        )

        assert [item['transcript_id'] for item in items] == ['trans_real_002', 'trans_real_001']
        assert items[0]['attachment_refs'] == attachments
        assert has_more is True
        assert next_seq == items[-1]['seq']
        assert prev_seq == items[0]['seq']

        older, next_seq, prev_seq, has_more = await store.page_transcript(
            'conv_001', before_seq=next_seq, limit=2, direction='backward'
        )
        assert [item['transcript_id'] for item in older] == ['trans_real_000']
        assert next_seq is None
        assert prev_seq == older[0]['seq']
        assert has_more is False

    @pytest.mark.asyncio
    async def test_page_transcript_caps_results_at_100(self, db_engine):
        store = TranscriptStore(db_engine)
        for i in range(101):
            await store.append_transcript(
                transcript_id=f'cap_{i}', event_id=f'evt_{i}', conversation_id='conv_cap', role='user', content=str(i)
            )

        items, next_seq, prev_seq, has_more = await store.page_transcript('conv_cap', limit=200)

        assert [item['transcript_id'] for item in items] == [f'cap_{i}' for i in range(100, 0, -1)]
        assert has_more is True
        assert next_seq == items[-1]['seq']
        assert prev_seq == items[0]['seq']

    @pytest.mark.asyncio
    async def test_get_legacy_provider_messages_projects_transcript_history(self, db_engine):
        """Transcript is the canonical source; legacy Pipeline readers get a Message view."""
        store = TranscriptStore(db_engine)

        await store.append_transcript(
            transcript_id='trans_view_001',
            event_id='evt_view_001',
            conversation_id='conv_view',
            role='user',
            content='User text',
            content_json={
                'role': 'user',
                'content': [{'type': 'text', 'text': 'User structured text'}],
            },
        )
        await store.append_transcript(
            transcript_id='trans_view_002',
            event_id='evt_view_002',
            conversation_id='conv_view',
            role='tool',
            item_type='tool_result',
            content='ignored tool result',
        )
        await store.append_transcript(
            transcript_id='trans_view_003',
            event_id='evt_view_003',
            conversation_id='conv_view',
            role='assistant',
            content='Assistant text',
        )

        messages = await store.get_legacy_provider_messages('conv_view')

        assert [message.role for message in messages] == ['user', 'assistant']
        assert messages[0].content[0].text == 'User structured text'
        assert messages[1].content == 'Assistant text'

    @pytest.mark.asyncio
    async def test_get_legacy_provider_messages_filters_scope(self, db_engine):
        """Legacy Pipeline history projection must stay inside the current run scope."""
        store = TranscriptStore(db_engine)

        await store.append_transcript(
            transcript_id='trans_scope_001',
            event_id='evt_scope_001',
            conversation_id='conv_scope',
            bot_id='bot_001',
            workspace_id='workspace_001',
            thread_id='thread_001',
            role='user',
            content='Current scope text',
        )
        await store.append_transcript(
            transcript_id='trans_scope_002',
            event_id='evt_scope_002',
            conversation_id='conv_scope',
            bot_id='bot_002',
            workspace_id='workspace_001',
            thread_id='thread_001',
            role='assistant',
            content='Other bot text',
        )
        await store.append_transcript(
            transcript_id='trans_scope_003',
            event_id='evt_scope_003',
            conversation_id='conv_scope',
            bot_id='bot_001',
            workspace_id='workspace_001',
            thread_id='thread_002',
            role='assistant',
            content='Other thread text',
        )

        messages = await store.get_legacy_provider_messages(
            'conv_scope',
            bot_id='bot_001',
            workspace_id='workspace_001',
            thread_id='thread_001',
            strict_thread=True,
        )

        assert [message.content for message in messages] == ['Current scope text']

    @pytest.mark.asyncio
    async def test_search_transcript_real_db(self, db_engine):
        """Test search_transcript with real DB."""
        store = TranscriptStore(db_engine)

        # Append transcript items
        await store.append_transcript(
            transcript_id='trans_search_001',
            event_id='evt_search_001',
            conversation_id='conv_search',
            role='user',
            content='I want to learn about databases',
        )
        await store.append_transcript(
            transcript_id='trans_search_002',
            event_id='evt_search_002',
            conversation_id='conv_search',
            role='assistant',
            content='Here is information about databases',
        )
        await store.append_transcript(
            transcript_id='nonmatch',
            event_id='evt_nonmatch',
            conversation_id='conv_search',
            role='user',
            content='hello',
        )
        await store.append_transcript(
            transcript_id='foreign_match',
            event_id='evt_foreign',
            conversation_id='conv_other',
            role='user',
            content='foreign database',
        )

        # Search for "database"
        items = await store.search_transcript(
            conversation_id='conv_search',
            query_text='database',
        )

        assert [item['transcript_id'] for item in items] == ['trans_search_002', 'trans_search_001']
        limited = await store.search_transcript('conv_search', query_text='database', top_k=1)
        assert [item['transcript_id'] for item in limited] == ['trans_search_002']
        assert await store.search_transcript('conv_search', query_text='missing') == []

    @pytest.mark.asyncio
    async def test_get_latest_cursor_real_db(self, db_engine):
        """Cursors and history-before checks reflect persisted conversation rows."""
        store = TranscriptStore(db_engine)
        assert await store.get_latest_cursor('conv_cursor') is None
        assert await store.has_history_before('conv_cursor', 1) is False

        # Append transcript items
        for i in range(3):
            await store.append_transcript(
                transcript_id=f'trans_cursor_{i:03d}',
                event_id=f'evt_cursor_{i:03d}',
                conversation_id='conv_cursor',
                role='user',
                content=f'Message {i}',
            )

        # Get latest cursor
        cursor = await store.get_latest_cursor('conv_cursor')
        assert cursor == '3'
        assert await store.has_history_before('conv_cursor', 1) is False
        assert await store.has_history_before('conv_cursor', 2) is True
        assert await store.has_history_before('conv_other', 4) is False

    @pytest.mark.asyncio
    async def test_cleanup_transcripts_older_than(self, db_engine):
        """Transcript cleanup removes only rows older than the cutoff."""
        import sqlalchemy
        from langbot.pkg.entity.persistence.transcript import Transcript

        store = TranscriptStore(db_engine)
        cutoff = datetime.datetime.utcnow()
        await store.append_transcript(
            transcript_id='trans_cleanup_old',
            event_id='evt_cleanup_old',
            conversation_id='conv_cleanup',
            role='user',
            content='old',
        )
        await store.append_transcript(
            transcript_id='trans_cleanup_new',
            event_id='evt_cleanup_new',
            conversation_id='conv_cleanup',
            role='assistant',
            content='new',
        )
        async with store._session_factory() as session:
            await session.execute(
                sqlalchemy.update(Transcript)
                .where(Transcript.transcript_id == 'trans_cleanup_old')
                .values(created_at=cutoff - datetime.timedelta(days=2))
            )
            await session.execute(
                sqlalchemy.update(Transcript)
                .where(Transcript.transcript_id == 'trans_cleanup_new')
                .values(created_at=cutoff + datetime.timedelta(days=2))
            )
            await session.commit()

        removed = await store.cleanup_transcripts_older_than(cutoff)
        items, _, _, _ = await store.page_transcript('conv_cleanup', limit=10)

        assert removed == 1
        assert [item['content'] for item in items] == ['new']


# Fixtures
@pytest.fixture
def mock_db_engine():
    """Create a mock database engine for AsyncSession-based stores."""
    from unittest.mock import MagicMock
    from sqlalchemy.ext.asyncio import AsyncEngine

    engine = MagicMock(spec=AsyncEngine)
    return engine
