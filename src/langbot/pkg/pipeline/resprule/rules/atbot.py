from __future__ import annotations


from .. import rule as rule_model
from .. import entities
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


@rule_model.rule_class('at-bot')
class AtBotRule(rule_model.GroupRespondRule):
    async def match(
        self,
        message_text: str,
        message_chain: platform_message.MessageChain,
        rule_dict: dict,
        query: pipeline_query.Query,
    ) -> entities.RuleJudgeResult:
        found = False

        def remove_at(message_chain: platform_message.MessageChain):
            nonlocal found
            for component in message_chain.root:
                if isinstance(component, platform_message.At) and str(component.target) == str(
                    query.adapter.bot_account_id
                ):
                    message_chain.remove(component)
                    found = True
                    break

        remove_at(message_chain)
        remove_at(message_chain)  # 回复消息时会at两次，检查并删除重复的

        return entities.RuleJudgeResult(matching=found, replacement=message_chain)
