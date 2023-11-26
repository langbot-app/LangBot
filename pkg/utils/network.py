from . import context


def wrapper_proxies() -> dict:
    """获取代理"""
    config = context.get_config_manager().data

    return {
        "http": config['openai_config']['proxy'],
        "https": config['openai_config']['proxy']
    } if 'proxy' in config['openai_config'] and (config['openai_config']['proxy'] is not None) else None
