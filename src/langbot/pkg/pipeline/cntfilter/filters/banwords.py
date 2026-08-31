from __future__ import annotations

from .. import filter as filter_model
from .. import entities
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from ....utils.safe_regex import SafeRegexError, mask_patterns

# Legacy sensitive-words.json files shipped ~70 rules, which exceeds the
# default safe_regex per-call cap of 64 and used to fail-close every message.
# Keep one 50ms CPU budget for the whole list; only raise the pattern cap.
_MAX_SENSITIVE_WORD_PATTERNS = 256


@filter_model.filter_class('ban-word-filter')
class BanWordFilter(filter_model.ContentFilter):
    """Filter content"""

    async def initialize(self):
        pass

    async def process(self, query: pipeline_query.Query, message: str) -> entities.FilterResult:
        words = self.ap.sensitive_meta.data.get('words') or []
        mask = self.ap.sensitive_meta.data['mask']
        mask_word = self.ap.sensitive_meta.data['mask_word']

        try:
            found, current = await mask_patterns(
                words,
                message,
                mask=mask,
                mask_word=mask_word,
                max_pattern_count=_MAX_SENSITIVE_WORD_PATTERNS,
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
            replacement=current,
            user_notice='消息中存在不合适的内容, 请修改' if found else '',
            console_notice='',
        )
