from __future__ import annotations

import mirai

from ...core import app
from . import entities, rule
from .rules import atbot, prefix, regexp, random


class GroupRespondRuleChecker:
    """群组响应规则检查器
    """

    ap: app.Application

    rule_matchers: list[rule.GroupRespondRule]

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        """初始化检查器
        """
        self.rule_matchers = [
            atbot.AtBotRule(self.ap),
            prefix.PrefixRule(self.ap),
            regexp.RegExpRule(self.ap),
            random.RandomRespRule(self.ap),
        ]

        for rule_matcher in self.rule_matchers:
            await rule_matcher.initialize()

    async def check(
        self,
        message_text: str,
        message_chain: mirai.MessageChain,
        launcher_id: int,
        sender_id: int,
    ) -> entities.RuleJudgeResult:
        """检查消息是否匹配规则
        """
        rules = self.ap.cfg_mgr.data['response_rules']

        use_rule = rules['default']

        if str(launcher_id) in use_rule:
            use_rule = use_rule[str(launcher_id)]

        for rule_matcher in self.rule_matchers:
            res = await rule_matcher.match(message_text, message_chain, use_rule)
            if res.matching:
                return res
        
        return entities.RuleJudgeResult(
            matching=False,
            replacement=message_chain
        )
