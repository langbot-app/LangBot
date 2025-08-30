from __future__ import annotations
import re

from .. import filter as filter_model
from .. import entities
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


@filter_model.filter_class('ban-word-filter')
class BanWordFilter(filter_model.ContentFilter):
    """Filter content"""

    async def initialize(self):
        pass

    async def process(self, query: pipeline_query.Query, message: str) -> entities.FilterResult:
        found = False

        for word in self.ap.sensitive_meta.data['words']:
            match = re.findall(word, message)

            if len(match) > 0:
                found = True

                for i in range(len(match)):
                    if self.ap.sensitive_meta.data['mask_word'] == '':
                        message = message.replace(
                            match[i],
                            self.ap.sensitive_meta.data['mask'] * len(match[i]),
                        )
                    else:
                        message = message.replace(match[i], self.ap.sensitive_meta.data['mask_word'])

        return entities.FilterResult(
            level=entities.ResultLevel.MASKED if found else entities.ResultLevel.PASS,
            replacement=message,
            user_notice='消息中存在不合适的内容, 请修改' if found else '',
            console_notice='',
        )
