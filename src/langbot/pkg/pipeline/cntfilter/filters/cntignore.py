from __future__ import annotations

from .. import entities
from .. import filter as filter_model
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from ....utils.safe_regex import SafeRegexError, matches_any


@filter_model.filter_class('content-ignore')
class ContentIgnore(filter_model.ContentFilter):
    """Ignore message according to content"""

    @property
    def enable_stages(self):
        return [
            entities.EnableStage.PRE,
        ]

    async def process(self, query: pipeline_query.Query, message: str) -> entities.FilterResult:
        if 'prefix' in query.pipeline_config['trigger']['ignore-rules']:
            for rule in query.pipeline_config['trigger']['ignore-rules']['prefix']:
                if message.startswith(rule):
                    return entities.FilterResult(
                        level=entities.ResultLevel.BLOCK,
                        replacement='',
                        user_notice='',
                        console_notice='Ignore message according to prefix rule in ignore_rules',
                    )

        if 'regexp' in query.pipeline_config['trigger']['ignore-rules']:
            try:
                matches = await matches_any(
                    query.pipeline_config['trigger']['ignore-rules']['regexp'],
                    message,
                )
            except SafeRegexError as exc:
                return entities.FilterResult(
                    level=entities.ResultLevel.BLOCK,
                    replacement='',
                    user_notice='',
                    console_notice=f'Ignore-rule regex rejected: {exc}',
                )
            if matches:
                return entities.FilterResult(
                    level=entities.ResultLevel.BLOCK,
                    replacement='',
                    user_notice='',
                    console_notice='Ignore message according to regexp rule in ignore_rules',
                )

        return entities.FilterResult(
            level=entities.ResultLevel.PASS,
            replacement=message,
            user_notice='',
            console_notice='',
        )
