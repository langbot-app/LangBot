"""Wait Node - pause execution for a duration

Node metadata is loaded from: ../../templates/metadata/nodes/wait.yaml
"""

from __future__ import annotations

import logging
from typing import Any

from langbot_plugin.api.entities.builtin.workflow import ExecutionContext
from ..node import WorkflowNode, workflow_node

logger = logging.getLogger(__name__)

# 最大等待时间（秒）
_MAX_WAIT_SECONDS = 300  # 5 分钟


@workflow_node('wait')
class WaitNode(WorkflowNode):
    """Wait node - pause execution for a duration"""

    category = 'control'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        import asyncio

        duration = self.get_config('duration', 1)
        duration_type = self.get_config('duration_type', 'seconds')

        # 转换为秒
        if duration_type == 'minutes':
            duration *= 60
        elif duration_type == 'hours':
            duration *= 3600

        # 限制最大等待时间
        if duration > _MAX_WAIT_SECONDS:
            logger.warning('Wait duration %s exceeds maximum %s, capping to %s',
                          duration, _MAX_WAIT_SECONDS, _MAX_WAIT_SECONDS)
            duration = _MAX_WAIT_SECONDS

        # 确保 duration 为正数
        duration = max(0, duration)

        logger.info('Waiting for %.2f seconds', duration)
        await asyncio.sleep(duration)

        return {'output': inputs.get('input'), 'waited_seconds': duration}
