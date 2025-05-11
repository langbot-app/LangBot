from __future__ import annotations
import re

from .. import entities
from .. import filter as filter_model


@filter_model.filter_class("content-ignore")
class ContentIgnore(filter_model.ContentFilter):
    """根据内容忽略消息"""

    @property
    def enable_stages(self):
        return [
            entities.EnableStage.PRE,
        ]

    async def process(self, message: str) -> entities.FilterResult:
        if 'prefix' in self.ap.pipeline_cfg.data['ignore-rules']:
            for rule in self.ap.pipeline_cfg.data['ignore-rules']['prefix']:
                if message.startswith(rule):
                    return entities.FilterResult(
                        level=entities.ResultLevel.BLOCK,
                        replacement='',
                        user_notice='',
                        console_notice='根据 ignore_rules 中的 prefix 规则，忽略消息'
                    )
        
        if 'regexp' in self.ap.pipeline_cfg.data['ignore-rules']:
            for rule in self.ap.pipeline_cfg.data['ignore-rules']['regexp']:
                if re.search(rule, message):
                    return entities.FilterResult(
                        level=entities.ResultLevel.BLOCK,
                        replacement='',
                        user_notice='',
                        console_notice='根据 ignore_rules 中的 regexp 规则，忽略消息'
                    )

        return entities.FilterResult(
            level=entities.ResultLevel.PASS,
            replacement=message,
            user_notice='',
            console_notice=''
        )