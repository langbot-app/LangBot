import random

import mirai

from .. import rule as rule_model
from .. import entities


class RandomRespRule(rule_model.GroupRespondRule):

    async def match(
        self,
        message_text: str,
        message_chain: mirai.MessageChain,
        rule_dict: dict
    ) -> entities.RuleJudgeResult:
        random_rate = rule_dict['random']
        
        return entities.RuleJudgeResult(
            matching=random.random() < random_rate,
            replacement=message_chain
        )