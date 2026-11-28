from .. import rule as rule_model
from .. import entities
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


@rule_model.rule_class('prefix')
class PrefixRule(rule_model.GroupRespondRule):
    async def match(
        self,
        message_text: str,
        message_chain: platform_message.MessageChain,
        rule_dict: dict,
        query: pipeline_query.Query,
    ) -> entities.RuleJudgeResult:
        prefixes = rule_dict['prefix']

        for prefix in prefixes:
            if message_text.startswith(prefix):
                # Remove the prefix from the leading text only, and leave later text untouched.
                remaining = len(prefix)
                for me in message_chain:
                    if remaining <= 0:
                        break
                    if isinstance(me, platform_message.Plain):
                        cut = min(remaining, len(me.text))
                        me.text = me.text[cut:]
                        remaining -= cut
                    elif not isinstance(me, platform_message.Source):
                        break

                return entities.RuleJudgeResult(
                    matching=True,
                    replacement=message_chain,
                )

        return entities.RuleJudgeResult(matching=False, replacement=message_chain)
