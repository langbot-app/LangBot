from __future__ import annotations


from . import rule

from .. import stage, entities
from ...utils import importutil

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

from . import rules

importutil.import_modules_in_pkg(rules)


@stage.stage_class('GroupRespondRuleCheckStage')
class GroupRespondRuleCheckStage(stage.PipelineStage):
    """群组响应规则检查器

    仅检查群消息是否符合规则。
    """

    rule_matchers: list[rule.GroupRespondRule]
    """检查器实例"""

    async def initialize(self, pipeline_config: dict):
        """初始化检查器"""

        self.rule_matchers = []

        for rule_matcher in rule.preregisetered_rules:
            rule_inst = rule_matcher(self.ap)
            await rule_inst.initialize()
            self.rule_matchers.append(rule_inst)

    async def process(self, query: pipeline_query.Query, stage_inst_name: str) -> entities.StageProcessResult:
        if query.launcher_type.value != 'group':  # 只处理群消息
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        rules = query.pipeline_config['trigger']['group-respond-rules']

        use_rule = rules

        # TODO revert it
        # if str(query.launcher_id) in rules:
        #     use_rule = rules[str(query.launcher_id)]

        for rule_matcher in self.rule_matchers:  # 任意一个匹配就放行
            res = await rule_matcher.match(str(query.message_chain), query.message_chain, use_rule, query)
            if res.matching:
                query.message_chain = res.replacement

                return entities.StageProcessResult(
                    result_type=entities.ResultType.CONTINUE,
                    new_query=query,
                )

        return entities.StageProcessResult(result_type=entities.ResultType.INTERRUPT, new_query=query)
