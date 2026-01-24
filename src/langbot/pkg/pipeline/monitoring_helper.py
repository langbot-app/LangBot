"""
Monitoring helper for recording events during pipeline execution.
This module provides convenient methods to record monitoring data
without cluttering the main pipeline code.
"""

from __future__ import annotations

import traceback
import typing
import time
import json

if typing.TYPE_CHECKING:
    from ..core import app
    import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


class MonitoringHelper:
    """Helper class for monitoring operations"""

    @staticmethod
    async def record_query_start(
        ap: app.Application,
        query: pipeline_query.Query,
        bot_id: str,
        bot_name: str,
        pipeline_id: str,
        pipeline_name: str,
        runner_name: str | None = None,
    ) -> str:
        """Record the start of query processing, returns message_id"""
        try:
            # Check if session exists, if not, record session start
            session_id = f'{query.launcher_type}_{query.launcher_id}'

            # Try to record message
            # Use JSON serialization to preserve message chain structure (including image URLs, etc.)
            if hasattr(query, 'message_chain') and hasattr(query.message_chain, 'model_dump'):
                message_content = json.dumps(query.message_chain.model_dump(), ensure_ascii=False)
            else:
                message_content = str(query)

            # Variables will be updated in record_query_success after preproc stage sets them
            # Here we just record None, the full variables will be set when query completes

            message_id = await ap.monitoring_service.record_message(
                bot_id=bot_id,
                bot_name=bot_name,
                pipeline_id=pipeline_id,
                pipeline_name=pipeline_name,
                message_content=message_content,
                session_id=session_id,
                status='pending',
                level='info',
                platform=query.launcher_type.value
                if hasattr(query.launcher_type, 'value')
                else str(query.launcher_type),
                user_id=query.sender_id,
                runner_name=runner_name,
                variables=None,  # Will be updated in record_query_success
            )

            # Update session activity or create new session if it doesn't exist
            # Always pass pipeline info to handle pipeline switches
            session_updated = await ap.monitoring_service.update_session_activity(
                session_id,
                pipeline_id=pipeline_id,
                pipeline_name=pipeline_name,
            )
            if not session_updated:
                # Session doesn't exist, create it
                await ap.monitoring_service.record_session_start(
                    session_id=session_id,
                    bot_id=bot_id,
                    bot_name=bot_name,
                    pipeline_id=pipeline_id,
                    pipeline_name=pipeline_name,
                    platform=query.launcher_type.value
                    if hasattr(query.launcher_type, 'value')
                    else str(query.launcher_type),
                    user_id=query.sender_id,
                )

            return message_id
        except Exception as e:
            ap.logger.error(f'Failed to record query start: {e}')
            return ''

    @staticmethod
    async def record_query_success(
        ap: app.Application,
        message_id: str,
        query: pipeline_query.Query | None = None,
    ):
        """Record successful query processing by updating message status and variables"""
        try:
            if message_id:
                # Serialize query.variables (filtering out internal variables)
                query_variables_str = None
                if query and hasattr(query, 'variables') and query.variables:
                    filtered_vars = {k: v for k, v in query.variables.items() if not k.startswith('_')}
                    if filtered_vars:
                        try:
                            query_variables_str = json.dumps(filtered_vars, ensure_ascii=False, default=str)
                        except Exception:
                            pass

                await ap.monitoring_service.update_message_status(
                    message_id=message_id,
                    status='success',
                    variables=query_variables_str,
                )
        except Exception as e:
            ap.logger.error(f'Failed to record query success: {e}')

    @staticmethod
    async def record_query_error(
        ap: app.Application,
        query: pipeline_query.Query,
        bot_id: str,
        bot_name: str,
        pipeline_id: str,
        pipeline_name: str,
        error: Exception,
        runner_name: str | None = None,
    ) -> str:
        """Record query processing error, returns message_id"""
        try:
            session_id = f'{query.launcher_type}_{query.launcher_id}'

            # Record error message
            message_id = await ap.monitoring_service.record_message(
                bot_id=bot_id,
                bot_name=bot_name,
                pipeline_id=pipeline_id,
                pipeline_name=pipeline_name,
                message_content=f'Error: {str(error)}',
                session_id=session_id,
                status='error',
                level='error',
                platform=query.launcher_type.value
                if hasattr(query.launcher_type, 'value')
                else str(query.launcher_type),
                user_id=query.sender_id,
                runner_name=runner_name,
            )

            # Record error log
            await ap.monitoring_service.record_error(
                bot_id=bot_id,
                bot_name=bot_name,
                pipeline_id=pipeline_id,
                pipeline_name=pipeline_name,
                error_type=type(error).__name__,
                error_message=str(error),
                session_id=session_id,
                stack_trace=traceback.format_exc(),
                message_id=message_id,
            )

            return message_id
        except Exception as e:
            ap.logger.error(f'Failed to record query error: {e}')
            return ''

    @staticmethod
    async def record_llm_call(
        ap: app.Application,
        query: pipeline_query.Query,
        bot_id: str,
        bot_name: str,
        pipeline_id: str,
        pipeline_name: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int,
        status: str = 'success',
        cost: float | None = None,
        error_message: str | None = None,
        message_id: str | None = None,
    ):
        """Record LLM call"""
        try:
            session_id = f'{query.launcher_type}_{query.launcher_id}'

            await ap.monitoring_service.record_llm_call(
                bot_id=bot_id,
                bot_name=bot_name,
                pipeline_id=pipeline_id,
                pipeline_name=pipeline_name,
                session_id=session_id,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration=duration_ms,
                status=status,
                cost=cost,
                error_message=error_message,
                message_id=message_id,
            )
        except Exception as e:
            ap.logger.error(f'Failed to record LLM call: {e}')


class LLMCallMonitor:
    """Context manager for monitoring LLM calls"""

    def __init__(
        self,
        ap: app.Application,
        query: pipeline_query.Query,
        bot_id: str,
        bot_name: str,
        pipeline_id: str,
        pipeline_name: str,
        model_name: str,
    ):
        self.ap = ap
        self.query = query
        self.bot_id = bot_id
        self.bot_name = bot_name
        self.pipeline_id = pipeline_id
        self.pipeline_name = pipeline_name
        self.model_name = model_name
        self.start_time = None
        self.input_tokens = 0
        self.output_tokens = 0

    async def __aenter__(self):
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.time() - self.start_time) * 1000)

        if exc_type is not None:
            # Error occurred
            await MonitoringHelper.record_llm_call(
                ap=self.ap,
                query=self.query,
                bot_id=self.bot_id,
                bot_name=self.bot_name,
                pipeline_id=self.pipeline_id,
                pipeline_name=self.pipeline_name,
                model_name=self.model_name,
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
                duration_ms=duration_ms,
                status='error',
                error_message=str(exc_val) if exc_val else None,
            )
        else:
            # Success
            await MonitoringHelper.record_llm_call(
                ap=self.ap,
                query=self.query,
                bot_id=self.bot_id,
                bot_name=self.bot_name,
                pipeline_id=self.pipeline_id,
                pipeline_name=self.pipeline_name,
                model_name=self.model_name,
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
                duration_ms=duration_ms,
                status='success',
            )

        return False  # Don't suppress exceptions
