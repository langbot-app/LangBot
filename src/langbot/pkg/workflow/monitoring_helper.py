"""
Monitoring helper for recording events during workflow execution.
This module provides convenient methods to record monitoring data
without cluttering the main workflow code.

Logging scheme (aligned with pipeline monitoring):
- Trigger log: stores original user message content directly
- LLM call log: uses record_llm_call only (no additional message record)
- LLM response log: stores response message content directly
- Reply log: stores reply content directly

Fields are extracted from WorkflowQuery object when available, with fallback to context_vars.
"""

from __future__ import annotations

import typing
import time
import json

if typing.TYPE_CHECKING:
    from ..core import app


class WorkflowMonitoringHelper:
    """Helper class for workflow monitoring operations"""

    @staticmethod
    def _is_workflow_query(query) -> bool:
        """Check if query is a WorkflowQuery object"""
        if query is None or isinstance(query, str):
            return False
        # Check for WorkflowQuery attributes
        return hasattr(query, 'launcher_type') or hasattr(query, 'workflow_uuid')

    @staticmethod
    def _get_session_id(query, context_vars: dict | None = None) -> str:
        """Build session_id from query or context_vars"""
        # Try to get from WorkflowQuery first
        if WorkflowMonitoringHelper._is_workflow_query(query) and query.launcher_type:
            launcher_type = query.launcher_type.value if hasattr(query.launcher_type, 'value') else str(query.launcher_type)
            launcher_id = query.launcher_id or 'unknown'
            return f'{launcher_type}_{launcher_id}'
        
        # Fallback to context_vars
        if context_vars and context_vars.get('_launcher_type') and context_vars.get('_launcher_id'):
            return f"{context_vars['_launcher_type']}_{context_vars['_launcher_id']}"
        
        return 'workflow_session'

    @staticmethod
    def _get_platform(query, context_vars: dict | None = None) -> str:
        """Get platform name from query or context_vars"""
        # Try WorkflowQuery first
        if WorkflowMonitoringHelper._is_workflow_query(query) and query.launcher_type:
            if hasattr(query.launcher_type, 'value'):
                return query.launcher_type.value
            return str(query.launcher_type)
        
        # Fallback to context_vars for launcher_type (person/group)
        if context_vars and context_vars.get('_launcher_type'):
            return context_vars['_launcher_type']
        
        return 'workflow'

    @staticmethod
    def _get_sender_name(query, context_vars: dict | None = None) -> str | None:
        """Get sender name from query or context_vars"""
        # Try WorkflowQuery first
        if WorkflowMonitoringHelper._is_workflow_query(query):
            if query.sender_name:
                return query.sender_name
            if query.message_event and hasattr(query.message_event, 'sender'):
                sender = query.message_event.sender
                if hasattr(sender, 'nickname'):
                    return sender.nickname
                if hasattr(sender, 'member_name'):
                    return sender.member_name
        
        # Fallback to context_vars
        if context_vars:
            return context_vars.get('_sender_name')
        
        return None

    @staticmethod
    async def record_trigger_log(
        ap: app.Application,
        query,
        workflow_id: str,
        workflow_name: str,
        bot_name: str = 'Workflow',
        context_vars: dict | None = None,
    ) -> str:
        """Record trigger node log (stores original user message content directly)
        
        Aligned with pipeline monitoring: record_query_start
        """
        try:
            session_id = WorkflowMonitoringHelper._get_session_id(query, context_vars)
            platform = WorkflowMonitoringHelper._get_platform(query, context_vars)
            sender_name = WorkflowMonitoringHelper._get_sender_name(query, context_vars)
            
            # Get message content - store original content directly
            message_content = ''
            if isinstance(query, str):
                message_content = query
            elif not isinstance(query, str) and query.message_context:
                message_content = query.message_context.message_content
            elif not isinstance(query, str) and query.message_chain and hasattr(query.message_chain, 'model_dump'):
                message_content = json.dumps(query.message_chain.model_dump(), ensure_ascii=False)
            elif not isinstance(query, str) and query.user_message:
                message_content = str(query.user_message)
            
            # Get bot_id and user_id
            bot_id = ''
            user_id = None
            if not isinstance(query, str):
                bot_id = query.bot_uuid or ''
                user_id = query.sender_id
            elif context_vars:
                bot_id = context_vars.get('_bot_id', '') or ''
                user_id = context_vars.get('_user_id')
            
            message_id = await ap.monitoring_service.record_message(
                bot_id=bot_id,
                bot_name=bot_name,
                pipeline_id=workflow_id,
                pipeline_name=workflow_name or 'Workflow',
                message_content=message_content,
                session_id=session_id,
                status='success',
                level='info',
                platform=platform,
                user_id=user_id,
                user_name=sender_name,
                role='user',
                runner_name='local-workflow',
            )
            
            return message_id
        except Exception as e:
            ap.logger.error(f'Failed to record trigger log: {e}')
            return ''

    @staticmethod
    async def record_llm_call_log(
        ap: app.Application,
        query,
        workflow_id: str,
        workflow_name: str,
        node_name: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int,
        status: str = 'success',
        error_message: str | None = None,
        bot_name: str = 'Workflow',
        context_vars: dict | None = None,
        input_message: str | None = None,
        message_id: str | None = None,
    ):
        """Record LLM call log with message_id association
        
        Aligned with pipeline monitoring: record_llm_call with message_id
        LLM calls are aggregated under the trigger log via message_id.
        """
        try:
            session_id = WorkflowMonitoringHelper._get_session_id(query, context_vars)
            
            # Get bot_id
            bot_id = ''
            if not isinstance(query, str):
                bot_id = query.bot_uuid or ''
            elif context_vars:
                bot_id = context_vars.get('_bot_id', '') or ''
            
            # Record LLM call with message_id for association
            await ap.monitoring_service.record_llm_call(
                bot_id=bot_id,
                bot_name=bot_name,
                pipeline_id=workflow_id,
                pipeline_name=workflow_name or 'Workflow',
                session_id=session_id,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration=duration_ms,
                status=status,
                error_message=error_message,
                message_id=message_id,
            )
        except Exception as e:
            ap.logger.error(f'Failed to record LLM call log: {e}')

    @staticmethod
    async def record_llm_response_log(
        ap: app.Application,
        query,
        workflow_id: str,
        workflow_name: str,
        node_name: str,
        response_content: str,
        bot_name: str = 'Workflow',
        context_vars: dict | None = None,
    ):
        """Record LLM response log (stores response content directly)
        
        Aligned with pipeline monitoring: record_query_response
        """
        try:
            session_id = WorkflowMonitoringHelper._get_session_id(query, context_vars)
            platform = WorkflowMonitoringHelper._get_platform(query, context_vars)
            sender_name = WorkflowMonitoringHelper._get_sender_name(query, context_vars)
            
            # Get bot_id and user_id
            bot_id = ''
            user_id = None
            if not isinstance(query, str):
                bot_id = query.bot_uuid or ''
                user_id = query.sender_id
            elif context_vars:
                bot_id = context_vars.get('_bot_id', '') or ''
                user_id = context_vars.get('_user_id')
            
            # Store response content directly, no prefix
            await ap.monitoring_service.record_message(
                bot_id=bot_id,
                bot_name=bot_name,
                pipeline_id=workflow_id,
                pipeline_name=workflow_name or 'Workflow',
                message_content=response_content[:2000],  # Limit length
                session_id=session_id,
                status='success',
                level='info',
                platform=platform,
                user_id=user_id,
                user_name=sender_name,
                role='assistant',
                runner_name='local-workflow',
            )
        except Exception as e:
            ap.logger.error(f'Failed to record LLM response log: {e}')

    @staticmethod
    async def record_reply_log(
        ap: app.Application,
        query,
        workflow_id: str,
        workflow_name: str,
        node_name: str,
        reply_content: str,
        bot_name: str = 'Workflow',
        context_vars: dict | None = None,
    ):
        """Record reply message log (stores reply content directly)
        
        Aligned with pipeline monitoring: record_query_response
        """
        try:
            session_id = WorkflowMonitoringHelper._get_session_id(query, context_vars)
            platform = WorkflowMonitoringHelper._get_platform(query, context_vars)
            sender_name = WorkflowMonitoringHelper._get_sender_name(query, context_vars)
            
            # Get bot_id and user_id
            bot_id = ''
            user_id = None
            if not isinstance(query, str):
                bot_id = query.bot_uuid or ''
                user_id = query.sender_id
            elif context_vars:
                bot_id = context_vars.get('_bot_id', '') or ''
                user_id = context_vars.get('_user_id')
            
            # Store reply content directly, no prefix
            await ap.monitoring_service.record_message(
                bot_id=bot_id,
                bot_name=bot_name,
                pipeline_id=workflow_id,
                pipeline_name=workflow_name or 'Workflow',
                message_content=reply_content[:2000],  # Limit length
                session_id=session_id,
                status='success',
                level='info',
                platform=platform,
                user_id=user_id,
                user_name=sender_name,
                role='assistant',
                runner_name='local-workflow',
            )
        except Exception as e:
            ap.logger.error(f'Failed to record reply log: {e}')


class LLMCallMonitor:
    """Context manager for monitoring LLM calls in workflow"""

    def __init__(
        self,
        ap: app.Application,
        query,
        bot_id: str,
        bot_name: str,
        workflow_id: str,
        workflow_name: str,
        node_name: str,
        model_name: str,
        context_vars: dict | None = None,
    ):
        self.ap = ap
        self.query = query
        self.bot_id = bot_id
        self.bot_name = bot_name
        self.workflow_id = workflow_id
        self.workflow_name = workflow_name
        self.node_name = node_name
        self.model_name = model_name
        self.context_vars = context_vars
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
                bot_name=self.bot_name,
                context_vars=self.context_vars,
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
                bot_name=self.bot_name,
                context_vars=self.context_vars,
            )

        return False
