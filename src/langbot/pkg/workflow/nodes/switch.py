"""Switch Node - multi-way branch based on value

Node metadata is loaded from: ../../templates/metadata/nodes/switch.yaml
"""

from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.workflow import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('switch')
class SwitchNode(WorkflowNode):
    """Switch node - multi-way branch based on value"""

    category = 'control'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        expression = self.get_config('expression', '')
        cases = self.get_config('cases', [])
        input_data = inputs.get('input')

        value = await self._evaluate_expression(expression, input_data, context)

        for case in cases:
            if str(case.get('value')) == str(value):
                return {'matched_case': input_data, 'default': None, '_matched_output': case.get('output')}

        return {'matched_case': None, 'default': input_data}

    async def _evaluate_expression(self, expression: str, data: Any, context: ExecutionContext) -> Any:
        if not expression:
            return data

        if expression.startswith('{{') and expression.endswith('}}'):
            var_path = expression[2:-2].strip()
            parts = var_path.split('.')

            if parts[0] == 'input':
                result = data
                for part in parts[1:]:
                    if isinstance(result, dict):
                        result = result.get(part)
                    else:
                        return None
                return result
            elif parts[0] == 'variables':
                return context.variables.get('.'.join(parts[1:]))

        return expression
