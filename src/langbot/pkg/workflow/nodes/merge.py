"""Merge Node - combine multiple inputs

Node metadata is loaded from: ../../templates/metadata/nodes/merge.yaml
"""

from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.workflow.entities import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('merge')
class MergeNode(WorkflowNode):
    """Merge node - combine multiple inputs"""

    category = 'control'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        strategy = self.get_config('merge_strategy', 'object')

        values = [inputs.get('input_1'), inputs.get('input_2'), inputs.get('input_3'), inputs.get('input_4')]
        non_null_values = [v for v in values if v is not None]

        if strategy == 'object':
            merged = {}
            for i, v in enumerate(non_null_values):
                if isinstance(v, dict):
                    merged.update(v)
                else:
                    merged[f'value_{i}'] = v
            return {'merged': merged, 'array': non_null_values}

        elif strategy == 'array':
            return {'merged': non_null_values, 'array': non_null_values}

        elif strategy == 'first_non_null':
            first = non_null_values[0] if non_null_values else None
            return {'merged': first, 'array': non_null_values}

        elif strategy == 'concat':
            if all(isinstance(v, str) for v in non_null_values):
                return {'merged': ''.join(non_null_values), 'array': non_null_values}
            elif all(isinstance(v, list) for v in non_null_values):
                merged_list = []
                for v in non_null_values:
                    merged_list.extend(v)
                return {'merged': merged_list, 'array': merged_list}
            else:
                return {'merged': non_null_values, 'array': non_null_values}

        return {'merged': non_null_values, 'array': non_null_values}
