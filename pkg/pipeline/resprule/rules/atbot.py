from __future__ import annotations


from .. import rule as rule_model
from .. import entities
from ....core import entities as core_entities
from ....platform.types import message as platform_message


@rule_model.rule_class('at-bot')
class AtBotRule(rule_model.GroupRespondRule):
    async def match(
        self,
        message_text: str,
        message_chain: platform_message.MessageChain,
        rule_dict: dict,
        query: core_entities.Query,
    ) -> entities.RuleJudgeResult:
        if message_chain.has(platform_message.At(query.adapter.bot_account_id)) and rule_dict['at']:
            message_chain.remove(platform_message.At(query.adapter.bot_account_id))

            if message_chain.has(
                platform_message.At(query.adapter.bot_account_id)
            ):  # 回复消息时会at两次，检查并删除重复的
                message_chain.remove(platform_message.At(query.adapter.bot_account_id))

            return entities.RuleJudgeResult(
                matching=True,
                replacement=message_chain,
            )

        return entities.RuleJudgeResult(matching=False, replacement=message_chain)
