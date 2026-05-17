"""Opening Statement Node - provide conversation opener and suggested questions

Node metadata is loaded from: ../../templates/metadata/nodes/opening_statement.yaml
"""

from __future__ import annotations

from typing import Any

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('opening_statement')
class OpeningStatementNode(WorkflowNode):
    """Opening statement node - provide conversation opener and suggested questions"""

    category = 'action'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        statement = self.get_config('statement', '')
        suggestions = self.get_config('suggested_questions', [])
        show = self.get_config('show_suggestions', True)

        return {'statement': statement, 'suggested_questions': suggestions if show else []}
