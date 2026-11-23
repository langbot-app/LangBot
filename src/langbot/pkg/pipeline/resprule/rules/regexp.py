from .. import rule as rule_model
from .. import entities
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from ....utils.safe_regex import SafeRegexError, matches_any


@rule_model.rule_class('regexp')
class RegExpRule(rule_model.GroupRespondRule):
    async def match(
        self,
        message_text: str,
        message_chain: platform_message.MessageChain,
        rule_dict: dict,
        query: pipeline_query.Query,
    ) -> entities.RuleJudgeResult:
        try:
            matching = await matches_any(
                rule_dict['regexp'],
                message_text,
                mode='match',
            )
        except SafeRegexError as exc:
            self.ap.logger.warning(f'Group response regex rejected: {exc}')
            matching = False

        if matching:
            return entities.RuleJudgeResult(
                matching=True,
                replacement=message_chain,
            )

        return entities.RuleJudgeResult(matching=False, replacement=message_chain)
