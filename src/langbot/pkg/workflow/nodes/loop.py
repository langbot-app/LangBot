"""Loop Node - iterate over items"""

from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.workflow.entities import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('loop')
class LoopNode(WorkflowNode):
    """Loop node - iterate over items"""

    category = 'control'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        items = inputs.get('items', [])
        if not isinstance(items, list):
            items = [items] if items else []

        max_iterations = self.get_config('max_iterations', 100)
        items = items[:max_iterations]

        return {
            'item': items[0] if items else None,
            'index': 0,
            'results': [],
            'completed': len(items) == 0,
            '_items': items,
        }
