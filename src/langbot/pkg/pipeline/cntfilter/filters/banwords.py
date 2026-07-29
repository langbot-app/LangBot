from __future__ import annotations

from .. import filter as filter_model
from .. import entities
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from ....utils.safe_regex import SafeRegexError, mask_patterns


@filter_model.filter_class('ban-word-filter')
class BanWordFilter(filter_model.ContentFilter):
    """Filter content"""

    async def initialize(self):
        pass

    async def process(self, query: pipeline_query.Query, message: str) -> entities.FilterResult:
        try:
            found, message = await mask_patterns(
                self.ap.sensitive_meta.data['words'],
                message,
                mask=self.ap.sensitive_meta.data['mask'],
                mask_word=self.ap.sensitive_meta.data['mask_word'],
            )
        except SafeRegexError as exc:
            return entities.FilterResult(
                level=entities.ResultLevel.BLOCK,
                replacement='',
                user_notice='内容检查规则执行失败，请联系管理员',
                console_notice=f'Sensitive-word regex rejected: {exc}',
            )

        return entities.FilterResult(
            level=entities.ResultLevel.MASKED if found else entities.ResultLevel.PASS,
            replacement=message,
            user_notice='消息中存在不合适的内容, 请修改' if found else '',
            console_notice='',
        )
