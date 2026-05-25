"""Database Query Node - execute database queries

Node metadata is loaded from: ../../templates/metadata/nodes/database_query.yaml
"""

from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.workflow.entities import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('database_query')
class DatabaseQueryNode(WorkflowNode):
    """Database query node - execute database queries"""

    category = 'integration'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        connection_type = self.get_config('connection_type', 'postgresql')
        query = self.get_config('query', '')
        query_type = self.get_config('query_type', 'select')
        timeout = self.get_config('timeout', 30)

        parameters = inputs.get('parameters', {})

        return {
            'results': [],
            'row_count': 0,
            'success': False,
            '_debug': {
                'connection_type': connection_type,
                'query': query,
                'query_type': query_type,
                'timeout': timeout,
                'parameters': parameters,
            },
        }
