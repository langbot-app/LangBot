context = {
    'inst': {
        'database.manager.DatabaseManager': None,
        'openai.manager.OpenAIInteract': None,
        'qqbot.manager.QQBotManager': None,
    },
    'logger_handler': None,
    'config': None,
    'plugin_host': None,
}


def set_config(inst):
    context['config'] = inst


def get_config():
    return context['config']


def set_database_manager(inst):
    context['inst']['database.manager.DatabaseManager'] = inst


def get_database_manager():
    return context['inst']['database.manager.DatabaseManager']


def set_openai_manager(inst):
    context['inst']['openai.manager.OpenAIInteract'] = inst


def get_openai_manager():
    return context['inst']['openai.manager.OpenAIInteract']


def set_qqbot_manager(inst):
    context['inst']['qqbot.manager.QQBotManager'] = inst


def get_qqbot_manager():
    return context['inst']['qqbot.manager.QQBotManager']


def set_plugin_host(inst):
    context['plugin_host'] = inst


def get_plugin_host():
    return context['plugin_host']
