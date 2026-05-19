from __future__ import annotations

from .. import truncator
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from ....agent.runner.config_migration import ConfigMigration


@truncator.truncator_class('round')
class RoundTruncator(truncator.Truncator):
    """Truncate the conversation message chain to adapt to the LLM message length limit."""

    async def truncate(self, query: pipeline_query.Query) -> pipeline_query.Query:
        """截断"""
        # max-round remains a pipeline-side trimming knob until token-budget
        # based compaction replaces this stage.
        runner_id = ConfigMigration.resolve_runner_id(query.pipeline_config)
        runner_config = ConfigMigration.resolve_runner_config(query.pipeline_config, runner_id) if runner_id else {}
        max_round = runner_config.get('max-round', 10)

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
