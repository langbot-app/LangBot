"""Resumable, bounded historical repair, never called by interactive reads."""

import asyncio
import argparse
import datetime
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite

from ..entity.persistence.agent_run import AgentRun
from ..entity.persistence.event_log import EventLog
from ..entity.persistence.metadata import WorkspaceMetadata
from ..entity.persistence.monitoring import MonitoringMessage
from .session_summary_reader import SessionScope
from .session_summary_writer import SessionSummaryWriter, ingress_summary_change, message_summary_change


CURSOR_KEY = 'session_summary_backfill_v1'
BATCH_SIZE = 100
JSON_LIMIT = 65536


async def _initialization_pending(session, workspace: str) -> bool:
    value = (
        await session.execute(
            sa.select(WorkspaceMetadata.value).where(
                WorkspaceMetadata.workspace_uuid == workspace,
                WorkspaceMetadata.key == CURSOR_KEY,
            )
        )
    ).scalar_one_or_none()
    return value is not None and json.loads(value)['source'] != 'done'


async def require_initialized(session, workspace: str):
    if await _initialization_pending(session, workspace):
        raise RuntimeError(
            f'Session summaries for Workspace {workspace} require offline initialization. '
            'Stop writers and run: uv run python -m langbot.pkg.persistence.session_summary_backfill '
            f'--workspace {workspace} --writers-stopped --database-url-env LANGBOT_SUMMARY_DATABASE_URL'
        )


async def require_application_initialized(ap):
    """Reject startup before producers can replay uninitialized history."""
    for binding in await ap.workspace_service.list_active_execution_bindings():
        async with ap.monitoring_service._summary_session(binding.workspace_uuid) as session:
            await require_initialized(session, binding.workspace_uuid)


async def initialize_application_summaries(ap):
    """Complete OSS initialization before starting HTTP or message producers."""
    from .mgr import PersistenceMode

    if ap.persistence_mgr.mode != PersistenceMode.OSS_COMPAT:
        await require_application_initialized(ap)
        return

    backfill = SessionSummaryBackfill(
        ap.monitoring_service._summary_session, ap.persistence_mgr.get_db_engine().dialect.name
    )
    for binding in await ap.workspace_service.list_active_execution_bindings():
        workspace = binding.workspace_uuid
        async with ap.monitoring_service._summary_session(workspace) as session:
            pending = await _initialization_pending(session, workspace)
        if not pending:
            continue
        ap.logger.info(f'Initializing session summaries for Workspace {workspace} before starting services.')
        while not await backfill.run_batch(workspace):
            await asyncio.sleep(0)
        ap.logger.info(f'Session summaries for Workspace {workspace} initialized; continuing startup.')


class SessionSummaryBackfill:
    def __init__(self, session_scope: SessionScope, dialect: str):
        self._session_scope = session_scope
        self._dialect = dialect
        self._insert = {'postgresql': postgresql.insert, 'sqlite': sqlite.insert}[dialect]
        self._writer = SessionSummaryWriter(dialect)

    def _json_text(self, column, key):
        expression = sa.type_coerce(column, sa.JSON) if self._dialect == 'sqlite' else sa.cast(column, sa.JSON)
        relevant = sa.and_(
            EventLog.source == 'platform',
            EventLog.event_type == 'message.received',
            sa.func.length(column) <= JSON_LIMIT,
        )
        return sa.case((relevant, expression[key].as_string()), else_=None)

    async def run_batch(self, workspace: str, batch_size: int = BATCH_SIZE) -> bool:
        """Commit at most one page and its cursor atomically; return completion."""
        if not 1 <= batch_size <= BATCH_SIZE:
            raise ValueError(f'batch_size must be between 1 and {BATCH_SIZE}')
        async with self._session_scope(workspace) as session:
            await session.execute(
                self._insert(WorkspaceMetadata)
                .values(
                    workspace_uuid=workspace,
                    key=CURSOR_KEY,
                    value=json.dumps({'source': 'messages'}),
                )
                .on_conflict_do_nothing(index_elements=['workspace_uuid', 'key'])
            )
            cursor = json.loads(
                (
                    await session.execute(
                        sa.select(WorkspaceMetadata.value)
                        .where(
                            WorkspaceMetadata.workspace_uuid == workspace,
                            WorkspaceMetadata.key == CURSOR_KEY,
                        )
                        .with_for_update()
                    )
                ).scalar_one()
            )
            source = cursor['source']
            if source == 'done':
                return True
            model = MonitoringMessage if source == 'messages' else EventLog
            timestamp = model.timestamp if source == 'messages' else model.created_at
            tenant = model.workspace_uuid if source == 'messages' else model.workspace_id
            # The same (Workspace, timestamp, id) indexes also drive media expiry.
            page = sa.select(model.id.label('id'), timestamp.label('cursor_time')).where(tenant == workspace)
            if cursor.get('after'):
                date, identity = cursor['after']
                page = page.where(
                    sa.tuple_(timestamp, model.id) > sa.tuple_(datetime.datetime.fromisoformat(date), identity)
                )
            page = page.order_by(timestamp, model.id).limit(batch_size).subquery()
            if source == 'messages':
                fields = (
                    'bot_id',
                    'session_id',
                    'timestamp',
                    'bot_name',
                    'pipeline_id',
                    'pipeline_name',
                    'platform',
                    'user_id',
                    'user_name',
                    'role',
                    'event_id',
                )
                statement = sa.select(page.c.cursor_time, model.id, *(getattr(model, field) for field in fields))
            else:
                known_conversation = sa.func.coalesce(
                    model.conversation_id,
                    sa.select(AgentRun.conversation_id)
                    .where(
                        AgentRun.workspace_id == workspace,
                        AgentRun.bot_id == model.bot_id,
                        AgentRun.event_id == model.event_id,
                    )
                    .order_by(AgentRun.id)
                    .limit(1)
                    .scalar_subquery(),
                )
                conversation = sa.func.coalesce(
                    known_conversation,
                    sa.case(
                        (
                            self._json_text(model.input_json, 'chat_type') == 'group',
                            sa.literal('group_') + self._json_text(model.input_json, 'chat_id'),
                        ),
                        (
                            self._json_text(model.input_json, 'chat_type') == 'private',
                            sa.literal('person_') + self._json_text(model.input_json, ('sender', 'id')),
                        ),
                    ),
                )
                statement = sa.select(
                    page.c.cursor_time,
                    model.id,
                    model.bot_id,
                    model.event_id,
                    model.event_time,
                    model.created_at,
                    conversation.label('conversation_id'),
                    sa.case(
                        (
                            sa.and_(
                                model.source == 'platform',
                                model.event_type == 'message.received',
                                sa.func.length(model.metadata_json) <= JSON_LIMIT,
                            ),
                            model.metadata_json,
                        ),
                        else_=None,
                    ).label('metadata_json'),
                    model.actor_id,
                    model.actor_name,
                    model.source,
                    model.event_type,
                    sa.or_(
                        sa.func.length(model.metadata_json) > JSON_LIMIT,
                        sa.and_(known_conversation.is_(None), sa.func.length(model.input_json) > JSON_LIMIT),
                    ).label('oversized'),
                )
            rows = (
                (
                    await session.execute(
                        statement.join(model, model.id == page.c.id).order_by(page.c.cursor_time, model.id)
                    )
                )
                .mappings()
                .all()
            )
            for row in rows:
                if source == 'events' and (row['source'] != 'platform' or row['event_type'] != 'message.received'):
                    continue
                if source == 'events' and row['oversized']:
                    raise ValueError(f'EventLog {row["id"]} exceeds the {JSON_LIMIT}-character legacy metadata limit')
                if not row['bot_id']:
                    continue
                await self._writer.apply_once(
                    session,
                    (message_summary_change if source == 'messages' else ingress_summary_change)(workspace, row),
                    backfill=True,
                )
            if len(rows) < batch_size:
                cursor = {'source': 'events' if source == 'messages' else 'done'}
            else:
                cursor['after'] = [rows[-1]['cursor_time'].isoformat(), rows[-1]['id']]
            await session.execute(
                sa.update(WorkspaceMetadata)
                .where(
                    WorkspaceMetadata.workspace_uuid == workspace,
                    WorkspaceMetadata.key == CURSOR_KEY,
                )
                .values(value=json.dumps(cursor))
            )
            return cursor['source'] == 'done'


async def _main(args):
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine
    from .tenant_uow import TenantUnitOfWork

    url = make_url(os.environ[args.database_url_env])
    if url.drivername not in {'sqlite+aiosqlite', 'postgresql+asyncpg'}:
        raise ValueError('Use an explicit sqlite+aiosqlite or postgresql+asyncpg database URL')
    if url.drivername == 'sqlite+aiosqlite' and (not url.database or not Path(url.database).is_file()):
        raise ValueError('The SQLite database must already exist and be migrated')
    engine = create_async_engine(url)
    if engine.dialect.name == 'sqlite':

        @sa.event.listens_for(engine.sync_engine, 'connect')
        def enable_foreign_keys(connection, _record):
            cursor = connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()

    @asynccontextmanager
    async def scope(workspace):
        async with TenantUnitOfWork(engine, workspace) as uow:
            yield uow.session

    try:
        async with engine.connect() as connection:
            columns = await connection.run_sync(
                lambda conn: {item['name'] for item in sa.inspect(conn).get_columns('monitoring_session_receipts')}
            )
            if not {'session_id', 'covered', 'timestamp'} <= columns:
                raise ValueError('Apply migration 0040_session_summaries before initializing summaries')
        backfill = SessionSummaryBackfill(scope, engine.dialect.name)
        for workspace in args.workspace:
            while not await backfill.run_batch(workspace):
                await asyncio.sleep(0)
            print(f'Workspace {workspace}: session summaries initialized')
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Initialize session summaries offline; stop all writers first')
    parser.add_argument('--workspace', action='append', required=True)
    parser.add_argument('--database-url-env', default='LANGBOT_SUMMARY_DATABASE_URL')
    parser.add_argument('--writers-stopped', action='store_true', required=True)
    asyncio.run(_main(parser.parse_args()))
