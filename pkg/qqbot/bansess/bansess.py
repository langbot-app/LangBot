# 处理对会话的禁用配置
# 过去的 banlist
from __future__ import annotations
import re

from ...boot import app
from ...config import manager as cfg_mgr


class SessionBanManager:
    
    ap: app.Application = None

    banlist_mgr: cfg_mgr.ConfigManager

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        self.banlist_mgr = await cfg_mgr.load_python_module_config(
            "banlist.py",
            "res/templates/banlist-template.py"
        )

    async def is_banned(
        self, launcher_type: str, launcher_id: int, sender_id: int
    ) -> bool:
        if not self.banlist_mgr.data['enable']:
            return False
        
        result = False

        if launcher_type == 'group':
            if not self.banlist_mgr.data['enable_group']:  # 未启用群聊响应
                result = True
            # 检查是否显式声明发起人QQ要被person忽略
            elif sender_id in self.banlist_mgr.data['person']:
                result = True
            else:
                for group_rule in self.banlist_mgr.data['group']:
                    if type(group_rule) == int:
                        if group_rule == launcher_id:
                            result = True
                    elif type(group_rule) == str:
                        if group_rule.startswith('!'):
                            reg_str = group_rule[1:]
                            if re.match(reg_str, str(launcher_id)):
                                result = False
                                break
                        else:
                            if re.match(group_rule, str(launcher_id)):
                                result = True
        elif launcher_type == 'person':
            if not self.banlist_mgr.data['enable_private']:
                result = True
            else:
                for person_rule in self.banlist_mgr.data['person']:
                    if type(person_rule) == int:
                        if person_rule == launcher_id:
                            result = True
                    elif type(person_rule) == str:
                        if person_rule.startswith('!'):
                            reg_str = person_rule[1:]
                            if re.match(reg_str, str(launcher_id)):
                                result = False
                                break
                        else:
                            if re.match(person_rule, str(launcher_id)):
                                result = True
        return result
