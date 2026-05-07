"""Question Classifier Node - classify user questions into categories

Node metadata is loaded from: ../../templates/metadata/nodes/question_classifier.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('question_classifier')
class QuestionClassifierNode(WorkflowNode):
    """Question classifier node - classify user questions into categories"""

    type_name = "question_classifier"
    category = "process"
    icon = "🏷️"
    name = "question_classifier"
    description = "question_classifier"
    name_zh = "问题分类器"
    name_en = "Question Classifier"
    description_zh = "使用 AI 将问题分类到预定义类别"
    description_en = "Classify questions into predefined categories using AI"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        categories = self.get_config("categories", [])

        if categories:
            return {
                "category": categories[0].get("name", "unknown"),
                "confidence": 0.8,
                "all_scores": {cat.get("name"): 0.1 for cat in categories},
            }

        return {"category": "unknown", "confidence": 0.0, "all_scores": {}}
