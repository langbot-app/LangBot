import random


from .. import rule as rule_model
from .. import entities
from ....core import entities as core_entities
from ....platform.types import message as platform_message


@rule_model.rule_class('random')
class RandomRespRule(rule_model.GroupRespondRule):
    async def match(
        self,
        message_text: str,
        message_chain: platform_message.MessageChain,
        rule_dict: dict,
        query: core_entities.Query,
    ) -> entities.RuleJudgeResult:
        random_rate = rule_dict['random']

        return entities.RuleJudgeResult(matching=random.random() < random_rate, replacement=message_chain)
