"""Bounded traffic aggregation, independent of record-list pagination."""

from __future__ import annotations

import datetime
import typing

import sqlalchemy

from ....entity.persistence.monitoring import MonitoringLLMCall, MonitoringMessage
from .tenant import TenantContext, require_workspace_uuid

if typing.TYPE_CHECKING:
    from ....core.app import Application

MAX_TRAFFIC_POINTS = 1000


async def get_traffic_series(
    ap: Application,
    context: TenantContext,
    *,
    bot_ids: list[str] | None = None,
    pipeline_ids: list[str] | None = None,
    start_time: datetime.datetime | None = None,
    end_time: datetime.datetime | None = None,
) -> dict:
    """Count all matching records in UTC buckets, returning at most 1000 points."""
    workspace_uuid = require_workspace_uuid(context)
    bucket = 'hour' if start_time and end_time and end_time - start_time <= datetime.timedelta(days=7) else 'day'
    step = datetime.timedelta(hours=1) if bucket == 'hour' else datetime.timedelta(days=1)
    postgres = ap.persistence_mgr.get_db_engine().dialect.name == 'postgresql'
    points: dict[datetime.datetime, dict[str, int]] = {}
    truncated = False
    for model, field in ((MonitoringMessage, 'messages'), (MonitoringLLMCall, 'llm_calls')):
        timestamp = model.timestamp
        if postgres:
            time_bucket = sqlalchemy.func.date_trunc(bucket, timestamp)
        else:
            pattern = '%Y-%m-%dT%H:00:00' if bucket == 'hour' else '%Y-%m-%dT00:00:00'
            time_bucket = sqlalchemy.func.strftime(pattern, timestamp)
        conditions = [model.workspace_uuid == workspace_uuid]
        if bot_ids:
            conditions.append(model.bot_id.in_(bot_ids))
        if pipeline_ids:
            conditions.append(model.pipeline_id.in_(pipeline_ids))
        if start_time is not None:
            conditions.append(timestamp >= start_time)
        if end_time is not None:
            conditions.append(timestamp <= end_time)
        statement = (
            sqlalchemy.select(time_bucket.label('bucket'), sqlalchemy.func.count(model.id).label('count'))
            .where(*conditions)
            .group_by(time_bucket)
            .order_by(time_bucket)
            .limit(MAX_TRAFFIC_POINTS + 1)
        )
        result = await ap.persistence_mgr.execute_async(statement)
        rows = result.all()
        truncated = truncated or len(rows) > MAX_TRAFFIC_POINTS
        for timestamp_value, count in rows[:MAX_TRAFFIC_POINTS]:
            key = (
                datetime.datetime.fromisoformat(timestamp_value)
                if isinstance(timestamp_value, str)
                else timestamp_value
            )
            points.setdefault(key, {'messages': 0, 'llm_calls': 0})[field] = int(count)

    def floor(value: datetime.datetime) -> datetime.datetime:
        return value.replace(minute=0, second=0, microsecond=0, **({'hour': 0} if bucket == 'day' else {}))

    first = floor(start_time) if start_time is not None else min(points, default=None)
    last = floor(end_time) if end_time is not None else max(points, default=None)
    series = []
    if first is not None and last is not None:
        cursor = first
        while cursor <= last and len(series) < MAX_TRAFFIC_POINTS:
            series.append(
                {'timestamp': cursor.isoformat() + 'Z', **points.get(cursor, {'messages': 0, 'llm_calls': 0})}
            )
            cursor += step
        truncated = truncated or cursor <= last
    return {'bucket': bucket, 'points': series, 'truncated': truncated}
