from ..utils import context


# 检查消息是否符合泛响应匹配机制
def check_response_rule(group_id:int, text: str):
    config = context.get_config_manager().data

    rules = config['response_rules']

    # 检查是否有特定规则
    if 'prefix' not in config['response_rules']:
        if str(group_id) in config['response_rules']:
            rules = config['response_rules'][str(group_id)]
        else:
            rules = config['response_rules']['default']

    # 检查前缀匹配
    if 'prefix' in rules:
        for rule in rules['prefix']:
            if text.startswith(rule):
                return True, text.replace(rule, "", 1)

    # 检查正则表达式匹配
    if 'regexp' in rules:
        for rule in rules['regexp']:
            import re
            match = re.match(rule, text)
            if match:
                return True, text

    return False, ""


def response_at(group_id: int):
    config = context.get_config_manager().data

    use_response_rule = config['response_rules']

    # 检查是否有特定规则
    if 'prefix' not in config['response_rules']:
        if str(group_id) in config['response_rules']:
            use_response_rule = config['response_rules'][str(group_id)]
        else:
            use_response_rule = config['response_rules']['default']

    if 'at' not in use_response_rule:
        return True

    return use_response_rule['at']


def random_responding(group_id):
    config = context.get_config_manager().data

    use_response_rule = config['response_rules']

    # 检查是否有特定规则
    if 'prefix' not in config['response_rules']:
        if str(group_id) in config['response_rules']:
            use_response_rule = config['response_rules'][str(group_id)]
        else:
            use_response_rule = config['response_rules']['default']

    if 'random_rate' in use_response_rule:
        import random
        return random.random() < use_response_rule['random_rate']
    return False
