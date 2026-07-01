"""Store Data Node - save data to storage

Node metadata is loaded from: ../../templates/metadata/nodes/store_data.yaml
"""

from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.workflow.entities import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('store_data')
class StoreDataNode(WorkflowNode):
    """Store data node - save data to storage"""

    category = 'action'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        key = inputs.get('key', '')
        value = inputs.get('value')
        storage_type = self.get_config('storage_type', 'session')
        prefix = self.get_config('key_prefix', '')

        full_key = f'{prefix}{key}' if prefix else key

        if storage_type == 'session':
            context.set_conversation_variable(full_key, value)
        else:
            context.set_variable(full_key, value)

        return {'status': 'stored'}
