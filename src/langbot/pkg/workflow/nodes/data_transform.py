"""Data Transform Node - transform data using templates or JSONPath

Node metadata is loaded from: ../../templates/metadata/nodes/data_transform.yaml
"""

from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.workflow import ExecutionContext
from ..node import WorkflowNode, workflow_node
from ..safe_eval import safe_eval_with_vars

@workflow_node('data_transform')
class DataTransformNode(WorkflowNode):
    """Data transform node - transform data using templates or JSONPath"""

    category = 'process'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        data = inputs.get('data')
        transform_type = self.get_config('transform_type', 'template')

        if transform_type == 'template':
            template = self.get_config('template', '')
            result = self._apply_template(template, data, context)
        elif transform_type == 'jsonpath':
            expression = self.get_config('expression', '$')
            result = self._apply_jsonpath(expression, data)
        elif transform_type == 'expression':
            expression = self.get_config('expression', '')
            result = self._evaluate_expression(expression, data, context)
        else:
            result = data

        return {'result': result}

    def _apply_template(self, template: str, data: Any, context: ExecutionContext) -> str:
        result = template
        if isinstance(data, dict):
            for key, value in data.items():
                result = result.replace(f'{{{{data.{key}}}}}', str(value))
        for key, value in context.variables.items():
            result = result.replace(f'{{{{variables.{key}}}}}', str(value))
        return result

    def _apply_jsonpath(self, expression: str, data: Any) -> Any:
        if expression == '$':
            return data
        if expression.startswith('$.'):
            parts = expression[2:].split('.')
            result = data
            for part in parts:
                if isinstance(result, dict):
                    result = result.get(part)
                elif isinstance(result, list) and part.isdigit():
                    result = result[int(part)]
                else:
                    return None
            return result
        return data

    def _evaluate_expression(self, expression: str, data: Any, context: ExecutionContext) -> Any:
        local_vars = {'data': data, 'variables': context.variables}
        try:
            return safe_eval_with_vars(expression, local_vars)
        except Exception:
            return None
