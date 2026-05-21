"""Knowledge Retrieval Node - search in knowledge base

Node metadata is loaded from: ../../templates/metadata/nodes/knowledge_retrieval.yaml
"""

from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.workflow import ExecutionContext
from ..node import WorkflowNode, workflow_node

@workflow_node('knowledge_retrieval')
class KnowledgeRetrievalNode(WorkflowNode):
    """Knowledge retrieval node - search in knowledge base"""

    category = 'process'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        query = inputs.get('query', '')
        return {'documents': [], 'citations': [], 'context': f'[Knowledge base search for: {query}]'}
