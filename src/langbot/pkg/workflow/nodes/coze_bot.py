"""Coze Bot Node - call Coze API bot

Node metadata is loaded from: ../../templates/metadata/nodes/coze_bot.yaml
"""

from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.workflow import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('coze_bot')
class CozeBotNode(WorkflowNode):
    """Coze bot node - call Coze API bot"""

    category = 'integration'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        api_key = self.get_config('api_key', '')
        bot_id = self.get_config('bot_id', '')
        api_base = self.get_config('api_base', 'https://api.coze.cn')
        query = inputs.get('query', '')
        conversation_id = inputs.get('conversation_id')

        return {
            'answer': '',
            'conversation_id': conversation_id,
            'success': False,
            '_debug': {
                'api_key': api_key[:8] + '...' if api_key else '',
                'bot_id': bot_id,
                'api_base': api_base,
                'query': query,
            },
        }
