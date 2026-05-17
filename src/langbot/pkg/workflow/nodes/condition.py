"""Condition Node - branch based on condition

Node metadata is loaded from: ../../templates/metadata/nodes/condition.yaml
"""

from __future__ import annotations

from typing import Any

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node
from ..safe_eval import safe_eval_with_vars

@workflow_node('condition')
class ConditionNode(WorkflowNode):
    """Condition node - branch based on condition"""

    category = 'control'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        condition_type = self.get_config('condition_type', 'expression')
        input_data = inputs.get('input')

        result = False

        if condition_type == 'expression':
            expression = self.get_config('expression', 'false')
            result = await self._evaluate_expression(expression, input_data, context)
        elif condition_type == 'comparison':
            result = await self._evaluate_comparison(input_data, context)
        elif condition_type == 'contains':
            left = self.get_config('left_value', '')
            right = self.get_config('right_value', '')
            result = right in left
        elif condition_type == 'empty':
            result = not bool(input_data)
        elif condition_type == 'regex':
            import re

            left = self.get_config('left_value', '')
            pattern = self.get_config('right_value', '')
            result = bool(re.match(pattern, str(left)))

        if result:
            return {'true': input_data, 'false': None}
        else:
            return {'true': None, 'false': input_data}

    async def _evaluate_expression(self, expression: str, data: Any, context: ExecutionContext) -> bool:
        try:
            local_vars = {'input': data, 'data': data, 'variables': context.variables}
            return bool(safe_eval_with_vars(expression, local_vars))
        except Exception:
            return False

    async def _evaluate_comparison(self, data: Any, context: ExecutionContext) -> bool:
        left = self.get_config('left_value', '')
        right = self.get_config('right_value', '')
        operator = self.get_config('operator', '==')

        try:
            left_num = float(left)
            right_num = float(right)

            if operator == '==':
                return left_num == right_num
            elif operator == '!=':
                return left_num != right_num
            elif operator == '>':
                return left_num > right_num
            elif operator == '<':
                return left_num < right_num
            elif operator == '>=':
                return left_num >= right_num
            elif operator == '<=':
                return left_num <= right_num
        except ValueError:
            if operator == '==':
                return left == right
            elif operator == '!=':
                return left != right
            elif operator in ('>', '<', '>=', '<='):
                return False

        return False
