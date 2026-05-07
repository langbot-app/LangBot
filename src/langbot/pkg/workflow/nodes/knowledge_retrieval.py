"""Knowledge Retrieval Node - search in knowledge base

Node metadata is loaded from: ../../templates/metadata/nodes/knowledge_retrieval.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('knowledge_retrieval')
class KnowledgeRetrievalNode(WorkflowNode):
    """Knowledge retrieval node - search in knowledge base"""

    type_name = "knowledge_retrieval"
    category = "process"
    icon = "📚"
    name = "knowledge_retrieval"
    description = "knowledge_retrieval"
    name_zh = "知识库检索"
    name_en = "Knowledge Retrieval"
    description_zh = "从知识库中检索相关信息"
    description_en = "Retrieve relevant information from knowledge bases"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        query = inputs.get("query", "")
        return {"documents": [], "citations": [], "context": f"[Knowledge base search for: {query}]"}
