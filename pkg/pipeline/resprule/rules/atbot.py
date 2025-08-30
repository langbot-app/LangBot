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
        def remove_at(message_chain: platform_message.MessageChain):
            for component in message_chain.root:
                if isinstance(component, platform_message.At) and component.target == query.adapter.bot_account_id:
                    message_chain.remove(component)
                    break

        remove_at(message_chain)
        remove_at(message_chain)  # 回复消息时会at两次，检查并删除重复的

        # if message_chain.has(platform_message.At(query.adapter.bot_account_id)) and rule_dict['at']:
        #     message_chain.remove(platform_message.At(query.adapter.bot_account_id))

        #     if message_chain.has(
        #         platform_message.At(query.adapter.bot_account_id)
        #     ):  # 回复消息时会at两次，检查并删除重复的
        #         message_chain.remove(platform_message.At(query.adapter.bot_account_id))

        #     return entities.RuleJudgeResult(
        #         matching=True,
        #         replacement=message_chain,
        #     )

        return entities.RuleJudgeResult(matching=False, replacement=message_chain)
