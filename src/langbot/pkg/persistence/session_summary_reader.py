"""Only the summary table is available to the interactive list implementation."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from ..entity.persistence.monitoring import MonitoringSession
from .session_summary_contract import SessionListFilter


SessionScope = Callable[[str], AbstractAsyncContextManager[AsyncSession]]
SUMMARY_FIELDS = (
    'workspace_uuid',
    'bot_id',
    'session_id',
    'bot_name',
    'pipeline_id',
    'pipeline_name',
    'message_count',
    'start_time',
    'last_activity',
    'is_active',
    'platform',
    'user_id',
    'user_name',
)


class SqlSessionSummaryReader:
    def __init__(self, session_scope: SessionScope):
        self._session_scope = session_scope

    async def list_page(
        self, workspace: str, filters: SessionListFilter, limit: int, offset: int
    ) -> tuple[list[dict], int]:
        model = MonitoringSession
        conditions = [model.workspace_uuid == workspace]
        if filters.bot_ids:
            conditions.append(model.bot_id.in_(filters.bot_ids))
        if filters.pipeline_ids:
            conditions.append(model.pipeline_id.in_(filters.pipeline_ids))
        if filters.start_time is not None:
            conditions.append(model.last_activity >= filters.start_time)
        if filters.end_time is not None:
            conditions.append(model.last_activity <= filters.end_time)
        if filters.user_query and filters.user_query.strip():
            pattern = f'%{filters.user_query.strip()}%'
            conditions.append(sa.or_(model.user_id.ilike(pattern), model.user_name.ilike(pattern)))
        if filters.is_active is not None:
            conditions.append(model.is_active == filters.is_active)
        async with self._session_scope(workspace) as session:
            total = (
                await session.execute(sa.select(sa.func.count()).select_from(model).where(*conditions))
            ).scalar_one()
            rows = (
                (
                    await session.execute(
                        sa.select(*(getattr(model, field) for field in SUMMARY_FIELDS))
                        .where(*conditions)
                        .order_by(model.last_activity.desc(), model.bot_id, model.session_id)
                        .limit(limit)
                        .offset(offset)
                    )
                )
                .mappings()
                .all()
            )
        return [
            {key: value.isoformat() if isinstance(value, datetime.datetime) else value for key, value in row.items()}
            for row in rows
        ], total
