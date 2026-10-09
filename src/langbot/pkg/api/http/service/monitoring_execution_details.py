"""Tenant-scoped execution inputs, outputs, related runs and conversation history."""

from __future__ import annotations

import datetime
import json
from langbot_plugin.api.entities.builtin.platform.events import event_summary

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from ....entity.persistence.agent_run import AgentRun, AgentRunEvent
from ....entity.persistence.event_log import EventLog
from ....entity.persistence.transcript import Transcript
from ....entity.persistence import monitoring as models
from .tenant import require_workspace_uuid


def epoch(value):
    if value is None:
        return None
    return int(value.replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)


def parsed(value, fallback=None):
    try:
        return json.loads(value) if value else fallback
    except (TypeError, ValueError):
        return fallback


def event_content(content, event_data):
    """Keep event-specific properties alongside the normalized message input."""
    if not isinstance(event_data, dict) or not event_data:
        return content
    # Keep the original event intact; text is the existing normalized input field.
    return {'text': event_summary(event_data), 'event': event_data, 'input': content}


def event_item(row):
    metadata = parsed(row.metadata_json, {})
    return {
        'id': row.event_id,
        'event_type': row.event_type,
        'source': row.source,
        'timestamp_ms': epoch(row.event_time or row.created_at),
        'actor_id': row.actor_id,
        'actor_name': row.actor_name,
        'conversation_id': row.conversation_id,
        'thread_id': row.thread_id,
        'content': event_content(parsed(row.input_json, None) or row.input_summary, metadata.get('input_event')),
        'metadata': metadata,
    }


def message_item(row):
    return {
        'id': row.id,
        'role': row.role or 'user',
        'timestamp_ms': epoch(row.timestamp),
        'content': parsed(row.message_content, None) or row.message_content,
        'actor_id': row.user_id,
        'actor_name': row.user_name,
        'status': row.status,
        'event_id': row.event_id,
        'run_id': row.run_id,
        'origin': 'delivery' if row.role == 'assistant' else 'input',
        'delivery': parsed(row.variables, {}) if row.role == 'assistant' else None,
    }


def transcript_item(row):
    return {
        'id': row.transcript_id,
        'role': row.role,
        'timestamp_ms': epoch(row.created_at),
        'content': parsed(row.content_json, None) or row.content,
        'attachments': parsed(row.attachment_refs_json, []),
        'event_id': row.event_id,
        'run_id': row.run_id,
        'origin': 'generated' if row.role == 'assistant' else 'input',
    }


class ExecutionDetailsMixin:
    def _session_message_source(self, workspace, bot_ids):
        """Combine delivered messages with ingress missing from the legacy ledger."""
        message = models.MonitoringMessage
        conversation = sa.func.coalesce(
            EventLog.conversation_id,
            sa.select(AgentRun.conversation_id).where(
                AgentRun.workspace_id == workspace,
                AgentRun.bot_id == EventLog.bot_id,
                AgentRun.event_id == EventLog.event_id,
            ).order_by(AgentRun.id).limit(1).scalar_subquery(),
            sa.case(
                (self._execution_json_text(EventLog.input_json, 'chat_type') == 'group',
                 sa.literal('group_') + self._execution_json_text(EventLog.input_json, 'chat_id')),
                (self._execution_json_text(EventLog.input_json, 'chat_type') == 'private',
                 sa.literal('person_') + self._execution_json_text(EventLog.input_json, ('sender', 'id'))),
            ),
        )
        values = {
            'id': EventLog.event_id,
            'workspace_uuid': EventLog.workspace_id,
            'timestamp': sa.func.coalesce(EventLog.event_time, EventLog.created_at),
            'bot_id': EventLog.bot_id,
            'bot_name': sa.func.coalesce(self._execution_json_text(EventLog.metadata_json, 'bot_name'), ''),
            'pipeline_id': sa.func.coalesce(self._execution_json_text(EventLog.metadata_json, ('routes', 0, 'target_uuid')), ''),
            'pipeline_name': sa.func.coalesce(self._execution_json_text(EventLog.metadata_json, ('routes', 0, 'target_type')), ''),
            'message_content': sa.func.coalesce(EventLog.input_json, EventLog.input_summary, ''),
            'session_id': conversation,
            'status': sa.func.coalesce(self._execution_json_text(EventLog.metadata_json, 'status'), 'success'),
            'level': sa.literal('info'),
            'platform': self._execution_json_text(EventLog.metadata_json, 'platform'),
            'user_id': EventLog.actor_id,
            'user_name': EventLog.actor_name,
            'role': sa.literal('user'),
            'event_id': EventLog.event_id,
            'run_id': EventLog.run_id,
        }
        columns = list(message.__table__.columns)
        stored = sa.select(*columns).where(message.workspace_uuid == workspace, message.bot_id.in_(bot_ids))
        incoming = sa.select(*[
            values.get(column.name, sa.literal(None)).label(column.name) for column in columns
        ]).where(
            EventLog.workspace_id == workspace,
            EventLog.bot_id.in_(bot_ids),
            EventLog.source == 'platform',
            EventLog.event_type == 'message.received',
            conversation.is_not(None),
            conversation != '',
            ~sa.exists(sa.select(message.id).where(
                message.workspace_uuid == workspace,
                message.bot_id == EventLog.bot_id,
                sa.func.coalesce(message.role, 'user') != 'assistant',
                sa.or_(message.event_id == EventLog.event_id, message.id == EventLog.event_id),
            )),
        )
        return sa.union_all(stored, incoming).subquery()

    async def _session_projection_page(self, workspace, statement, limit, offset):
        count = (await self._execution_query(workspace, sa.select(sa.func.count()).select_from(statement.subquery()))).scalar_one()
        rows = (await self._execution_query(workspace, statement.limit(limit).offset(offset))).mappings().all()
        return [
            {key: value.isoformat() if isinstance(value, datetime.datetime) else value for key, value in row.items()}
            for row in rows
        ], count

    async def get_bot_conversation_sessions(self, workspace, bot_ids, start_time, end_time, user_query, is_active, limit, offset):
        """Read session summaries across processor types without mutating history."""
        messages = self._session_message_source(workspace, bot_ids)
        key = [messages.c.workspace_uuid, messages.c.bot_id, messages.c.session_id]
        ranked = sa.select(
            *messages.c,
            sa.func.row_number().over(partition_by=key, order_by=[
                sa.case((messages.c.role == 'user', 0), else_=1), messages.c.timestamp.desc(), messages.c.id.desc(),
            ]).label('position'),
            sa.func.min(messages.c.timestamp).over(partition_by=key).label('first_seen'),
            sa.func.max(messages.c.timestamp).over(partition_by=key).label('last_seen'),
            sa.func.count().over(partition_by=key).label('count'),
        ).where(messages.c.session_id != '').subquery()
        session = models.MonitoringSession
        fields = list(session.__table__.columns)
        projected = {
            'start_time': ranked.c.first_seen,
            'last_activity': ranked.c.last_seen,
            'message_count': ranked.c['count'],
            'is_active': sa.literal(True),
        }
        derived = sa.select(*[
            (projected[field.name] if field.name in projected else ranked.c[field.name]).label(field.name)
            for field in fields
        ]).where(ranked.c.position == 1)
        existing = sa.select(*fields).where(session.workspace_uuid == workspace, session.bot_id.in_(bot_ids))
        combined = sa.union_all(existing, derived).subquery()
        group = [combined.c.workspace_uuid, combined.c.bot_id, combined.c.session_id]
        merged = sa.select(
            *[combined.c[field.name] for field in fields if field.name not in {'message_count', 'start_time', 'last_activity'}],
            sa.func.max(combined.c.message_count).over(partition_by=group).label('message_count'),
            sa.func.min(combined.c.start_time).over(partition_by=group).label('start_time'),
            sa.func.max(combined.c.last_activity).over(partition_by=group).label('last_activity'),
            sa.func.row_number().over(partition_by=group, order_by=combined.c.last_activity.desc()).label('position'),
        ).subquery()
        query = sa.select(*[merged.c[field.name] for field in fields]).where(merged.c.position == 1)
        if start_time:
            query = query.where(merged.c.last_activity >= start_time)
        if end_time:
            query = query.where(merged.c.last_activity <= end_time)
        if user_query and user_query.strip():
            pattern = f'%{user_query.strip()}%'
            query = query.where(sa.or_(merged.c.user_id.ilike(pattern), merged.c.user_name.ilike(pattern)))
        if is_active is not None:
            query = query.where(merged.c.is_active == is_active)
        return await self._session_projection_page(
            workspace, query.order_by(merged.c.last_activity.desc(), merged.c.session_id), limit, offset,
        )

    def _execution_json_text(self, column, key):
        # SQLite JSON functions accept TEXT directly; PostgreSQL operators
        # require an explicit JSON cast for the existing text-backed journals.
        if self.ap.persistence_mgr.get_db_engine().dialect.name == 'sqlite':
            expression = sa.type_coerce(column, sa.JSON)
        else:
            expression = sa.cast(column, sa.JSON)
        return expression[key].as_string()

    async def link_execution_message(self, context, message_id, run_id, event_id):
        workspace = self._require_write_context(context)
        statement = (
            sa.update(models.MonitoringMessage)
            .where(
                models.MonitoringMessage.workspace_uuid == workspace,
                models.MonitoringMessage.id == message_id,
            )
            .values(run_id=run_id, event_id=sa.func.coalesce(models.MonitoringMessage.event_id, event_id))
        )
        tenant_uow = getattr(self.ap.persistence_mgr, 'tenant_uow', None)
        if callable(tenant_uow):
            async with tenant_uow(workspace) as uow:
                await uow.session.execute(statement)
        else:
            await self.ap.persistence_mgr.execute_async(statement)

    async def record_ingress_event(
        self,
        context,
        *,
        event_id,
        event_type,
        bot_id,
        bot_name,
        platform,
        payload,
        actor_id=None,
        actor_name=None,
        conversation_id=None,
        status='running',
        routes=None,
    ):
        """Persist entry facts even when routing never creates a processor run."""
        from ....agent.runner.event_log_store import EventLogStore
        from .monitoring import _message_preview

        workspace = self._require_write_context(context)
        store = EventLogStore(self.ap.persistence_mgr.get_db_engine())
        # Reuse the message sanitizer (including inline-media handling) instead
        # of storing an unbounded adapter object in the event journal.
        content = parsed(self._sanitize_message_content(json.dumps(payload, ensure_ascii=False, default=str)), {})
        summary = _message_preview(json.dumps(content, ensure_ascii=False), 1000) if content else event_type
        await store.append_event(
            event_id=event_id,
            event_type=event_type,
            source='platform',
            workspace_id=workspace,
            bot_id=bot_id,
            actor_id=actor_id,
            actor_name=actor_name,
            conversation_id=conversation_id,
            actor_type='user' if actor_id else 'system',
            input_summary=summary,
            input_json=content,
            metadata={'status': status, 'bot_name': bot_name, 'platform': platform},
        )
        if routes is not None:
            safe_routes = []
            for route in routes:
                if isinstance(route, BaseException):
                    safe_routes.append({'status': 'failed', 'reason': str(route)})
                elif isinstance(route, dict):
                    safe_routes.append(
                        {
                            key: route.get(key)
                            for key in (
                                'status',
                                'reason',
                                'target_type',
                                'target_uuid',
                                'run_id',
                                'failure_code',
                            )
                        }
                    )
            metadata = {'status': status, 'bot_name': bot_name, 'platform': platform, 'routes': safe_routes}
            async with AsyncSession(self.ap.persistence_mgr.get_db_engine()) as session:
                await session.execute(
                    sa.update(EventLog)
                    .where(
                        EventLog.workspace_id == workspace,
                        EventLog.event_id == event_id,
                    )
                    .values(metadata_json=json.dumps(metadata, ensure_ascii=False))
                )
                await session.commit()

    async def _execution_query(self, workspace, statement):
        tenant_uow = getattr(self.ap.persistence_mgr, 'tenant_uow', None)
        if callable(tenant_uow):
            async with tenant_uow(workspace) as uow:
                return await uow.session.execute(statement)
        async with AsyncSession(self.ap.persistence_mgr.get_db_engine()) as session:
            return await session.execute(statement)

    async def _execution_rows(self, workspace, statement):
        return list((await self._execution_query(workspace, statement)).scalars().all())

    async def _execution_page(self, workspace, statement, convert, offset, limit):
        rows = await self._execution_rows(workspace, statement.offset(offset).limit(limit + 1))
        return {
            'items': [convert(row) for row in rows[:limit]],
            'has_more': len(rows) > limit,
            'next_offset': offset + min(len(rows), limit),
        }

    def _unhandled_event_conditions(self, workspace, bot_ids=None, start_time=None, end_time=None):
        # Absorbed steering events belong to an existing run, too.
        conditions = [
            EventLog.workspace_id == workspace,
            # The primary route is first; plugin subscriptions follow it.
            # Delivered pipeline ingress is not an unhandled execution, including
            # older queued/aggregated messages whose trace identity was lost.
            ~sa.and_(
                sa.func.coalesce(
                    self._execution_json_text(EventLog.metadata_json, ('routes', 0, 'target_type')), ''
                ) == 'pipeline',
                sa.func.coalesce(
                    self._execution_json_text(EventLog.metadata_json, ('routes', 0, 'status')), ''
                ) == 'delivered',
            ),
            ~sa.exists(
                sa.select(AgentRun.id).where(
                    AgentRun.workspace_id == workspace,
                    sa.or_(
                        AgentRun.event_id == EventLog.event_id,
                        AgentRun.run_id == EventLog.run_id,
                        self._execution_json_text(AgentRun.metadata_json, 'ingress_event_id') == EventLog.event_id,
                    ),
                )
            ),
            ~sa.exists(
                sa.select(models.MonitoringMessage.id).where(
                    models.MonitoringMessage.workspace_uuid == workspace,
                    models.MonitoringMessage.event_id == EventLog.event_id,
                )
            ),
        ]
        if bot_ids:
            conditions.append(EventLog.bot_id.in_(bot_ids))
        if start_time:
            conditions.append(EventLog.created_at >= start_time)
        if end_time:
            conditions.append(EventLog.created_at <= end_time)
        return conditions

    def _serialize_event_execution(self, row):
        metadata = parsed(row.metadata_json, {})
        status = metadata.get('status', 'ignored')
        return {
            'source': 'event',
            'id': row.event_id,
            'event_id': row.event_id,
            'status': status,
            'status_group': status,
            'title': row.event_type,
            'input_preview': row.input_summary or '',
            'target_kind': 'event',
            'target_id': None,
            'target_name': None,
            'bot_id': row.bot_id,
            'bot_name': metadata.get('bot_name'),
            'platform': metadata.get('platform') or row.source,
            'user_id': row.actor_id,
            'user_name': row.actor_name,
            'conversation_id': row.conversation_id,
            'session_id': row.conversation_id,
            'created_at_ms': epoch(row.created_at),
            'started_at_ms': None,
            'finished_at_ms': None,
            'duration_ms': None,
            'usage': None,
            'cost': None,
            'queue_name': None,
            'pipeline_id': None,
            'pipeline_name': None,
            'runner_id': None,
            'debug': row.source == 'debug',
            'has_error': status == 'failed',
            'status_reason': metadata.get('reason'),
        }

    async def enrich_execution_rows(self, workspace, items):
        pipeline_items = {item['id']: item for item in items if item.get('source') == 'pipeline'}
        if pipeline_items:
            # Pipeline rows own the UI identity; their linked Runner ledger owns
            # timing and usage. Read them in one batch for both list and detail.
            linked = await self._execution_query(
                workspace,
                sa.select(models.MonitoringMessage.id, AgentRun)
                .join(AgentRun, sa.and_(
                    AgentRun.workspace_id == workspace,
                    AgentRun.run_id == models.MonitoringMessage.run_id,
                ))
                .where(
                    models.MonitoringMessage.workspace_uuid == workspace,
                    models.MonitoringMessage.id.in_(pipeline_items),
                ),
            )
            for message_id, run in linked.all():
                metrics = self._serialize_agent_execution(run)
                pipeline_items[message_id].update({
                    key: metrics[key]
                    for key in ('started_at_ms', 'finished_at_ms', 'duration_ms', 'usage', 'cost')
                })

            calls = models.MonitoringLLMCall
            usage_rows = await self._execution_query(
                workspace,
                sa.select(
                    calls.message_id,
                    sa.func.sum(calls.input_tokens),
                    sa.func.sum(calls.output_tokens),
                    sa.func.sum(calls.total_tokens),
                ).where(
                    calls.workspace_uuid == workspace,
                    calls.message_id.in_(pipeline_items),
                ).group_by(calls.message_id),
            )
            for message_id, input_tokens, output_tokens, total_tokens in usage_rows.all():
                if not pipeline_items[message_id].get('usage'):
                    pipeline_items[message_id]['usage'] = {
                        'input_tokens': int(input_tokens or 0),
                        'output_tokens': int(output_tokens or 0),
                        'total_tokens': int(total_tokens or 0),
                    }
        ids = {item['event_id'] for item in items if item.get('event_id')}
        if not ids:
            return
        events = await self._execution_rows(
            workspace,
            sa.select(EventLog).where(
                EventLog.workspace_id == workspace,
                EventLog.event_id.in_(ids),
            ),
        )
        by_id = {row.event_id: row for row in events}
        for item in items:
            event = by_id.get(item.get('event_id'))
            if event:
                meta = parsed(event.metadata_json, {})
                item.update(
                    event_type=event.event_type,
                    input_preview=event.input_summary or item.get('input_preview') or '',
                    user_id=event.actor_id,
                    user_name=event.actor_name,
                    platform=meta.get('platform') or event.source,
                    bot_name=item.get('bot_name') or meta.get('bot_name'),
                )

    async def get_execution_detail(self, context, source, execution_id, *, section=None, offset=0, limit=100):
        workspace = require_workspace_uuid(context)
        limit, offset = self.normalize_page_window(limit, offset)
        limit = min(limit, 100)
        sections = {
            'inputs',
            'outputs',
            'deliveries',
            'conversation',
            'related',
            'events',
            'llm_calls',
            'tool_calls',
            'errors',
        }
        if section is not None and section not in sections:
            raise ValueError('Unknown execution section')

        run = message = event = None
        if source in {'agent', 'auto'}:
            rows = await self._execution_rows(
                workspace,
                sa.select(AgentRun).where(
                    AgentRun.workspace_id == workspace,
                    AgentRun.run_id == execution_id,
                ),
            )
            run = rows[0] if rows else None
        if run is None and source in {'pipeline', 'auto'}:
            rows = await self._execution_rows(
                workspace,
                sa.select(models.MonitoringMessage).where(
                    models.MonitoringMessage.workspace_uuid == workspace,
                    models.MonitoringMessage.id == execution_id,
                ),
            )
            message = rows[0] if rows else None
            if message and message.parent_message_id:
                return await self.get_execution_detail(
                    context, 'auto', message.parent_message_id, section=section, offset=offset, limit=limit
                )
        if run is None and message is None and source in {'event', 'auto'}:
            rows = await self._execution_rows(
                workspace,
                sa.select(EventLog).where(
                    EventLog.workspace_id == workspace,
                    EventLog.event_id == execution_id,
                ),
            )
            event = rows[0] if rows else None
        if run is None and message is None and event is None:
            raise ValueError('Execution not found')

        if message and message.run_id:
            linked = await self._execution_rows(
                workspace,
                sa.select(AgentRun).where(AgentRun.workspace_id == workspace, AgentRun.run_id == message.run_id),
            )
            if linked:
                linked_run = linked[0]
            else:
                linked_run = None
        else:
            linked_run = None

        if run:
            names = await self._agent_names(workspace, [run])
            row = self._serialize_agent_execution(run, names)
            event_id, bot, conversation, thread = run.event_id, run.bot_id, run.conversation_id, run.thread_id
            run_id = run.run_id
        elif message:
            row = self._serialize_pipeline_execution(message)
            event_id, bot, conversation, thread = message.event_id, message.bot_id, message.session_id, None
            run_id = message.run_id
            if linked_run:
                row['duration_ms'] = (
                    int((linked_run.finished_at - linked_run.started_at).total_seconds() * 1000)
                    if linked_run.started_at and linked_run.finished_at
                    else None
                )
                row['usage'] = parsed(linked_run.usage_json)
                row['status_reason'] = linked_run.status_reason
        else:
            row = self._serialize_event_execution(event)
            event_id, bot, conversation, thread = event.event_id, event.bot_id, event.conversation_id, event.thread_id
            run_id = event.run_id
        await self.enrich_execution_rows(workspace, [row])

        ledger = run or linked_run
        ingress_id = parsed(ledger.metadata_json, {}).get('ingress_event_id') if ledger else None
        event_conditions = [
            EventLog.workspace_id == workspace,
            sa.or_(
                EventLog.event_id == ingress_id if ingress_id else sa.false(),
                EventLog.event_id == ledger.event_id if ledger else sa.false(),
                EventLog.event_id == event_id if event_id else sa.false(),
                EventLog.run_id == run_id if run_id else sa.false(),
            ),
        ]
        event_ids = sa.select(EventLog.event_id).where(*event_conditions)
        # All joins use explicit identities. Session/time matching is reserved
        # for the visibly separate conversation history section.
        message_scope = [models.MonitoringMessage.workspace_uuid == workspace]
        related_message = sa.or_(
            models.MonitoringMessage.id == message.id if message else sa.false(),
            models.MonitoringMessage.parent_message_id == (message.id if message else run_id)
            if message or run_id
            else sa.false(),
            models.MonitoringMessage.run_id == run_id if run_id else sa.false(),
        )
        transcript_scope = [Transcript.workspace_id == workspace, Transcript.bot_id == bot]
        transcripts = sa.select(Transcript).where(
            *transcript_scope,
            sa.or_(
                Transcript.run_id == run_id if run_id else sa.false(),
                sa.and_(Transcript.role == 'user', Transcript.event_id.in_(event_ids)),
            ),
        )
        call_ids = sa.select(models.MonitoringMessage.id).where(*message_scope, related_message)
        statements = {
            'inputs': (sa.select(EventLog).where(*event_conditions).order_by(EventLog.id.asc()), event_item),
            'outputs': (transcripts.where(Transcript.role != 'user').order_by(Transcript.seq.asc()), transcript_item),
            'deliveries': (
                sa.select(models.MonitoringMessage)
                .where(*message_scope, related_message, models.MonitoringMessage.role == 'assistant')
                .order_by(models.MonitoringMessage.timestamp.asc(), models.MonitoringMessage.id.asc()),
                message_item,
            ),
            'events': (
                sa.select(AgentRunEvent)
                .where(AgentRunEvent.run_id == run_id if run_id else sa.false())
                .order_by(AgentRunEvent.sequence.asc()),
                lambda r: {
                    'id': r.id,
                    'sequence': r.sequence,
                    'type': r.type,
                    'data': parsed(r.data_json, {}),
                    'timestamp_ms': epoch(r.created_at),
                },
            ),
        }
        for name, model in [
            ('llm_calls', models.MonitoringLLMCall),
            ('tool_calls', models.MonitoringToolCall),
            ('errors', models.MonitoringError),
        ]:
            statements[name] = (
                sa.select(model)
                .where(
                    model.workspace_uuid == workspace,
                    sa.or_(
                        model.message_id.in_(call_ids),
                        model.message_id == run_id if run_id else sa.false(),
                    ),
                )
                .order_by(model.timestamp.asc(), model.id.asc()),
                lambda r, model=model: self.ap.persistence_mgr.serialize_model(model, r),
            )
        if message:
            statements['conversation'] = (
                sa.select(models.MonitoringMessage)
                .where(
                    *message_scope,
                    models.MonitoringMessage.bot_id == bot,
                    models.MonitoringMessage.session_id == conversation,
                )
                .order_by(models.MonitoringMessage.timestamp.desc(), models.MonitoringMessage.id.desc()),
                message_item,
            )
        else:
            statements['conversation'] = (
                sa.select(Transcript)
                .where(
                    *transcript_scope,
                    Transcript.conversation_id == conversation if conversation else sa.false(),
                    Transcript.thread_id == thread,
                )
                .order_by(Transcript.seq.desc()),
                transcript_item,
            )

        pages = {}
        for name, (query, convert) in statements.items():
            if section is None or section == name:
                pages[name] = await self._execution_page(workspace, query, convert, offset, limit)
        if run:
            meta = parsed(run.metadata_json, {})
            for item in pages.get('inputs', {}).get('items', []):
                # Older event logs omitted data, but the root run may retain it.
                # Do not apply the root snapshot to later steering events.
                if item['id'] == run.event_id and not item.get('metadata', {}).get('input_event'):
                    item['content'] = event_content(item['content'], meta.get('input_event'))
        if message and (section is None or section == 'inputs'):
            # The original rich message is authoritative even when the event
            # log is absent or only retained a compact event summary.
            if offset == 0:
                pages['inputs']['items'].insert(0, message_item(message))
        if (
            run
            and not pages.get('inputs', {}).get('items')
            and offset == 0
            and (section is None or section == 'inputs')
        ):
            meta = parsed(run.metadata_json, {})
            content = event_content(meta.get('input'), meta.get('input_event'))
            if content:
                pages['inputs']['items'] = [
                    {'id': run.event_id or run.run_id, 'content': content, 'timestamp_ms': epoch(run.created_at)}
                ]

        if section is None or section == 'related':
            # Union of ledger executions and legacy pipeline roots. SQL paging
            # avoids silently dropping siblings on highly fanned-out events.
            related_runs = sa.select(
                sa.literal('agent').label('source'), AgentRun.run_id.label('id'), AgentRun.created_at.label('time')
            ).where(
                AgentRun.workspace_id == workspace,
                sa.or_(
                    AgentRun.event_id.in_(event_ids),
                    self._execution_json_text(AgentRun.metadata_json, 'ingress_event_id').in_(event_ids),
                ),
                AgentRun.run_id != (run_id or ''),
                ~sa.exists().where(
                    models.MonitoringMessage.workspace_uuid == workspace,
                    models.MonitoringMessage.run_id == AgentRun.run_id,
                    models.MonitoringMessage.role != 'assistant',
                ),
            )
            related_messages = sa.select(
                sa.literal('pipeline'), models.MonitoringMessage.id, models.MonitoringMessage.timestamp
            ).where(
                *message_scope,
                models.MonitoringMessage.event_id.in_(event_ids),
                models.MonitoringMessage.role != 'assistant',
                models.MonitoringMessage.id != (message.id if message else ''),
            )
            union = sa.union_all(related_runs, related_messages).subquery()
            refs = (
                await self._execution_query(
                    workspace,
                    sa.select(union).order_by(union.c.time, union.c.source, union.c.id).offset(offset).limit(limit + 1),
                )
            ).all()
            related = []
            for ref in refs[:limit]:
                if ref.source == 'agent':
                    records = await self._execution_rows(
                        workspace,
                        sa.select(AgentRun).where(AgentRun.workspace_id == workspace, AgentRun.run_id == ref.id),
                    )
                    related.append(
                        self._serialize_agent_execution(records[0], await self._agent_names(workspace, records))
                    )
                else:
                    records = await self._execution_rows(
                        workspace,
                        sa.select(models.MonitoringMessage).where(
                            *message_scope, models.MonitoringMessage.id == ref.id
                        ),
                    )
                    related.append(self._serialize_pipeline_execution(records[0]))
            pages['related'] = {
                'items': related,
                'has_more': len(refs) > limit,
                'next_offset': offset + min(len(refs), limit),
            }

        result = {
            'source': row['source'],
            'row': row,
            'pages': pages,
            'legacy_context': bool(message and not message.event_id),
        }
        if run:
            # Do not expose runtime authorization, leases or claim tokens.
            result['run'] = {'run_id': run.run_id, 'status': run.status, 'status_reason': run.status_reason}
        if message:
            result['message'] = self.ap.persistence_mgr.serialize_model(models.MonitoringMessage, message)
        # Backwards-compatible fields for existing API consumers.
        for key in ('events', 'llm_calls', 'tool_calls', 'errors'):
            if key in pages:
                result[key] = pages[key]['items']
        result['has_more'] = pages.get('events', {}).get('has_more', False)
        result['next_cursor'] = pages.get('events', {}).get('next_offset')
        return result
