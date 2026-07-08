from __future__ import annotations

from .. import truncator
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


@truncator.truncator_class('round')
class RoundTruncator(truncator.Truncator):
    """Truncate the conversation message chain to adapt to the LLM message length limit."""

    async def truncate(self, query: pipeline_query.Query) -> pipeline_query.Query:
        """截断"""
        max_round = query.pipeline_config['ai']['local-agent']['max-round']

        temp_messages = []

        current_round = 0

        # Traverse from back to front
        for msg in query.messages[::-1]:
            if current_round < max_round:
                temp_messages.append(msg)
                if msg.role == 'user':
                    current_round += 1
            else:
                break

        query.messages = temp_messages[::-1]

        return query
