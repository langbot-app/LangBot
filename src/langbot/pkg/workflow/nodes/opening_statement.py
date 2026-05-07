"""Opening Statement Node - provide conversation opener and suggested questions

Node metadata is loaded from: ../../templates/metadata/nodes/opening_statement.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('opening_statement')
class OpeningStatementNode(WorkflowNode):
    """Opening statement node - provide conversation opener and suggested questions"""

    type_name = "opening_statement"
    category = "action"
    icon = "👋"
    name = "opening_statement"
    description = "opening_statement"
    name_zh = "对话开场白"
    name_en = "Opening Statement"
    description_zh = "提供对话开场白和建议问题"
    description_en = "Provide conversation opener and suggested questions"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        statement = self.get_config("statement", "")
        suggestions = self.get_config("suggested_questions", [])
        show = self.get_config("show_suggestions", True)

        return {"statement": statement, "suggested_questions": suggestions if show else []}
