from __future__ import annotations

from .. import truncator
from ....core import entities as core_entities


@truncator.truncator_class('round')
class RoundTruncator(truncator.Truncator):
    """前文回合数阶段器"""

    async def truncate(self, query: core_entities.Query) -> core_entities.Query:
        """截断"""
        max_round = query.pipeline_config['ai']['local-agent']['max-round']

        temp_messages = []

        current_round = 0

        # 从后往前遍历
        for msg in query.messages[::-1]:
            if current_round < max_round:
                temp_messages.append(msg)
                if msg.role == 'user':
                    current_round += 1
            else:
                break

        query.messages = temp_messages[::-1]

        return query
