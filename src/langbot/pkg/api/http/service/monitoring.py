from __future__ import annotations

import uuid
import datetime
import sqlalchemy

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
        runner_name: str | None = None,
        variables: str | None = None,
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
            'runner_name': runner_name,
            'variables': variables,
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
        message_id: str | None = None,
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
            'message_id': message_id,
        }

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_monitoring.MonitoringLLMCall).values(call_data)
        )

        return call_id

    async def record_embedding_call(
        self,
        model_name: str,
        prompt_tokens: int,
        total_tokens: int,
        duration: int,
        input_count: int,
        status: str = 'success',
        error_message: str | None = None,
        knowledge_base_id: str | None = None,
        query_text: str | None = None,
        session_id: str | None = None,
        message_id: str | None = None,
        call_type: str | None = None,
    ) -> str:
        """Record an embedding call"""
        call_id = str(uuid.uuid4())
        call_data = {
            'id': call_id,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
            'model_name': model_name,
            'prompt_tokens': prompt_tokens,
            'total_tokens': total_tokens,
            'duration': duration,
            'input_count': input_count,
            'status': status,
            'error_message': error_message,
            'knowledge_base_id': knowledge_base_id,
            'query_text': query_text,
            'session_id': session_id,
            'message_id': message_id,
            'call_type': call_type,
        }

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_monitoring.MonitoringEmbeddingCall).values(call_data)
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

    async def update_session_activity(
        self,
        session_id: str,
        pipeline_id: str | None = None,
        pipeline_name: str | None = None,
    ) -> bool:
        """Update session last activity time and increment message count.

        Also updates pipeline info if the bot's pipeline has changed.

        Returns:
            True if session was found and updated, False if session doesn't exist.
        """
        update_values = {
            'last_activity': datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
            'message_count': persistence_monitoring.MonitoringSession.message_count + 1,
        }

        # Update pipeline info if provided (handles pipeline switch)
        if pipeline_id is not None:
            update_values['pipeline_id'] = pipeline_id
        if pipeline_name is not None:
            update_values['pipeline_name'] = pipeline_name

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_monitoring.MonitoringSession)
            .where(persistence_monitoring.MonitoringSession.session_id == session_id)
            .values(update_values)
        )
        # Check if any rows were updated
        return result.rowcount > 0

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
        message_id: str | None = None,
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
            'message_id': message_id,
        }

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_monitoring.MonitoringError).values(error_data)
        )

        return error_id

    async def update_message_status(
        self,
        message_id: str,
        status: str,
        level: str | None = None,
        variables: str | None = None,
    ) -> None:
        """Update message status and optionally variables"""
        update_values = {'status': status}
        if level is not None:
            update_values['level'] = level
        if variables is not None:
            update_values['variables'] = variables

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_monitoring.MonitoringMessage)
            .where(persistence_monitoring.MonitoringMessage.id == message_id)
            .values(update_values)
        )

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
        embedding_conditions = []
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
            embedding_conditions.append(persistence_monitoring.MonitoringEmbeddingCall.timestamp >= start_time)
            session_conditions.append(persistence_monitoring.MonitoringSession.start_time >= start_time)

        if end_time:
            message_conditions.append(persistence_monitoring.MonitoringMessage.timestamp <= end_time)
            llm_conditions.append(persistence_monitoring.MonitoringLLMCall.timestamp <= end_time)
            embedding_conditions.append(persistence_monitoring.MonitoringEmbeddingCall.timestamp <= end_time)
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

        # Total Embedding calls
        embedding_query = sqlalchemy.select(sqlalchemy.func.count(persistence_monitoring.MonitoringEmbeddingCall.id))
        if embedding_conditions:
            embedding_query = embedding_query.where(sqlalchemy.and_(*embedding_conditions))

        embedding_calls_result = await self.ap.persistence_mgr.execute_async(embedding_query)
        embedding_calls = embedding_calls_result.scalar() or 0

        # Total model calls (LLM + Embedding)
        model_calls = llm_calls + embedding_calls

        # Success rate (based on messages)
        success_query = sqlalchemy.select(sqlalchemy.func.count(persistence_monitoring.MonitoringMessage.id)).where(
            persistence_monitoring.MonitoringMessage.status == 'success'
        )
        if message_conditions:
            success_query = success_query.where(sqlalchemy.and_(*message_conditions))

        success_result = await self.ap.persistence_mgr.execute_async(success_query)
        success_count = success_result.scalar() or 0
        success_rate = (success_count / total_messages * 100) if total_messages > 0 else 100

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
            'embedding_calls': embedding_calls,
            'model_calls': model_calls,
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
            [
                self.ap.persistence_mgr.serialize_model(
                    persistence_monitoring.MonitoringLLMCall, row[0] if isinstance(row, tuple) else row
                )
                for row in llm_calls_rows
            ],
            total,
        )

    async def get_embedding_calls(
        self,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        knowledge_base_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Get embedding calls with filters"""
        conditions = []

        if start_time:
            conditions.append(persistence_monitoring.MonitoringEmbeddingCall.timestamp >= start_time)
        if end_time:
            conditions.append(persistence_monitoring.MonitoringEmbeddingCall.timestamp <= end_time)
        if knowledge_base_id:
            conditions.append(persistence_monitoring.MonitoringEmbeddingCall.knowledge_base_id == knowledge_base_id)

        # Get total count
        count_query = sqlalchemy.select(sqlalchemy.func.count(persistence_monitoring.MonitoringEmbeddingCall.id))
        if conditions:
            count_query = count_query.where(sqlalchemy.and_(*conditions))

        count_result = await self.ap.persistence_mgr.execute_async(count_query)
        total = count_result.scalar() or 0

        # Get embedding calls
        query = sqlalchemy.select(persistence_monitoring.MonitoringEmbeddingCall).order_by(
            persistence_monitoring.MonitoringEmbeddingCall.timestamp.desc()
        )
        if conditions:
            query = query.where(sqlalchemy.and_(*conditions))

        query = query.limit(limit).offset(offset)

        result = await self.ap.persistence_mgr.execute_async(query)
        embedding_calls_rows = result.all()

        return (
            [
                self.ap.persistence_mgr.serialize_model(
                    persistence_monitoring.MonitoringEmbeddingCall, row[0] if isinstance(row, tuple) else row
                )
                for row in embedding_calls_rows
            ],
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
            [
                self.ap.persistence_mgr.serialize_model(
                    persistence_monitoring.MonitoringSession, row[0] if isinstance(row, tuple) else row
                )
                for row in sessions_rows
            ],
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
            [
                self.ap.persistence_mgr.serialize_model(
                    persistence_monitoring.MonitoringError, row[0] if isinstance(row, tuple) else row
                )
                for row in errors_rows
            ],
            total,
        )

    async def get_session_analysis(
        self,
        session_id: str,
    ) -> dict:
        """Get detailed analysis for a specific session"""
        # Get session info
        session_query = sqlalchemy.select(persistence_monitoring.MonitoringSession).where(
            persistence_monitoring.MonitoringSession.session_id == session_id
        )
        session_result = await self.ap.persistence_mgr.execute_async(session_query)
        session_row = session_result.first()

        if not session_row:
            return {
                'session_id': session_id,
                'found': False,
            }

        session = session_row[0] if isinstance(session_row, tuple) else session_row

        # Get messages for this session
        messages_query = (
            sqlalchemy.select(persistence_monitoring.MonitoringMessage)
            .where(persistence_monitoring.MonitoringMessage.session_id == session_id)
            .order_by(persistence_monitoring.MonitoringMessage.timestamp.asc())
        )
        messages_result = await self.ap.persistence_mgr.execute_async(messages_query)
        messages_rows = messages_result.all()

        # Count messages by status
        success_messages = 0
        error_messages = 0
        pending_messages = 0
        for row in messages_rows:
            msg = row[0] if isinstance(row, tuple) else row
            if msg.status == 'success':
                success_messages += 1
            elif msg.status == 'error':
                error_messages += 1
            elif msg.status == 'pending':
                pending_messages += 1

        # Get LLM calls for this session
        llm_query = sqlalchemy.select(persistence_monitoring.MonitoringLLMCall).where(
            persistence_monitoring.MonitoringLLMCall.session_id == session_id
        )
        llm_result = await self.ap.persistence_mgr.execute_async(llm_query)
        llm_rows = llm_result.all()

        # Calculate LLM statistics
        total_llm_calls = len(llm_rows)
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0
        total_duration = 0
        success_llm_calls = 0
        error_llm_calls = 0

        for row in llm_rows:
            llm_call = row[0] if isinstance(row, tuple) else row
            total_input_tokens += llm_call.input_tokens
            total_output_tokens += llm_call.output_tokens
            total_tokens += llm_call.total_tokens
            total_duration += llm_call.duration
            if llm_call.status == 'success':
                success_llm_calls += 1
            else:
                error_llm_calls += 1

        # Get errors for this session
        error_query = (
            sqlalchemy.select(persistence_monitoring.MonitoringError)
            .where(persistence_monitoring.MonitoringError.session_id == session_id)
            .order_by(persistence_monitoring.MonitoringError.timestamp.desc())
        )
        error_result = await self.ap.persistence_mgr.execute_async(error_query)
        error_rows = error_result.all()

        errors = [
            self.ap.persistence_mgr.serialize_model(
                persistence_monitoring.MonitoringError, row[0] if isinstance(row, tuple) else row
            )
            for row in error_rows
        ]

        # Calculate session duration
        if messages_rows:
            first_msg = messages_rows[0][0] if isinstance(messages_rows[0], tuple) else messages_rows[0]
            last_msg = messages_rows[-1][0] if isinstance(messages_rows[-1], tuple) else messages_rows[-1]
            session_duration_seconds = int((last_msg.timestamp - first_msg.timestamp).total_seconds())
        else:
            session_duration_seconds = 0

        return {
            'session_id': session_id,
            'found': True,
            'session': self.ap.persistence_mgr.serialize_model(persistence_monitoring.MonitoringSession, session),
            'message_stats': {
                'total': len(messages_rows),
                'success': success_messages,
                'error': error_messages,
                'pending': pending_messages,
            },
            'llm_stats': {
                'total_calls': total_llm_calls,
                'success_calls': success_llm_calls,
                'error_calls': error_llm_calls,
                'total_input_tokens': total_input_tokens,
                'total_output_tokens': total_output_tokens,
                'total_tokens': total_tokens,
                'average_duration_ms': int(total_duration / total_llm_calls) if total_llm_calls > 0 else 0,
            },
            'errors': errors,
            'session_duration_seconds': session_duration_seconds,
        }

    async def get_message_details(
        self,
        message_id: str,
    ) -> dict:
        """Get detailed information for a specific message including associated LLM calls and errors"""
        # Get message info
        message_query = sqlalchemy.select(persistence_monitoring.MonitoringMessage).where(
            persistence_monitoring.MonitoringMessage.id == message_id
        )
        message_result = await self.ap.persistence_mgr.execute_async(message_query)
        message_row = message_result.first()

        if not message_row:
            return {
                'message_id': message_id,
                'found': False,
            }

        message = message_row[0] if isinstance(message_row, tuple) else message_row

        # Get LLM calls for this message
        llm_query = (
            sqlalchemy.select(persistence_monitoring.MonitoringLLMCall)
            .where(persistence_monitoring.MonitoringLLMCall.message_id == message_id)
            .order_by(persistence_monitoring.MonitoringLLMCall.timestamp.asc())
        )
        llm_result = await self.ap.persistence_mgr.execute_async(llm_query)
        llm_rows = llm_result.all()

        llm_calls = [
            self.ap.persistence_mgr.serialize_model(
                persistence_monitoring.MonitoringLLMCall, row[0] if isinstance(row, tuple) else row
            )
            for row in llm_rows
        ]

        # Calculate LLM statistics
        total_input_tokens = sum(call.input_tokens for call in llm_rows)
        total_output_tokens = sum(call.output_tokens for call in llm_rows)
        total_tokens = sum(call.total_tokens for call in llm_rows)
        total_duration = sum(call.duration for call in llm_rows)

        # Get errors for this message
        error_query = (
            sqlalchemy.select(persistence_monitoring.MonitoringError)
            .where(persistence_monitoring.MonitoringError.message_id == message_id)
            .order_by(persistence_monitoring.MonitoringError.timestamp.asc())
        )
        error_result = await self.ap.persistence_mgr.execute_async(error_query)
        error_rows = error_result.all()

        errors = [
            self.ap.persistence_mgr.serialize_model(
                persistence_monitoring.MonitoringError, row[0] if isinstance(row, tuple) else row
            )
            for row in error_rows
        ]

        return {
            'message_id': message_id,
            'found': True,
            'message': self.ap.persistence_mgr.serialize_model(persistence_monitoring.MonitoringMessage, message),
            'llm_calls': llm_calls,
            'llm_stats': {
                'total_calls': len(llm_rows),
                'total_input_tokens': total_input_tokens,
                'total_output_tokens': total_output_tokens,
                'total_tokens': total_tokens,
                'total_duration_ms': total_duration,
                'average_duration_ms': int(total_duration / len(llm_rows)) if len(llm_rows) > 0 else 0,
            },
            'errors': errors,
        }
