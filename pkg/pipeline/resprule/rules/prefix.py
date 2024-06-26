import mirai

from .. import rule as rule_model
from .. import entities
from ....core import entities as core_entities


@rule_model.rule_class("prefix")
class PrefixRule(rule_model.GroupRespondRule):

    async def match(
        self,
        message_text: str,
        message_chain: mirai.MessageChain,
        rule_dict: dict,
        query: core_entities.Query
    ) -> entities.RuleJudgeResult:
        prefixes = rule_dict['prefix']

        for prefix in prefixes:
            if message_text.startswith(prefix):

                # 查找第一个plain元素
                for me in message_chain:
                    if isinstance(me, mirai.Plain):
                        me.text = me.text[len(prefix):]

                return entities.RuleJudgeResult(
                    matching=True,
                    replacement=message_chain,
                )

        return entities.RuleJudgeResult(
            matching=False,
            replacement=message_chain
        )
