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
        role: str = 'user',
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
            'role': role,
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
        session_ids: list[str] | None = None,
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
        if session_ids:
            conditions.append(persistence_monitoring.MonitoringMessage.session_id.in_(session_ids))
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

    # ========== Export Methods ==========

    def _escape_csv_field(self, field: str | None) -> str:
        """Escape a field for CSV output"""
        if field is None:
            return ''
        # Replace common escape sequences
        field = field.replace('\r\n', '\n').replace('\r', '\n')
        # If field contains comma, double quote, or newline, wrap in quotes
        if ',' in field or '"' in field or '\n' in field:
            # Escape double quotes by doubling them
            field = '"' + field.replace('"', '""') + '"'
        return field

    def _format_timestamp(self, dt: datetime.datetime) -> str:
        """Format datetime to ISO format string"""
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    def _extract_message_text(self, message_content: str) -> str:
        """Extract plain text from message chain JSON"""
        if not message_content:
            return ''

        try:
            import json

            message_chain = json.loads(message_content)
            if not isinstance(message_chain, list):
                return message_content

            text_parts = []
            for component in message_chain:
                if not isinstance(component, dict):
                    continue
                component_type = component.get('type')
                if component_type == 'Plain':
                    text = component.get('text', '')
                    text_parts.append(text)
                elif component_type == 'At':
                    display = component.get('display', '')
                    target = component.get('target', '')
                    if display:
                        text_parts.append(f'@{display}')
                    elif target:
                        text_parts.append(f'@{target}')
                elif component_type == 'AtAll':
                    text_parts.append('@All')
                elif component_type == 'Image':
                    text_parts.append('[Image]')
                elif component_type == 'File':
                    name = component.get('name', 'File')
                    text_parts.append(f'[File: {name}]')
                elif component_type == 'Voice':
                    length = component.get('length', 0)
                    text_parts.append(f'[Voice {length}s]')
                elif component_type == 'Quote':
                    # Quote content is in 'origin' field
                    origin = component.get('origin', [])
                    if isinstance(origin, list):
                        for item in origin:
                            if isinstance(item, dict) and item.get('type') == 'Plain':
                                text_parts.append(f'> {item.get("text", "")}')
                elif component_type == 'Source':
                    # Skip Source component
                    continue
                else:
                    # Other unknown types
                    text_parts.append(f'[{component_type}]')

            return ''.join(text_parts)
        except (json.JSONDecodeError, TypeError, KeyError):
            # If not valid JSON, return as-is
            return message_content

    async def export_messages(
        self,
        bot_ids: list[str] | None = None,
        pipeline_ids: list[str] | None = None,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        limit: int = 100000,
    ) -> list[dict]:
        """Export messages as list of dictionaries for CSV conversion"""
        conditions = []

        if bot_ids:
            conditions.append(persistence_monitoring.MonitoringMessage.bot_id.in_(bot_ids))
        if pipeline_ids:
            conditions.append(persistence_monitoring.MonitoringMessage.pipeline_id.in_(pipeline_ids))
        if start_time:
            conditions.append(persistence_monitoring.MonitoringMessage.timestamp >= start_time)
        if end_time:
            conditions.append(persistence_monitoring.MonitoringMessage.timestamp <= end_time)

        query = sqlalchemy.select(persistence_monitoring.MonitoringMessage).order_by(
            persistence_monitoring.MonitoringMessage.timestamp.desc()
        )
        if conditions:
            query = query.where(sqlalchemy.and_(*conditions))

        query = query.limit(limit)

        result = await self.ap.persistence_mgr.execute_async(query)
        rows = result.all()

        return [
            {
                'id': row[0].id if isinstance(row, tuple) else row.id,
                'timestamp': self._format_timestamp(row[0].timestamp if isinstance(row, tuple) else row.timestamp),
                'bot_id': row[0].bot_id if isinstance(row, tuple) else row.bot_id,
                'bot_name': row[0].bot_name if isinstance(row, tuple) else row.bot_name,
                'pipeline_id': row[0].pipeline_id if isinstance(row, tuple) else row.pipeline_id,
                'pipeline_name': row[0].pipeline_name if isinstance(row, tuple) else row.pipeline_name,
                'runner_name': row[0].runner_name if isinstance(row, tuple) else row.runner_name,
                'message_content': row[0].message_content if isinstance(row, tuple) else row.message_content,
                'message_text': self._extract_message_text(
                    row[0].message_content if isinstance(row, tuple) else row.message_content
                ),
                'session_id': row[0].session_id if isinstance(row, tuple) else row.session_id,
                'status': row[0].status if isinstance(row, tuple) else row.status,
                'level': row[0].level if isinstance(row, tuple) else row.level,
                'platform': row[0].platform if isinstance(row, tuple) else row.platform,
                'user_id': row[0].user_id if isinstance(row, tuple) else row.user_id,
            }
            for row in rows
        ]

    async def export_llm_calls(
        self,
        bot_ids: list[str] | None = None,
        pipeline_ids: list[str] | None = None,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        limit: int = 100000,
    ) -> list[dict]:
        """Export LLM calls as list of dictionaries for CSV conversion"""
        conditions = []

        if bot_ids:
            conditions.append(persistence_monitoring.MonitoringLLMCall.bot_id.in_(bot_ids))
        if pipeline_ids:
            conditions.append(persistence_monitoring.MonitoringLLMCall.pipeline_id.in_(pipeline_ids))
        if start_time:
            conditions.append(persistence_monitoring.MonitoringLLMCall.timestamp >= start_time)
        if end_time:
            conditions.append(persistence_monitoring.MonitoringLLMCall.timestamp <= end_time)

        query = sqlalchemy.select(persistence_monitoring.MonitoringLLMCall).order_by(
            persistence_monitoring.MonitoringLLMCall.timestamp.desc()
        )
        if conditions:
            query = query.where(sqlalchemy.and_(*conditions))

        query = query.limit(limit)

        result = await self.ap.persistence_mgr.execute_async(query)
        rows = result.all()

        return [
            {
                'id': row[0].id if isinstance(row, tuple) else row.id,
                'timestamp': self._format_timestamp(row[0].timestamp if isinstance(row, tuple) else row.timestamp),
                'model_name': row[0].model_name if isinstance(row, tuple) else row.model_name,
                'input_tokens': row[0].input_tokens if isinstance(row, tuple) else row.input_tokens,
                'output_tokens': row[0].output_tokens if isinstance(row, tuple) else row.output_tokens,
                'total_tokens': row[0].total_tokens if isinstance(row, tuple) else row.total_tokens,
                'duration_ms': row[0].duration if isinstance(row, tuple) else row.duration,
                'cost': row[0].cost if isinstance(row, tuple) else row.cost,
                'status': row[0].status if isinstance(row, tuple) else row.status,
                'bot_id': row[0].bot_id if isinstance(row, tuple) else row.bot_id,
                'bot_name': row[0].bot_name if isinstance(row, tuple) else row.bot_name,
                'pipeline_id': row[0].pipeline_id if isinstance(row, tuple) else row.pipeline_id,
                'pipeline_name': row[0].pipeline_name if isinstance(row, tuple) else row.pipeline_name,
                'session_id': row[0].session_id if isinstance(row, tuple) else row.session_id,
                'message_id': row[0].message_id if isinstance(row, tuple) else row.message_id,
                'error_message': row[0].error_message if isinstance(row, tuple) else row.error_message,
            }
            for row in rows
        ]

    async def export_embedding_calls(
        self,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        knowledge_base_id: str | None = None,
        limit: int = 100000,
    ) -> list[dict]:
        """Export embedding calls as list of dictionaries for CSV conversion"""
        conditions = []

        if start_time:
            conditions.append(persistence_monitoring.MonitoringEmbeddingCall.timestamp >= start_time)
        if end_time:
            conditions.append(persistence_monitoring.MonitoringEmbeddingCall.timestamp <= end_time)
        if knowledge_base_id:
            conditions.append(persistence_monitoring.MonitoringEmbeddingCall.knowledge_base_id == knowledge_base_id)

        query = sqlalchemy.select(persistence_monitoring.MonitoringEmbeddingCall).order_by(
            persistence_monitoring.MonitoringEmbeddingCall.timestamp.desc()
        )
        if conditions:
            query = query.where(sqlalchemy.and_(*conditions))

        query = query.limit(limit)

        result = await self.ap.persistence_mgr.execute_async(query)
        rows = result.all()

        return [
            {
                'id': row[0].id if isinstance(row, tuple) else row.id,
                'timestamp': self._format_timestamp(row[0].timestamp if isinstance(row, tuple) else row.timestamp),
                'model_name': row[0].model_name if isinstance(row, tuple) else row.model_name,
                'prompt_tokens': row[0].prompt_tokens if isinstance(row, tuple) else row.prompt_tokens,
                'total_tokens': row[0].total_tokens if isinstance(row, tuple) else row.total_tokens,
                'duration_ms': row[0].duration if isinstance(row, tuple) else row.duration,
                'input_count': row[0].input_count if isinstance(row, tuple) else row.input_count,
                'status': row[0].status if isinstance(row, tuple) else row.status,
                'error_message': row[0].error_message if isinstance(row, tuple) else row.error_message,
                'knowledge_base_id': row[0].knowledge_base_id if isinstance(row, tuple) else row.knowledge_base_id,
                'query_text': row[0].query_text if isinstance(row, tuple) else row.query_text,
                'session_id': row[0].session_id if isinstance(row, tuple) else row.session_id,
                'message_id': row[0].message_id if isinstance(row, tuple) else row.message_id,
                'call_type': row[0].call_type if isinstance(row, tuple) else row.call_type,
            }
            for row in rows
        ]

    async def export_errors(
        self,
        bot_ids: list[str] | None = None,
        pipeline_ids: list[str] | None = None,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        limit: int = 100000,
    ) -> list[dict]:
        """Export errors as list of dictionaries for CSV conversion"""
        conditions = []

        if bot_ids:
            conditions.append(persistence_monitoring.MonitoringError.bot_id.in_(bot_ids))
        if pipeline_ids:
            conditions.append(persistence_monitoring.MonitoringError.pipeline_id.in_(pipeline_ids))
        if start_time:
            conditions.append(persistence_monitoring.MonitoringError.timestamp >= start_time)
        if end_time:
            conditions.append(persistence_monitoring.MonitoringError.timestamp <= end_time)

        query = sqlalchemy.select(persistence_monitoring.MonitoringError).order_by(
            persistence_monitoring.MonitoringError.timestamp.desc()
        )
        if conditions:
            query = query.where(sqlalchemy.and_(*conditions))

        query = query.limit(limit)

        result = await self.ap.persistence_mgr.execute_async(query)
        rows = result.all()

        return [
            {
                'id': row[0].id if isinstance(row, tuple) else row.id,
                'timestamp': self._format_timestamp(row[0].timestamp if isinstance(row, tuple) else row.timestamp),
                'error_type': row[0].error_type if isinstance(row, tuple) else row.error_type,
                'error_message': row[0].error_message if isinstance(row, tuple) else row.error_message,
                'bot_id': row[0].bot_id if isinstance(row, tuple) else row.bot_id,
                'bot_name': row[0].bot_name if isinstance(row, tuple) else row.bot_name,
                'pipeline_id': row[0].pipeline_id if isinstance(row, tuple) else row.pipeline_id,
                'pipeline_name': row[0].pipeline_name if isinstance(row, tuple) else row.pipeline_name,
                'session_id': row[0].session_id if isinstance(row, tuple) else row.session_id,
                'message_id': row[0].message_id if isinstance(row, tuple) else row.message_id,
                'stack_trace': row[0].stack_trace if isinstance(row, tuple) else row.stack_trace,
            }
            for row in rows
        ]

    async def export_sessions(
        self,
        bot_ids: list[str] | None = None,
        pipeline_ids: list[str] | None = None,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        limit: int = 100000,
    ) -> list[dict]:
        """Export sessions as list of dictionaries for CSV conversion"""
        conditions = []

        if bot_ids:
            conditions.append(persistence_monitoring.MonitoringSession.bot_id.in_(bot_ids))
        if pipeline_ids:
            conditions.append(persistence_monitoring.MonitoringSession.pipeline_id.in_(pipeline_ids))
        if start_time:
            conditions.append(persistence_monitoring.MonitoringSession.start_time >= start_time)
        if end_time:
            conditions.append(persistence_monitoring.MonitoringSession.start_time <= end_time)

        query = sqlalchemy.select(persistence_monitoring.MonitoringSession).order_by(
            persistence_monitoring.MonitoringSession.last_activity.desc()
        )
        if conditions:
            query = query.where(sqlalchemy.and_(*conditions))

        query = query.limit(limit)

        result = await self.ap.persistence_mgr.execute_async(query)
        rows = result.all()

        return [
            {
                'session_id': row[0].session_id if isinstance(row, tuple) else row.session_id,
                'bot_id': row[0].bot_id if isinstance(row, tuple) else row.bot_id,
                'bot_name': row[0].bot_name if isinstance(row, tuple) else row.bot_name,
                'pipeline_id': row[0].pipeline_id if isinstance(row, tuple) else row.pipeline_id,
                'pipeline_name': row[0].pipeline_name if isinstance(row, tuple) else row.pipeline_name,
                'message_count': row[0].message_count if isinstance(row, tuple) else row.message_count,
                'start_time': self._format_timestamp(row[0].start_time if isinstance(row, tuple) else row.start_time),
                'last_activity': self._format_timestamp(
                    row[0].last_activity if isinstance(row, tuple) else row.last_activity
                ),
                'is_active': str(row[0].is_active if isinstance(row, tuple) else row.is_active),
                'platform': row[0].platform if isinstance(row, tuple) else row.platform,
                'user_id': row[0].user_id if isinstance(row, tuple) else row.user_id,
            }
            for row in rows
        ]
