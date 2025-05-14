from __future__ import annotations
import re

from .. import entities
from .. import filter as filter_model
from ....core import entities as core_entities


@filter_model.filter_class('content-ignore')
class ContentIgnore(filter_model.ContentFilter):
    """根据内容忽略消息"""

    @property
    def enable_stages(self):
        return [
            entities.EnableStage.PRE,
        ]

    async def process(self, query: core_entities.Query, message: str) -> entities.FilterResult:
        if 'prefix' in query.pipeline_config['trigger']['ignore-rules']:
            for rule in query.pipeline_config['trigger']['ignore-rules']['prefix']:
                if message.startswith(rule):
                    return entities.FilterResult(
                        level=entities.ResultLevel.BLOCK,
                        replacement='',
                        user_notice='',
                        console_notice='根据 ignore_rules 中的 prefix 规则，忽略消息',
                    )

        if 'regexp' in query.pipeline_config['trigger']['ignore-rules']:
            for rule in query.pipeline_config['trigger']['ignore-rules']['regexp']:
                if re.search(rule, message):
                    return entities.FilterResult(
                        level=entities.ResultLevel.BLOCK,
                        replacement='',
                        user_notice='',
                        console_notice='根据 ignore_rules 中的 regexp 规则，忽略消息',
                    )

        return entities.FilterResult(
            level=entities.ResultLevel.PASS,
            replacement=message,
            user_notice='',
            console_notice='',
        )
