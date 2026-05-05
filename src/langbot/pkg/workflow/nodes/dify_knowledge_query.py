"""Dify Knowledge Query Node - query Dify knowledge base

Node metadata is loaded from: ../../templates/metadata/nodes/dify_knowledge_query.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('dify_knowledge_query')
class DifyKnowledgeQueryNode(WorkflowNode):
    """Dify knowledge base query node - query Dify knowledge base"""

    type_name = "dify_knowledge_query"
    category = "integration"
    icon = "BookOpen"
    name = "dify_knowledge_query"
    description = "dify_knowledge_query"
    name_zh = "Dify 知识库查询"
    name_en = "Dify Knowledge Query"
    description_zh = "查询 Dify 知识库"
    description_en = "Query Dify knowledge base"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        base_url = self.get_config("base_url", "https://api.dify.ai/v1")
        api_key = self.get_config("api_key", "")
        dataset_id = self.get_config("dataset_id", "")
        query = inputs.get("query", "")

        return {
            "results": [],
            "success": False,
            "_debug": {
                "base_url": base_url,
                "api_key": api_key[:8] + "..." if api_key else "",
                "dataset_id": dataset_id,
                "query": query,
            },
        }
