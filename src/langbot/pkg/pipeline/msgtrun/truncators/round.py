from __future__ import annotations

from .. import truncator
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from ....agent.runner.config_migration import ConfigMigration
from ....agent.runner.context_packager import (
    get_legacy_max_round,
    select_legacy_max_round_messages,
)


@truncator.truncator_class('round')
class RoundTruncator(truncator.Truncator):
    """Truncate the conversation message chain to adapt to the LLM message length limit."""

    async def truncate(self, query: pipeline_query.Query) -> pipeline_query.Query:
        """截断"""
        runner_id = ConfigMigration.resolve_runner_id(query.pipeline_config)
        if runner_id:
            runner_config = ConfigMigration.resolve_runner_config(query.pipeline_config, runner_id)
        else:
            runner_config = query.pipeline_config.get('msg-truncate', {}).get('round', {})

        query.messages = select_legacy_max_round_messages(
            query.messages,
            get_legacy_max_round(runner_config),
        )

        return query
