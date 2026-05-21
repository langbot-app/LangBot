"""Parameter Extractor Node - extract structured parameters from text

Node metadata is loaded from: ../../templates/metadata/nodes/parameter_extractor.yaml
"""

from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.workflow import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('parameter_extractor')
class ParameterExtractorNode(WorkflowNode):
    """Parameter extractor node - extract structured parameters from text"""

    category = 'process'
    icon: str = 'Variable'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        param_defs = self.get_config('parameters', [])

        extracted = {}
        for param in param_defs:
            extracted[param.get('name', '')] = None

        return {'parameters': extracted, 'extraction_success': False}
