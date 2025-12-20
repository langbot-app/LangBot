from __future__ import annotations

import uuid
import datetime
import sqlalchemy
import typing

from ....core import app
from ....entity.persistence import monitoring as persistence_monitoring


class MonitoringService:
    """Monitoring service"""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    # ========== Recording Methods ==========

    async def record_message(
        self,
        bot_id: str,
        bot_name: str,
        pipeline_id: str,
        pipeline_name: str,
        message_content: str,
        session_id: str,
        status: str = 'success',
        level: str = 'info',
        platform: str | None = None,
        user_id: str | None = None,
    ) -> str:
        """Record a message"""
        message_id = str(uuid.uuid4())
        message_data = {
            'id': message_id,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
            'bot_id': bot_id,
            'bot_name': bot_name,
            'pipeline_id': pipeline_id,
            'pipeline_name': pipeline_name,
            'message_content': message_content,
            'session_id': session_id,
            'status': status,
            'level': level,
            'platform': platform,
            'user_id': user_id,
        }

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_monitoring.MonitoringMessage).values(message_data)
        )

        return message_id

    async def record_llm_call(
        self,
        bot_id: str,
        bot_name: str,
        pipeline_id: str,
        pipeline_name: str,
        session_id: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        duration: int,
        status: str = 'success',
        cost: float | None = None,
        error_message: str | None = None,
    ) -> str:
        """Record an LLM call"""
        call_id = str(uuid.uuid4())
        call_data = {
            'id': call_id,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
            'model_name': model_name,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': input_tokens + output_tokens,
            'duration': duration,
            'cost': cost,
            'status': status,
            'bot_id': bot_id,
            'bot_name': bot_name,
            'pipeline_id': pipeline_id,
            'pipeline_name': pipeline_name,
            'session_id': session_id,
            'error_message': error_message,
        }

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_monitoring.MonitoringLLMCall).values(call_data)
        )

        return call_id

    async def record_session_start(
        self,
        session_id: str,
        bot_id: str,
        bot_name: str,
        pipeline_id: str,
        pipeline_name: str,
        platform: str | None = None,
        user_id: str | None = None,
    ) -> None:
        """Record a new session"""
        session_data = {
            'session_id': session_id,
            'bot_id': bot_id,
            'bot_name': bot_name,
            'pipeline_id': pipeline_id,
            'pipeline_name': pipeline_name,
            'message_count': 0,
            'start_time': datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
            'last_activity': datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
            'is_active': True,
            'platform': platform,
            'user_id': user_id,
        }

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_monitoring.MonitoringSession).values(session_data)
        )

    async def update_session_activity(self, session_id: str) -> None:
        """Update session last activity time and increment message count"""
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_monitoring.MonitoringSession)
            .where(persistence_monitoring.MonitoringSession.session_id == session_id)
            .values({
                'last_activity': datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
                'message_count': persistence_monitoring.MonitoringSession.message_count + 1,
            })
        )

    async def record_error(
        self,
        bot_id: str,
        bot_name: str,
        pipeline_id: str,
        pipeline_name: str,
        error_type: str,
        error_message: str,
        session_id: str | None = None,
        stack_trace: str | None = None,
    ) -> str:
        """Record an error"""
        error_id = str(uuid.uuid4())
        error_data = {
            'id': error_id,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
            'error_type': error_type,
            'error_message': error_message,
            'bot_id': bot_id,
            'bot_name': bot_name,
            'pipeline_id': pipeline_id,
            'pipeline_name': pipeline_name,
            'session_id': session_id,
            'stack_trace': stack_trace,
        }

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_monitoring.MonitoringError).values(error_data)
        )

        return error_id

    # ========== Query Methods ==========

    async def get_overview_metrics(
        self,
        bot_ids: list[str] | None = None,
        pipeline_ids: list[str] | None = None,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
    ) -> dict:
        """Get overview metrics"""
        # Build base query conditions
        message_conditions = []
        llm_conditions = []
        session_conditions = []

        if bot_ids:
            message_conditions.append(persistence_monitoring.MonitoringMessage.bot_id.in_(bot_ids))
            llm_conditions.append(persistence_monitoring.MonitoringLLMCall.bot_id.in_(bot_ids))
            session_conditions.append(persistence_monitoring.MonitoringSession.bot_id.in_(bot_ids))

        if pipeline_ids:
            message_conditions.append(persistence_monitoring.MonitoringMessage.pipeline_id.in_(pipeline_ids))
            llm_conditions.append(persistence_monitoring.MonitoringLLMCall.pipeline_id.in_(pipeline_ids))
            session_conditions.append(persistence_monitoring.MonitoringSession.pipeline_id.in_(pipeline_ids))

        if start_time:
            message_conditions.append(persistence_monitoring.MonitoringMessage.timestamp >= start_time)
            llm_conditions.append(persistence_monitoring.MonitoringLLMCall.timestamp >= start_time)
            session_conditions.append(persistence_monitoring.MonitoringSession.start_time >= start_time)

        if end_time:
            message_conditions.append(persistence_monitoring.MonitoringMessage.timestamp <= end_time)
            llm_conditions.append(persistence_monitoring.MonitoringLLMCall.timestamp <= end_time)
            session_conditions.append(persistence_monitoring.MonitoringSession.start_time <= end_time)

        # Total messages
        message_query = sqlalchemy.select(sqlalchemy.func.count(persistence_monitoring.MonitoringMessage.id))
        if message_conditions:
            message_query = message_query.where(sqlalchemy.and_(*message_conditions))

        total_messages_result = await self.ap.persistence_mgr.execute_async(message_query)
        total_messages = total_messages_result.scalar() or 0

        # Total LLM calls
        llm_query = sqlalchemy.select(sqlalchemy.func.count(persistence_monitoring.MonitoringLLMCall.id))
        if llm_conditions:
            llm_query = llm_query.where(sqlalchemy.and_(*llm_conditions))

        llm_calls_result = await self.ap.persistence_mgr.execute_async(llm_query)
        llm_calls = llm_calls_result.scalar() or 0

        # Success rate (based on messages)
        success_query = sqlalchemy.select(sqlalchemy.func.count(persistence_monitoring.MonitoringMessage.id)).where(
            persistence_monitoring.MonitoringMessage.status == 'success'
        )
        if message_conditions:
            success_query = success_query.where(sqlalchemy.and_(*message_conditions))

        success_result = await self.ap.persistence_mgr.execute_async(success_query)
        success_count = success_result.scalar() or 0
        success_rate = (success_count / total_messages * 100) if total_messages > 0 else 0

        # Active sessions
        active_session_query = sqlalchemy.select(
            sqlalchemy.func.count(persistence_monitoring.MonitoringSession.session_id)
        ).where(persistence_monitoring.MonitoringSession.is_active == True)
        if session_conditions:
            active_session_query = active_session_query.where(sqlalchemy.and_(*session_conditions))

        active_sessions_result = await self.ap.persistence_mgr.execute_async(active_session_query)
        active_sessions = active_sessions_result.scalar() or 0

        return {
            'total_messages': total_messages,
            'llm_calls': llm_calls,
            'success_rate': round(success_rate, 2),
            'active_sessions': active_sessions,
        }

    async def get_messages(
        self,
        bot_ids: list[str] | None = None,
        pipeline_ids: list[str] | None = None,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Get messages with filters"""
        conditions = []

        if bot_ids:
            conditions.append(persistence_monitoring.MonitoringMessage.bot_id.in_(bot_ids))
        if pipeline_ids:
            conditions.append(persistence_monitoring.MonitoringMessage.pipeline_id.in_(pipeline_ids))
        if start_time:
            conditions.append(persistence_monitoring.MonitoringMessage.timestamp >= start_time)
        if end_time:
            conditions.append(persistence_monitoring.MonitoringMessage.timestamp <= end_time)

        # Get total count
        count_query = sqlalchemy.select(sqlalchemy.func.count(persistence_monitoring.MonitoringMessage.id))
        if conditions:
            count_query = count_query.where(sqlalchemy.and_(*conditions))

        count_result = await self.ap.persistence_mgr.execute_async(count_query)
        total = count_result.scalar() or 0

        # Get messages
        query = sqlalchemy.select(persistence_monitoring.MonitoringMessage).order_by(
            persistence_monitoring.MonitoringMessage.timestamp.desc()
        )
        if conditions:
            query = query.where(sqlalchemy.and_(*conditions))

        query = query.limit(limit).offset(offset)

        result = await self.ap.persistence_mgr.execute_async(query)
        messages_rows = result.all()

        serialized = []
        for row in messages_rows:
            # Extract model instance from Row (SQLAlchemy returns Row objects)
            msg = row[0] if isinstance(row, tuple) else row
            serialized_msg = self.ap.persistence_mgr.serialize_model(persistence_monitoring.MonitoringMessage, msg)
            serialized.append(serialized_msg)

        return (serialized, total)

    async def get_llm_calls(
        self,
        bot_ids: list[str] | None = None,
        pipeline_ids: list[str] | None = None,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Get LLM calls with filters"""
        conditions = []

        if bot_ids:
            conditions.append(persistence_monitoring.MonitoringLLMCall.bot_id.in_(bot_ids))
        if pipeline_ids:
            conditions.append(persistence_monitoring.MonitoringLLMCall.pipeline_id.in_(pipeline_ids))
        if start_time:
            conditions.append(persistence_monitoring.MonitoringLLMCall.timestamp >= start_time)
        if end_time:
            conditions.append(persistence_monitoring.MonitoringLLMCall.timestamp <= end_time)

        # Get total count
        count_query = sqlalchemy.select(sqlalchemy.func.count(persistence_monitoring.MonitoringLLMCall.id))
        if conditions:
            count_query = count_query.where(sqlalchemy.and_(*conditions))

        count_result = await self.ap.persistence_mgr.execute_async(count_query)
        total = count_result.scalar() or 0

        # Get LLM calls
        query = sqlalchemy.select(persistence_monitoring.MonitoringLLMCall).order_by(
            persistence_monitoring.MonitoringLLMCall.timestamp.desc()
        )
        if conditions:
            query = query.where(sqlalchemy.and_(*conditions))

        query = query.limit(limit).offset(offset)

        result = await self.ap.persistence_mgr.execute_async(query)
        llm_calls_rows = result.all()

        return (
            [self.ap.persistence_mgr.serialize_model(persistence_monitoring.MonitoringLLMCall, row[0] if isinstance(row, tuple) else row) for row in llm_calls_rows],
            total,
        )

    async def get_sessions(
        self,
        bot_ids: list[str] | None = None,
        pipeline_ids: list[str] | None = None,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        is_active: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Get sessions with filters"""
        conditions = []

        if bot_ids:
            conditions.append(persistence_monitoring.MonitoringSession.bot_id.in_(bot_ids))
        if pipeline_ids:
            conditions.append(persistence_monitoring.MonitoringSession.pipeline_id.in_(pipeline_ids))
        if start_time:
            conditions.append(persistence_monitoring.MonitoringSession.start_time >= start_time)
        if end_time:
            conditions.append(persistence_monitoring.MonitoringSession.start_time <= end_time)
        if is_active is not None:
            conditions.append(persistence_monitoring.MonitoringSession.is_active == is_active)

        # Get total count
        count_query = sqlalchemy.select(sqlalchemy.func.count(persistence_monitoring.MonitoringSession.session_id))
        if conditions:
            count_query = count_query.where(sqlalchemy.and_(*conditions))

        count_result = await self.ap.persistence_mgr.execute_async(count_query)
        total = count_result.scalar() or 0

        # Get sessions
        query = sqlalchemy.select(persistence_monitoring.MonitoringSession).order_by(
            persistence_monitoring.MonitoringSession.last_activity.desc()
        )
        if conditions:
            query = query.where(sqlalchemy.and_(*conditions))

        query = query.limit(limit).offset(offset)

        result = await self.ap.persistence_mgr.execute_async(query)
        sessions_rows = result.all()

        return (
            [self.ap.persistence_mgr.serialize_model(persistence_monitoring.MonitoringSession, row[0] if isinstance(row, tuple) else row) for row in sessions_rows],
            total,
        )

    async def get_errors(
        self,
        bot_ids: list[str] | None = None,
        pipeline_ids: list[str] | None = None,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Get errors with filters"""
        conditions = []

        if bot_ids:
            conditions.append(persistence_monitoring.MonitoringError.bot_id.in_(bot_ids))
        if pipeline_ids:
            conditions.append(persistence_monitoring.MonitoringError.pipeline_id.in_(pipeline_ids))
        if start_time:
            conditions.append(persistence_monitoring.MonitoringError.timestamp >= start_time)
        if end_time:
            conditions.append(persistence_monitoring.MonitoringError.timestamp <= end_time)

        # Get total count
        count_query = sqlalchemy.select(sqlalchemy.func.count(persistence_monitoring.MonitoringError.id))
        if conditions:
            count_query = count_query.where(sqlalchemy.and_(*conditions))

        count_result = await self.ap.persistence_mgr.execute_async(count_query)
        total = count_result.scalar() or 0

        # Get errors
        query = sqlalchemy.select(persistence_monitoring.MonitoringError).order_by(
            persistence_monitoring.MonitoringError.timestamp.desc()
        )
        if conditions:
            query = query.where(sqlalchemy.and_(*conditions))

        query = query.limit(limit).offset(offset)

        result = await self.ap.persistence_mgr.execute_async(query)
        errors_rows = result.all()

        return (
            [self.ap.persistence_mgr.serialize_model(persistence_monitoring.MonitoringError, row[0] if isinstance(row, tuple) else row) for row in errors_rows],
            total,
        )
