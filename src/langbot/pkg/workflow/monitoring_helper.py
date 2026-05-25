"""
Monitoring helper for recording events during workflow execution.
This module provides convenient methods to record monitoring data
without cluttering the main workflow code.

New logging scheme:
- Trigger log: adapter → workflow_name → local-workflow (with original message)
- LLM call log: adapter → workflow_name → local-workflow (with LLM info)
- LLM response log: adapter → workflow_name → local-workflow (with response message)
- Reply log: adapter → workflow_name → local-workflow (with reply content)
"""

from __future__ import annotations

import typing
import time
import json

if typing.TYPE_CHECKING:
    from ..core import app
    from langbot_plugin.api.entities.builtin.workflow.query import WorkflowQuery


class WorkflowMonitoringHelper:
    """Helper class for workflow monitoring operations"""

    @staticmethod
    def _get_adapter_name(query: WorkflowQuery) -> str:
        """Get adapter name from query"""
        if query.adapter and hasattr(query.adapter, 'name'):
            return query.adapter.name
        if query.adapter and hasattr(query.adapter, 'adapter_name'):
            return query.adapter.adapter_name
        return 'WebChat'

    @staticmethod
    def _get_session_id(query: WorkflowQuery) -> str:
        """Build session_id from launcher info"""
        launcher_type = query.launcher_type.value if query.launcher_type else 'unknown'
        launcher_id = query.launcher_id or 'unknown'
        return f'{launcher_type}_{launcher_id}'

    @staticmethod
    async def record_trigger_log(
        ap: app.Application,
        query: WorkflowQuery,
        workflow_id: str,
        workflow_name: str,
    ) -> str:
        """Record trigger node log
        
        Format: adapter → workflow_name → local-workflow
        Contains: original message content
        """
        try:
            adapter_name = WorkflowMonitoringHelper._get_adapter_name(query)
            session_id = WorkflowMonitoringHelper._get_session_id(query)
            
            # Get message content
            message_content = ''
            if query.message_context and hasattr(query.message_context, 'message_content'):
                message_content = query.message_context.message_content
            elif query.message_chain and hasattr(query.message_chain, 'model_dump'):
                message_content = json.dumps(query.message_chain.model_dump(), ensure_ascii=False)
            
            # Build pipeline_name: workflow_name/local-workflow
            pipeline_name = f'{workflow_name}/local-workflow' if workflow_name else 'local-workflow'
            
            # Build log message: adapter → workflow_name → local-workflow
            log_message = f'{adapter_name} → {workflow_name} → local-workflow'
            if message_content:
                log_message += f'\n{message_content}'
            
            message_id = await ap.monitoring_service.record_message(
                bot_id=query.bot_uuid or '',
                bot_name=workflow_name or 'Workflow',
                pipeline_id=workflow_id,
                pipeline_name=pipeline_name,
                message_content=log_message,
                session_id=session_id,
                status='success',
                level='info',
                platform='workflow',
                user_id=query.sender_id,
                user_name=query.sender_name,
                role='user',
            )
            
            return message_id
        except Exception as e:
            ap.logger.error(f'Failed to record trigger log: {e}')
            return ''

    @staticmethod
    async def record_llm_call_log(
        ap: app.Application,
        query: WorkflowQuery,
        workflow_id: str,
        workflow_name: str,
        node_name: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int,
        status: str = 'success',
        error_message: str | None = None,
    ):
        """Record LLM call log (with LLM info)
        
        Format: adapter → workflow_name → local-workflow
        Contains: LLM call statistics
        """
        try:
            adapter_name = WorkflowMonitoringHelper._get_adapter_name(query)
            session_id = WorkflowMonitoringHelper._get_session_id(query)
            
            # Build pipeline_name: workflow_name/local-workflow
            pipeline_name = f'{workflow_name}/local-workflow' if workflow_name else 'local-workflow'
            
            # Build log message with LLM info
            log_message = f'{adapter_name} → {workflow_name} → local-workflow\n'
            log_message += f'LLM Call: {node_name}\n'
            log_message += f'Model: {model_name}\n'
            log_message += f'Status: {status}\n'
            log_message += f'Duration: {duration_ms}ms\n'
            log_message += f'Input Tokens: {input_tokens}\n'
            log_message += f'Output Tokens: {output_tokens}\n'
            log_message += f'Total Tokens: {input_tokens + output_tokens}'
            
            if error_message:
                log_message += f'\nError: {error_message}'
            
            await ap.monitoring_service.record_llm_call(
                bot_id=query.bot_uuid or '',
                bot_name=workflow_name or 'Workflow',
                pipeline_id=workflow_id,
                pipeline_name=pipeline_name,
                session_id=session_id,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration=duration_ms,
                status=status,
                error_message=error_message,
            )
            
            # Also record as message for display
            await ap.monitoring_service.record_message(
                bot_id=query.bot_uuid or '',
                bot_name=workflow_name or 'Workflow',
                pipeline_id=workflow_id,
                pipeline_name=pipeline_name,
                message_content=log_message,
                session_id=session_id,
                status=status,
                level='info',
                platform='workflow',
                user_id=query.sender_id,
                user_name=query.sender_name,
                role='system',
            )
        except Exception as e:
            ap.logger.error(f'Failed to record LLM call log: {e}')

    @staticmethod
    async def record_llm_response_log(
        ap: app.Application,
        query: WorkflowQuery,
        workflow_id: str,
        workflow_name: str,
        node_name: str,
        response_content: str,
    ):
        """Record LLM response log (without LLM info, with response message)
        
        Format: adapter → workflow_name → local-workflow
        Contains: response message content
        """
        try:
            adapter_name = WorkflowMonitoringHelper._get_adapter_name(query)
            session_id = WorkflowMonitoringHelper._get_session_id(query)
            
            # Build pipeline_name: workflow_name/local-workflow
            pipeline_name = f'{workflow_name}/local-workflow' if workflow_name else 'local-workflow'
            
            # Build log message
            log_message = f'{adapter_name} → {workflow_name} → local-workflow\n'
            log_message += f'Node: {node_name}\n'
            log_message += f'Response: {response_content[:500]}'  # Limit length
            
            await ap.monitoring_service.record_message(
                bot_id=query.bot_uuid or '',
                bot_name=workflow_name or 'Workflow',
                pipeline_id=workflow_id,
                pipeline_name=pipeline_name,
                message_content=log_message,
                session_id=session_id,
                status='success',
                level='info',
                platform='workflow',
                user_id=query.sender_id,
                user_name=query.sender_name,
                role='assistant',
            )
        except Exception as e:
            ap.logger.error(f'Failed to record LLM response log: {e}')

    @staticmethod
    async def record_reply_log(
        ap: app.Application,
        query: WorkflowQuery,
        workflow_id: str,
        workflow_name: str,
        node_name: str,
        reply_content: str,
    ):
        """Record reply message log
        
        Format: adapter → workflow_name → local-workflow
        Contains: reply message content
        """
        try:
            adapter_name = WorkflowMonitoringHelper._get_adapter_name(query)
            session_id = WorkflowMonitoringHelper._get_session_id(query)
            
            # Build pipeline_name: workflow_name/local-workflow
            pipeline_name = f'{workflow_name}/local-workflow' if workflow_name else 'local-workflow'
            
            # Build log message
            log_message = f'{adapter_name} → {workflow_name} → local-workflow\n'
            log_message += f'Node: {node_name}\n'
            log_message += f'Reply: {reply_content[:500]}'  # Limit length
            
            await ap.monitoring_service.record_message(
                bot_id=query.bot_uuid or '',
                bot_name=workflow_name or 'Workflow',
                pipeline_id=workflow_id,
                pipeline_name=pipeline_name,
                message_content=log_message,
                session_id=session_id,
                status='success',
                level='info',
                platform='workflow',
                user_id=query.sender_id,
                user_name=query.sender_name,
                role='assistant',
            )
        except Exception as e:
            ap.logger.error(f'Failed to record reply log: {e}')


class LLMCallMonitor:
    """Context manager for monitoring LLM calls in workflow"""

    def __init__(
        self,
        ap: app.Application,
        query: WorkflowQuery,
        bot_id: str,
        bot_name: str,
        workflow_id: str,
        workflow_name: str,
        node_name: str,
        model_name: str,
    ):
        self.ap = ap
        self.query = query
        self.bot_id = bot_id
        self.bot_name = bot_name
        self.workflow_id = workflow_id
        self.workflow_name = workflow_name
        self.node_name = node_name
        self.model_name = model_name
        self.start_time = None
        self.input_tokens = 0
        self.output_tokens = 0

    async def __aenter__(self):
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.time() - self.start_time) * 1000) if self.start_time else 0

        if exc_type is not None:
            await WorkflowMonitoringHelper.record_llm_call_log(
                ap=self.ap,
                query=self.query,
                workflow_id=self.workflow_id,
                workflow_name=self.workflow_name,
                node_name=self.node_name,
                model_name=self.model_name,
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
                duration_ms=duration_ms,
                status='error',
                error_message=str(exc_val) if exc_val else None,
            )
        else:
            await WorkflowMonitoringHelper.record_llm_call_log(
                ap=self.ap,
                query=self.query,
                workflow_id=self.workflow_id,
                workflow_name=self.workflow_name,
                node_name=self.node_name,
                model_name=self.model_name,
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
                duration_ms=duration_ms,
                status='success',
            )

        return False
