from __future__ import annotations

import mirai

from .. import rule as rule_model
from .. import entities
from ....core import entities as core_entities


class AtBotRule(rule_model.GroupRespondRule):

    async def match(
        self,
        message_text: str,
        message_chain: mirai.MessageChain,
        rule_dict: dict,
        query: core_entities.Query
    ) -> entities.RuleJudgeResult:
        
        if message_chain.has(mirai.At(query.adapter.bot_account_id)) and rule_dict['at']:
            message_chain.remove(mirai.At(query.adapter.bot_account_id))
            return entities.RuleJudgeResult(
                matching=True,
                replacement=message_chain,
            )

        return entities.RuleJudgeResult(
            matching=False,
            replacement = message_chain
        )
