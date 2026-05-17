"""Wait Node - pause execution for a duration

Node metadata is loaded from: ../../templates/metadata/nodes/wait.yaml
"""

from __future__ import annotations

from typing import Any

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('wait')
class WaitNode(WorkflowNode):
    """Wait node - pause execution for a duration"""

    category = 'control'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        import asyncio

        duration = self.get_config('duration', 1)
        duration_type = self.get_config('duration_type', 'seconds')

        if duration_type == 'minutes':
            duration *= 60
        elif duration_type == 'hours':
            duration *= 3600

        await asyncio.sleep(duration)

        return {'output': inputs.get('input')}
