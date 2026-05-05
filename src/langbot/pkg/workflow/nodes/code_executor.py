"""Code Executor Node - run Python or JavaScript code

Node metadata is loaded from: ../../templates/metadata/nodes/code_executor.yaml
"""

from __future__ import annotations

import json
import re
from typing import Any, ClassVar

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('code_executor')
class CodeExecutorNode(WorkflowNode):
    """Code executor node - run Python or JavaScript code"""

    type_name = "code_executor"
    category = "process"
    icon = "💻"
    name = "code_executor"
    description = "code_executor"
    name_zh = "代码执行"
    name_en = "Code Executor"
    description_zh = "执行自定义代码处理数据"
    description_en = "Execute custom code to process data"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        code = self.get_config("code", "")
        language = self.get_config("language", "python")

        if language == "python":
            return await self._execute_python(code, inputs, context)
        else:
            return await self._execute_javascript(code, inputs, context)

    async def _execute_python(self, code: str, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        import io
        import sys

        stdout_capture = io.StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = stdout_capture

            restricted_globals = {
                '__builtins__': {
                    'len': len, 'str': str, 'int': int, 'float': float, 'bool': bool,
                    'list': list, 'dict': dict, 'set': set, 'tuple': tuple,
                    'range': range, 'enumerate': enumerate, 'zip': zip,
                    'map': map, 'filter': filter, 'sorted': sorted, 'reversed': reversed,
                    'sum': sum, 'min': min, 'max': max, 'abs': abs, 'round': round,
                    'print': print, 'isinstance': isinstance, 'type': type,
                    'hasattr': hasattr, 'getattr': getattr, 'json': json, 're': re,
                }
            }

            local_vars = {'inputs': inputs, 'output': None}
            exec(code, restricted_globals, local_vars)

            return {"output": local_vars.get('output'), "console": stdout_capture.getvalue()}
        finally:
            sys.stdout = old_stdout

    async def _execute_javascript(self, code: str, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        return {"output": f"[JS execution not implemented: {code[:50]}...]", "console": ""}
