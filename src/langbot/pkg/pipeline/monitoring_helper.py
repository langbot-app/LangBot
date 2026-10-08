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

from .pool import get_query_execution_context


async def resolve_processor_name(
    ap: app.Application,
    workspace_uuid: str,
    processor_type: str,
    processor_id: str | None,
    runner_id: str = '',
) -> str:
    """Display name of the processor kind that handled a run.

    Monitoring attributed every call to a Pipeline, so an Agent or a plugin event
    processor recorded "Unknown" for the entity that actually ran. Each kind is
    resolved from the table that owns it, falling back to the identity the
    binding carried.
    """
    import sqlalchemy

    from ..entity.persistence import agent as persistence_agent
    from ..entity.persistence import pipeline as persistence_pipeline

    identifier = str(processor_id or '').strip()
    if identifier:
        try:
            model = persistence_pipeline.LegacyPipeline if processor_type == 'pipeline' else persistence_agent.Agent
            result = await ap.persistence_mgr.execute_async(
                sqlalchemy.select(model.name).where(
                    sqlalchemy.and_(
                        model.uuid == identifier,
                        model.workspace_uuid == workspace_uuid,
                    )
                )
            )
            name = str(result.scalar() or '').strip()
            if name:
                return name
        except Exception as e:
            ap.logger.warning(f'Failed to resolve monitoring processor name: {e}')
    # A deleted Agent or an unregistered plugin processor still names the
    # component that ran, never a bare "Unknown".
    return identifier or runner_id or processor_type


async def prepare_monitoring_identity(
    ap: app.Application,
    query: pipeline_query.Query,
    *,
    processor_type: str,
    processor_id: str | None,
    runner_id: str = '',
    execution_record_id: str = '',
) -> None:
    """Pin the monitoring identity of a runner-owned execution.

    A Pipeline pins these variables when it starts a query; a Runner started by
    an Agent or a plugin event processor has to pin them itself, otherwise every
    LLM/tool call it makes is attributed to "Unknown". An enclosing Pipeline
    already named the run, so its label is never overwritten.

    ``_monitoring_message_id`` is the execution record the calls belong to: the
    Pipeline's message, or the Agent run's id. Both are the id the executions
    list shows, which is what lets a call jump back to its record.
    """
    try:
        variables = getattr(query, 'variables', None)
        if not isinstance(variables, dict):
            return
        if variables.get('_monitoring_pipeline_name'):
            return

        bot_name = 'WebChat'
        bot_uuid = str(getattr(query, 'bot_uuid', '') or '')
        workspace_uuid = str(getattr(query, 'workspace_uuid', '') or '')
        if bot_uuid and workspace_uuid:
            try:
                bot = await ap.bot_service.get_bot(
                    workspace_uuid,
                    bot_uuid,
                    include_secret=False,
                )
                if bot:
                    bot_name = bot.get('name', bot_name)
            except Exception as e:
                ap.logger.warning(f'Failed to resolve monitoring bot name: {e}')

        variables['_monitoring_bot_name'] = bot_name
        variables['_monitoring_pipeline_name'] = await resolve_processor_name(
            ap,
            workspace_uuid,
            processor_type,
            processor_id,
            runner_id,
        )
        if execution_record_id:
            variables['_monitoring_message_id'] = execution_record_id
    except Exception as e:
        ap.logger.error(f'Failed to prepare monitoring identity: {e}')


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
            session_id = f'{query.launcher_type.value if hasattr(query.launcher_type, "value") else query.launcher_type}_{query.launcher_id}'

            # Get sender name from message event
            sender_name = None
            if hasattr(query, 'message_event'):
                if hasattr(query.message_event, 'sender'):
                    if hasattr(query.message_event.sender, 'nickname'):
                        sender_name = query.message_event.sender.nickname
                    elif hasattr(query.message_event.sender, 'member_name'):
                        sender_name = query.message_event.sender.member_name

            # Try to record message
            # Use JSON serialization to preserve message chain structure (including image URLs, etc.)
            if hasattr(query, 'message_chain') and hasattr(query.message_chain, 'model_dump'):
                chain_dump = query.message_chain.model_dump()
                if hasattr(ap, 'storage_mgr') and hasattr(ap.storage_mgr, 'media_cache'):
                    chain_dump = await ap.storage_mgr.media_cache.externalize_chain_dump(chain_dump)
                message_content = json.dumps(chain_dump, ensure_ascii=False)
            else:
                message_content = str(query)

            # Variables will be updated in record_query_success after preproc stage sets them
            # Here we just record None, the full variables will be set when query completes

            message_id = await ap.monitoring_service.record_message(
                get_query_execution_context(query),
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
                user_name=sender_name,
                runner_name=runner_name,
                variables=None,  # Will be updated in record_query_success
            )

            # Update session activity or create new session if it doesn't exist
            # Always pass pipeline info to handle pipeline switches
            session_updated = await ap.monitoring_service.update_session_activity(
                get_query_execution_context(query),
                session_id,
                bot_id=bot_id,
                pipeline_id=pipeline_id,
                pipeline_name=pipeline_name,
            )
            if not session_updated:
                # Session doesn't exist, create it
                await ap.monitoring_service.record_session_start(
                    get_query_execution_context(query),
                    session_id=session_id,
                    bot_id=bot_id,
                    bot_name=bot_name,
                    pipeline_id=pipeline_id,
                    pipeline_name=pipeline_name,
                    platform=query.launcher_type.value
                    if hasattr(query.launcher_type, 'value')
                    else str(query.launcher_type),
                    user_id=query.sender_id,
                    user_name=sender_name,
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
                    get_query_execution_context(query),
                    message_id=message_id,
                    status='success',
                    variables=query_variables_str,
                )
        except Exception as e:
            ap.logger.error(f'Failed to record query success: {e}')

    @staticmethod
    async def record_query_response(
        ap: app.Application,
        query: pipeline_query.Query,
        bot_id: str,
        bot_name: str,
        pipeline_id: str,
        pipeline_name: str,
        runner_name: str | None = None,
    ):
        """Record bot response message to monitoring"""
        try:
            session_id = f'{query.launcher_type.value if hasattr(query.launcher_type, "value") else query.launcher_type}_{query.launcher_id}'

            # Get sender name from message event
            sender_name = None
            if hasattr(query, 'message_event'):
                if hasattr(query.message_event, 'sender'):
                    if hasattr(query.message_event.sender, 'nickname'):
                        sender_name = query.message_event.sender.nickname
                    elif hasattr(query.message_event.sender, 'member_name'):
                        sender_name = query.message_event.sender.member_name

            # Extract response content from resp_message_chain
            if hasattr(query, 'resp_message_chain') and query.resp_message_chain:
                # Serialize the last response message chain
                last_resp = query.resp_message_chain[-1]
                if hasattr(last_resp, 'model_dump'):
                    message_content = json.dumps(last_resp.model_dump(), ensure_ascii=False)
                else:
                    message_content = str(last_resp)
            elif hasattr(query, 'resp_messages') and query.resp_messages:
                last_resp = query.resp_messages[-1]
                if hasattr(last_resp, 'get_content_platform_message_chain'):
                    chain = last_resp.get_content_platform_message_chain()
                    if hasattr(chain, 'model_dump'):
                        chain_dump = chain.model_dump()
                        if hasattr(ap, 'storage_mgr') and hasattr(ap.storage_mgr, 'media_cache'):
                            chain_dump = await ap.storage_mgr.media_cache.externalize_chain_dump(chain_dump)
                        message_content = json.dumps(chain_dump, ensure_ascii=False)
                    else:
                        message_content = str(chain)
                else:
                    message_content = str(last_resp)
            else:
                return  # No response to record

            await ap.monitoring_service.record_message(
                get_query_execution_context(query),
                bot_id=bot_id,
                bot_name=bot_name,
                pipeline_id=pipeline_id,
                pipeline_name=pipeline_name,
                message_content=message_content,
                session_id=session_id,
                status='success',
                level='info',
                platform=query.launcher_type.value
                if hasattr(query.launcher_type, 'value')
                else str(query.launcher_type),
                user_id=query.sender_id,
                user_name=sender_name,
                runner_name=runner_name,
                role='assistant',
                parent_message_id=(query.variables or {}).get('_monitoring_message_id'),
            )
        except Exception as e:
            ap.logger.error(f'Failed to record query response: {e}')

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
            session_id = f'{query.launcher_type.value if hasattr(query.launcher_type, "value") else query.launcher_type}_{query.launcher_id}'

            # Get sender name from message event
            sender_name = None
            if hasattr(query, 'message_event'):
                if hasattr(query.message_event, 'sender'):
                    if hasattr(query.message_event.sender, 'nickname'):
                        sender_name = query.message_event.sender.nickname
                    elif hasattr(query.message_event.sender, 'member_name'):
                        sender_name = query.message_event.sender.member_name

            # Record error message
            message_id = await ap.monitoring_service.record_message(
                get_query_execution_context(query),
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
                user_name=sender_name,
                runner_name=runner_name,
            )

            # Record error log
            await ap.monitoring_service.record_error(
                get_query_execution_context(query),
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
            session_id = f'{query.launcher_type.value if hasattr(query.launcher_type, "value") else query.launcher_type}_{query.launcher_id}'

            await ap.monitoring_service.record_llm_call(
                get_query_execution_context(query),
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
