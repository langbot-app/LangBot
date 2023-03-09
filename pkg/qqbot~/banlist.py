import pkg.utils.context


def is_banned(launcher_type: str, launcher_id: int, sender_id: int) -> bool:
    if not pkg.utils.context.get_qqbot_manager().enable_banlist:
        return False
    
    result = False
    
    if launcher_type == 'group':
        # 检查是否显式声明发起人QQ要被person忽略
        if sender_id in pkg.utils.context.get_qqbot_manager().ban_person:
            result = True
        else:
            for group_rule in pkg.utils.context.get_qqbot_manager().ban_group:
                if type(group_rule) == int:
                    if group_rule == launcher_id:  # 此群群号被禁用
                        result = True
                elif type(group_rule) == str:
                    if group_rule.startswith('!'):
                        # 截取!后面的字符串作为表达式，判断是否匹配
                        reg_str = group_rule[1:]
                        import re
                        if re.match(reg_str, str(launcher_id)):  # 被豁免，最高级别
                            result = False
                            break
                    else:
                        # 判断是否匹配regexp
                        import re
                        if re.match(group_rule, str(launcher_id)):  # 此群群号被禁用
                            result = True
                    
    else:
        # ban_person, 与群规则相同
        for person_rule in pkg.utils.context.get_qqbot_manager().ban_person:
            if type(person_rule) == int:
                if person_rule == launcher_id:
                    result = True
            elif type(person_rule) == str:
                if person_rule.startswith('!'):
                    reg_str = person_rule[1:]
                    import re
                    if re.match(reg_str, str(launcher_id)):
                        result = False
                        break
                else:
                    import re
                    if re.match(person_rule, str(launcher_id)):
                        result = True
    return result
