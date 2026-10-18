"""Incrementally expire historical inline images without rewriting record history."""

from __future__ import annotations

import asyncio
import datetime
import json
from typing import TYPE_CHECKING

import sqlalchemy as sa

from ..api.http.authz import WorkspaceRequiredError
from ..api.http.context import ExecutionContext
from ..entity.persistence.agent_run import AgentRun, AgentRunEvent
from ..entity.persistence.event_log import EventLog
from ..entity.persistence.metadata import WorkspaceMetadata
from ..entity.persistence.monitoring import MonitoringMessage
from ..entity.persistence.transcript import Transcript
from ..persistence.datetime_utils import as_naive_utc
from .media import MediaCache

if TYPE_CHECKING:
    from ..core.app import Application


ROWS_PER_TABLE = 100
CHARACTERS_PER_TABLE = 8 * 1024 * 1024
CURSOR_PREFIX = 'inline_media_ttl_v1:'


def _redact_columns(values: dict) -> dict:
    updates = {}
    for name, raw in values.items():
        if not raw or ('base64' not in raw and 'data:image/' not in raw):
            continue
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError, RecursionError):
            # Preserve malformed historical text rather than deleting an entire record.
            continue
        if MediaCache.has_inline_images(payload):
            updates[name] = json.dumps(MediaCache.redact_inline_images(payload), ensure_ascii=False)
    return updates


async def cleanup_inline_media(ap: Application, context: ExecutionContext, retention_days: int) -> int:
    """Use the media TTL for immutable history, with durable per-Workspace cursors.

    Bound each table by both candidate count and serialized payload characters. One
    oversized row is processed on its own so it cannot permanently block the cursor.
    """
    if not isinstance(context, ExecutionContext) or not context.workspace_uuid:
        raise WorkspaceRequiredError('Inline media cleanup requires an ExecutionContext')
    if retention_days < 1:
        raise ValueError('retention_days must be >= 1')
    workspace = context.workspace_uuid
    cutoff = as_naive_utc(datetime.datetime.now(datetime.timezone.utc)) - datetime.timedelta(days=retention_days)
    sources = (
        (
            MonitoringMessage,
            MonitoringMessage.timestamp,
            MonitoringMessage.workspace_uuid == workspace,
            ('message_content', 'variables'),
        ),
        (EventLog, EventLog.created_at, EventLog.workspace_id == workspace, ('input_json', 'metadata_json')),
        (AgentRun, AgentRun.created_at, AgentRun.workspace_id == workspace, ('metadata_json',)),
        (
            AgentRunEvent,
            AgentRunEvent.created_at,
            sa.exists(
                sa.select(AgentRun.id).where(
                    AgentRun.run_id == AgentRunEvent.run_id, AgentRun.workspace_id == workspace
                )
            ),
            ('data_json', 'metadata_json'),
        ),
        (
            Transcript,
            Transcript.created_at,
            Transcript.workspace_id == workspace,
            ('content_json', 'attachment_refs_json', 'metadata_json'),
        ),
    )
    manager = ap.persistence_mgr
    cleaned = 0
    for model, timestamp, scope, fields in sources:
        consumed = 0
        cursor_key = CURSOR_PREFIX + model.__tablename__
        cursor_filter = (WorkspaceMetadata.workspace_uuid == workspace, WorkspaceMetadata.key == cursor_key)
        for _ in range(ROWS_PER_TABLE):
            async with manager.tenant_uow(workspace):
                cursor_result = await manager.execute_async(
                    sa.select(WorkspaceMetadata.value).where(*cursor_filter).with_for_update()
                )
                cursor_raw = cursor_result.scalar_one_or_none()
                # Events have no Workspace column. Limit indexed candidates before
                # checking ownership so other Workspaces cannot cause unbounded scans.
                query = sa.select(model.id, timestamp).where(timestamp < cutoff)
                if model is not AgentRunEvent:
                    query = query.where(scope)
                if cursor_raw is not None:
                    after_time, after_id = json.loads(cursor_raw)
                    query = query.where(
                        sa.tuple_(timestamp, model.id)
                        > sa.tuple_(datetime.datetime.fromisoformat(after_time), after_id)
                    )
                result = await manager.execute_async(query.order_by(timestamp, model.id).limit(1))
                row = result.first()
                if row is None:
                    break
                payload = (
                    await manager.execute_async(
                        sa.select(*(getattr(model, field) for field in fields)).where(model.id == row[0], scope)
                    )
                ).first()
                # Missing and foreign candidates still consume budget and advance the
                # cursor. Their payloads are never returned to the cleanup worker.
                values = dict(zip(fields, payload)) if payload is not None else {}
                consumed += sum(len(value) for value in values.values() if value)
                updates = await asyncio.to_thread(_redact_columns, values) if values else {}
                if updates:
                    if model is AgentRun:
                        # Media expiry must not appear as new execution activity.
                        updates['updated_at'] = AgentRun.updated_at
                    changed = await manager.execute_async(
                        sa.update(model)
                        .where(
                            scope,
                            model.id == row[0],
                            *(getattr(model, name) == values[name] for name in fields if name in updates),
                        )
                        .values(**updates)
                    )
                    if not changed.rowcount:
                        # A concurrent writer changed this payload; retry it next time.
                        break
                    cleaned += 1
                cursor = json.dumps([row[1].isoformat(), row[0]])
                if cursor_raw is None:
                    await manager.execute_async(
                        sa.insert(WorkspaceMetadata).values(workspace_uuid=workspace, key=cursor_key, value=cursor)
                    )
                else:
                    await manager.execute_async(sa.update(WorkspaceMetadata).where(*cursor_filter).values(value=cursor))
            if consumed >= CHARACTERS_PER_TABLE:
                break
    return cleaned
