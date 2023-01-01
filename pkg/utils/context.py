context = {
    'inst': {
        'database.manager.DatabaseManager': None,
        'openai.manager.OpenAIInteract': None,
        'qqbot.manager.QQBotManager': None,
    }
}


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