"""Message Trigger Node - triggers workflow on message arrival

This module contains the implementation for the Message Trigger workflow node.
Node metadata (label, description, inputs, outputs, config) is loaded from:
../../templates/metadata/nodes/message_trigger.yaml
"""

from __future__ import annotations

import logging
from typing import Any

from langbot_plugin.api.entities.builtin.workflow.entities import ExecutionContext
from ..node import WorkflowNode, workflow_node
from .. import monitoring_helper

logger = logging.getLogger(__name__)


@workflow_node('message_trigger')
class MessageTriggerNode(WorkflowNode):
    """Message trigger node - triggers workflow on message arrival"""

    category = 'trigger'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        msg_ctx = context.message_context

        # Record trigger log and store message_id for LLM call association
        try:
            if self.ap and context.query:
                workflow_id = context.workflow_id or ''
                workflow_name = context.variables.get('_workflow_name', 'Workflow')
                bot_name = context.variables.get('_bot_name', 'Workflow')
                message_id = await monitoring_helper.WorkflowMonitoringHelper.record_trigger_log(
                    ap=self.ap,
                    query=context.query,
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    bot_name=bot_name,
                    context_vars=context.variables,
                )
                # Store message_id for LLM call monitoring association
                if message_id:
                    context.variables['_monitoring_message_id'] = message_id
        except Exception as e:
            logger.warning(f'[MessageTrigger:{self.node_id}] Failed to record trigger log: {e}')

        if msg_ctx:
            return {
                'message': msg_ctx.message_content,
                'sender_id': msg_ctx.sender_id,
                'sender_name': msg_ctx.sender_name,
                'platform': msg_ctx.platform,
                'conversation_id': msg_ctx.conversation_id,
                'is_group': msg_ctx.is_group,
                'context': msg_ctx.model_dump(),
            }

        # Use safe variable access with fallback
        return {
            'message': context.get_variable('message') or '',
            'sender_id': context.get_variable('sender_id') or '',
            'sender_name': context.get_variable('sender_name') or '',
            'platform': context.get_variable('platform') or '',
            'conversation_id': context.get_variable('conversation_id') or '',
            'is_group': context.get_variable('is_group') or False,
            'context': context.trigger_data or {},
        }
