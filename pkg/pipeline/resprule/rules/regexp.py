import re

import mirai

from .. import rule as rule_model
from .. import entities


class RegExpRule(rule_model.GroupRespondRule):

    async def match(
        self,
        message_text: str,
        message_chain: mirai.MessageChain,
        rule_dict: dict
    ) -> entities.RuleJudgeResult:
        regexps = rule_dict['regexp']

        for regexp in regexps:
            match = re.match(regexp, message_text)

            if match:
                return entities.RuleJudgeResult(
                    matching=True,
                    replacement=message_chain,
                )
        
        return entities.RuleJudgeResult(
            matching=False,
            replacement=message_chain
        )
