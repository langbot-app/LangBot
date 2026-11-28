from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.entity.persistence.monitoring import MonitoringMessage
from langbot.pkg.workflow.operations import history, knowledge


async def test_history_is_scoped_before_limiting():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    context = SimpleNamespace(workspace_uuid='w', bot_uuid='bot')
    runtime = SimpleNamespace(execution_context=context, session_id='group_42')
    try:
        async with engine.begin() as conn:
            await conn.run_sync(MonitoringMessage.__table__.create)
            for index, (workspace, bot, session) in enumerate(
                [
                    ('w', 'bot', 'group_42'),
                    ('w', 'bot', 'group_42'),
                    ('other', 'bot', 'group_42'),
                    ('w', 'bot', 'person_42'),
                    ('w', 'other', 'group_42'),
                ]
            ):
                await conn.execute(
                    sa.insert(MonitoringMessage).values(
                        id=str(index),
                        workspace_uuid=workspace,
                        bot_id=bot,
                        bot_name='Bot',
                        pipeline_id='',
                        pipeline_name='',
                        session_id=session,
                        timestamp=datetime(2026, 1, 1) + timedelta(seconds=index),
                        message_content=str(index),
                        status='success',
                        level='info',
                        user_name='Ada',
                    )
                )
            app = SimpleNamespace(persistence_mgr=SimpleNamespace(execute_async=conn.execute))
            result = await history({'scope': 'group', 'limit': 2}, app, runtime)
            assert result['text'] == 'Ada: 0\nAda: 1'
    finally:
        await engine.dispose()


async def test_knowledge_uses_workspace_context_and_retrieval_limit():
    context = object()
    entry = SimpleNamespace(id='first', content=[SimpleNamespace(type='text', text='answer')])
    kb = SimpleNamespace(retrieve=AsyncMock(return_value=[entry, entry]))
    manager = SimpleNamespace(get_knowledge_base_by_uuid=AsyncMock(return_value=kb))
    result = await knowledge(
        {'kb_uuid': 'kb', 'query': 'question', 'top_k': 1},
        SimpleNamespace(rag_mgr=manager),
        SimpleNamespace(execution_context=context),
    )
    manager.get_knowledge_base_by_uuid.assert_awaited_once_with(context, 'kb')
    kb.retrieve.assert_awaited_once_with(context, 'question', {'top_k': 1})
    assert result == {'chunks': [{'id': 'first', 'text': 'answer'}], 'text': 'answer'}
