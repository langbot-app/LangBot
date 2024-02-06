import mirai

from .. import rule as rule_model
from .. import entities


class PrefixRule(rule_model.GroupRespondRule):

    async def match(
        self,
        message_text: str,
        message_chain: mirai.MessageChain,
        rule_dict: dict
    ) -> entities.RuleJudgeResult:
        prefixes = rule_dict['prefix']

        for prefix in prefixes:
            if message_text.startswith(prefix):

                return entities.RuleJudgeResult(
                    matching=True,
                    replacement=mirai.MessageChain([
                        mirai.Plain(message_text[len(prefix):])
                    ]),
                )

        return entities.RuleJudgeResult(
            matching=False,
            replacement=message_chain
        )
