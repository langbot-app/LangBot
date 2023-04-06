import re


def ignore(msg: str) -> bool:
    """检查消息是否应该被忽略"""
    import config
    
    if 'prefix' in config.ignore_rules:
        for rule in config.ignore_rules['prefix']:
            if msg.startswith(rule):
                return True

    if 'regexp' in config.ignore_rules:
        for rule in config.ignore_rules['regexp']:
            if re.search(rule, msg):
                return True
