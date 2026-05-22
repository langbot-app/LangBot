"""Code Executor Node - run Python or JavaScript code

Node metadata is loaded from: ../../templates/metadata/nodes/code_executor.yaml
"""

from __future__ import annotations

import ast
import io
import logging
import sys
import threading
from typing import Any

from langbot_plugin.api.entities.builtin.workflow import ExecutionContext
from ..node import WorkflowNode, workflow_node

logger = logging.getLogger(__name__)

# 危险的内置函数和模块黑名单
_DANGEROUS_BUILTINS = {
    '__import__', 'eval', 'exec', 'compile', 'open', 'file',
    'input', 'exit', 'quit', 'globals', 'locals', 'vars',
    'dir', 'help', 'breakpoint',
}

# 允许的安全内置函数
_SAFE_BUILTINS = {
    'abs': abs, 'all': all, 'any': any, 'bin': bin, 'bool': bool,
    'bytearray': bytearray, 'bytes': bytes, 'callable': callable,
    'chr': chr, 'complex': complex, 'dict': dict, 'divmod': divmod,
    'enumerate': enumerate, 'filter': filter, 'float': float,
    'format': format, 'frozenset': frozenset, 'hash': hash,
    'hex': hex, 'int': int, 'isinstance': isinstance, 'issubclass': issubclass,
    'iter': iter, 'len': len, 'list': list, 'map': map, 'max': max,
    'min': min, 'next': next, 'object': object, 'oct': oct, 'ord': ord,
    'pow': pow, 'print': print, 'range': range, 'repr': repr,
    'reversed': reversed, 'round': round, 'set': set, 'slice': slice,
    'sorted': sorted, 'str': str, 'sum': sum, 'tuple': tuple,
    'type': type, 'zip': zip,
}


def _check_code_safety(code: str) -> list[str]:
    """检查代码中是否包含危险操作"""
    warnings = []
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            # 检查 import 语句
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                warnings.append('Import statements are not allowed')
            # 检查危险函数调用
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in _DANGEROUS_BUILTINS:
                    warnings.append(f'Dangerous function call: {node.func.id}')
                # 检查 __import__ 通过 getattr 调用
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ('__import__', 'eval', 'exec', 'open', 'file'):
                        warnings.append(f'Dangerous attribute access: {node.func.attr}')
    except SyntaxError as e:
        warnings.append(f'Syntax error in code: {e}')
    return warnings


class _ExecutionTimeoutError(Exception):
    """执行超时错误"""
    pass


def _run_with_timeout(func, timeout: float = 10.0):
    """带超时限制的函数执行"""
    result = [None]
    error = [None]

    def _target():
        try:
            result[0] = func()
        except Exception as e:
            error[0] = e

    thread = threading.Thread(target=_target)
    thread.daemon = True
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        raise _ExecutionTimeoutError(f'Code execution timed out after {timeout} seconds')

    if error[0]:
        raise error[0]

    return result[0]


@workflow_node('code_executor')
class CodeExecutorNode(WorkflowNode):
    """Code executor node - run Python or JavaScript code"""

    category = 'process'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        code = self.get_config('code', '')
        language = self.get_config('language', 'python')
        timeout = self.get_config('timeout', 10)

        # 限制最大超时时间
        timeout = min(max(timeout, 1), 30)

        if not code:
            return {'output': None, 'console': '', 'error': 'No code provided'}

        if language == 'python':
            return await self._execute_python(code, inputs, context, timeout)
        else:
            return await self._execute_javascript(code, inputs, context)

    async def _execute_python(self, code: str, inputs: dict[str, Any], context: ExecutionContext, timeout: float) -> dict[str, Any]:
        # 安全检查
        warnings = _check_code_safety(code)
        if warnings:
            logger.warning('Code safety warnings: %s', warnings)
            return {'output': None, 'console': '', 'error': '; '.join(warnings)}

        stdout_capture = io.StringIO()
        old_stdout = sys.stdout

        def _exec_code():
            nonlocal stdout_capture
            sys.stdout = stdout_capture
            try:
                # 使用更安全的执行方式
                compiled = compile(code, '<workflow>', 'exec')
                safe_globals = {
                    '__builtins__': _SAFE_BUILTINS,
                    '__name__': '__workflow_sandbox__',
                }
                local_vars = {'inputs': inputs, 'output': None}
                exec(compiled, safe_globals, local_vars)
                return local_vars.get('output')
            finally:
                sys.stdout = old_stdout

        try:
            output = _run_with_timeout(_exec_code, timeout)
            console_output = stdout_capture.getvalue()
            return {'output': output, 'console': console_output, 'error': None}
        except _ExecutionTimeoutError as e:
            logger.error('Code execution timeout: %s', e)
            return {'output': None, 'console': stdout_capture.getvalue(), 'error': str(e)}
        except Exception as e:
            logger.error('Code execution error: %s', e)
            return {'output': None, 'console': stdout_capture.getvalue(), 'error': f'{type(e).__name__}: {e}'}

    async def _execute_javascript(self, code: str, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        return {'output': None, 'console': '', 'error': 'JavaScript execution is not implemented'}
