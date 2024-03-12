from __future__ import annotations

import mirai

from ...core import app
from . import entities as rule_entities, rule
from .rules import atbot, prefix, regexp, random

from .. import stage, entities, stagemgr
from ...core import entities as core_entities
from ...config import manager as cfg_mgr


@stage.stage_class("GroupRespondRuleCheckStage")
class GroupRespondRuleCheckStage(stage.PipelineStage):
    """群组响应规则检查器
    """

    rule_matchers: list[rule.GroupRespondRule]

    async def initialize(self):
        """初始化检查器
        """

        self.rule_matchers = []

        for rule_matcher in rule.preregisetered_rules:
            rule_inst = rule_matcher(self.ap)
            await rule_inst.initialize()
            self.rule_matchers.append(rule_inst)

    async def process(self, query: core_entities.Query, stage_inst_name: str) -> entities.StageProcessResult:
        
        if query.launcher_type.value != 'group':
            return entities.StageProcessResult(
                result_type=entities.ResultType.CONTINUE,
                new_query=query
            )

        rules = self.ap.pipeline_cfg.data['respond-rules']

        use_rule = rules['default']

        if str(query.launcher_id) in use_rule:
            use_rule = use_rule[str(query.launcher_id)]

        for rule_matcher in self.rule_matchers:  # 任意一个匹配就放行
            res = await rule_matcher.match(str(query.message_chain), query.message_chain, use_rule, query)
            if res.matching:
                query.message_chain = res.replacement

                return entities.StageProcessResult(
                    result_type=entities.ResultType.CONTINUE,
                    new_query=query,
                )
        
        return entities.StageProcessResult(
            result_type=entities.ResultType.INTERRUPT,
            new_query=query
        )
