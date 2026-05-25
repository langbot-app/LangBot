"""Condition Node - branch based on condition

Node metadata is loaded from: ../../templates/metadata/nodes/condition.yaml
"""

from __future__ import annotations

import logging
import re
import signal
from typing import Any

from langbot_plugin.api.entities.builtin.workflow.entities import ExecutionContext
from ..node import WorkflowNode, workflow_node
from ..safe_eval import safe_eval_with_vars

logger = logging.getLogger(__name__)

# 正则表达式超时限制（秒）
_REGEX_TIMEOUT = 2


class _RegexTimeoutError(Exception):
    """正则表达式超时错误"""
    pass


def _handle_timeout(signum, frame):
    """超时信号处理"""
    raise _RegexTimeoutError('Regex match timed out')


def _safe_regex_match(pattern: str, text: str) -> tuple[bool, str]:
    """安全地执行正则表达式匹配，带有超时限制"""
    # 设置超时信号
    old_handler = signal.signal(signal.SIGALRM, _handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, _REGEX_TIMEOUT)

    try:
        result = bool(re.match(pattern, str(text)))
        return result, ''
    except _RegexTimeoutError:
        logger.warning('Regex match timed out for pattern: %s', pattern[:50])
        return False, 'Regex match timed out'
    except re.error as e:
        logger.warning('Invalid regex pattern: %s', e)
        return False, f'Invalid regex: {e}'
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


@workflow_node('condition')
class ConditionNode(WorkflowNode):
    """Condition node - branch based on condition"""

    category = 'control'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        condition_type = self.get_config('condition_type', 'expression')
        input_data = inputs.get('input')

        result = False

        if condition_type == 'expression':
            expression = self.get_config('expression', 'false')
            result = await self._evaluate_expression(expression, input_data, context)
        elif condition_type == 'comparison':
            result = await self._evaluate_comparison(input_data, context)
        elif condition_type == 'contains':
            left = self.get_config('left_value', '')
            right = self.get_config('right_value', '')
            result = right in left
        elif condition_type == 'empty':
            result = not bool(input_data)
        elif condition_type == 'regex':
            left = self.get_config('left_value', '')
            pattern = self.get_config('right_value', '')
            result, error = _safe_regex_match(pattern, left)
            if error:
                return {'true': None, 'false': input_data, 'error': error}

        if result:
            return {'true': input_data, 'false': None}
        else:
            return {'true': None, 'false': input_data}

    async def _evaluate_expression(self, expression: str, data: Any, context: ExecutionContext) -> bool:
        try:
            local_vars = {'input': data, 'data': data, 'variables': context.variables}
            return bool(safe_eval_with_vars(expression, local_vars))
        except Exception as e:
            logger.warning('Expression evaluation error: %s', e)
            return False

    async def _evaluate_comparison(self, data: Any, context: ExecutionContext) -> bool:
        left = self.get_config('left_value', '')
        right = self.get_config('right_value', '')
        operator = self.get_config('operator', '==')

        try:
            left_num = float(left)
            right_num = float(right)

            if operator == '==':
                return left_num == right_num
            elif operator == '!=':
                return left_num != right_num
            elif operator == '>':
                return left_num > right_num
            elif operator == '<':
                return left_num < right_num
            elif operator == '>=':
                return left_num >= right_num
            elif operator == '<=':
                return left_num <= right_num
        except ValueError:
            if operator == '==':
                return left == right
            elif operator == '!=':
                return left != right
            elif operator in ('>', '<', '>=', '<='):
                return False

        return False
