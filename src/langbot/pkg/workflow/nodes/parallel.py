"""Parallel Node - execute multiple branches simultaneously"""

from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.workflow import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('parallel')
class ParallelNode(WorkflowNode):
    """Parallel node - execute multiple branches simultaneously"""

    category = 'control'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        return {
            'results': {},
            'errors': [],
        }
