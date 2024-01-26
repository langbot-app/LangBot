from __future__ import annotations
import re

from .. import stage, entities, stagemgr
from ...core import entities as core_entities
from ...config import manager as cfg_mgr


@stage.stage_class('BanSessionCheckStage')
class BanSessionCheckStage(stage.PipelineStage):

    banlist_mgr: cfg_mgr.ConfigManager

    async def initialize(self):
        self.banlist_mgr = await cfg_mgr.load_python_module_config(
            "banlist.py",
            "res/templates/banlist-template.py"
        )

    async def process(
        self,
        query: core_entities.Query,
        stage_inst_name: str
    ) -> entities.StageProcessResult:
        
        if not self.banlist_mgr.data['enable']:
            return entities.StageProcessResult(
                result_type=entities.ResultType.CONTINUE,
                new_query=query
            )
        
        result = False

        if query.launcher_type == 'group':
            if not self.banlist_mgr.data['enable_group']:  # 未启用群聊响应
                result = True
            # 检查是否显式声明发起人QQ要被person忽略
            elif query.sender_id in self.banlist_mgr.data['person']:
                result = True
            else:
                for group_rule in self.banlist_mgr.data['group']:
                    if type(group_rule) == int:
                        if group_rule == query.launcher_id:
                            result = True
                    elif type(group_rule) == str:
                        if group_rule.startswith('!'):
                            reg_str = group_rule[1:]
                            if re.match(reg_str, str(query.launcher_id)):
                                result = False
                                break
                        else:
                            if re.match(group_rule, str(query.launcher_id)):
                                result = True
        elif query.launcher_type == 'person':
            if not self.banlist_mgr.data['enable_private']:
                result = True
            else:
                for person_rule in self.banlist_mgr.data['person']:
                    if type(person_rule) == int:
                        if person_rule == query.launcher_id:
                            result = True
                    elif type(person_rule) == str:
                        if person_rule.startswith('!'):
                            reg_str = person_rule[1:]
                            if re.match(reg_str, str(query.launcher_id)):
                                result = False
                                break
                        else:
                            if re.match(person_rule, str(query.launcher_id)):
                                result = True

        return entities.StageProcessResult(
            result_type=entities.ResultType.CONTINUE if not result else entities.ResultType.INTERRUPT,
            new_query=query,
            debug_notice=f'根据禁用列表忽略消息: {query.launcher_type}_{query.launcher_id}' if result else ''
        )
