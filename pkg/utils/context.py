import threading
from pkg.utils import ThreadCtl


context = {
    'inst': {
        'database.manager.DatabaseManager': None,
        'openai.manager.OpenAIInteract': None,
        'qqbot.manager.QQBotManager': None,
    },
    'pool_ctl': None,
    'logger_handler': None,
    'config': None,
    'plugin_host': None,
}
context_lock = threading.Lock()

### context耦合度非常高，需要大改 ###
def set_config(inst):
    context_lock.acquire()
    context['config'] = inst
    context_lock.release()


def get_config():
    context_lock.acquire()
    t = context['config']
    context_lock.release()
    return t


def set_database_manager(inst):
    context_lock.acquire()
    context['inst']['database.manager.DatabaseManager'] = inst
    context_lock.release()


def get_database_manager():
    context_lock.acquire()
    t = context['inst']['database.manager.DatabaseManager']
    context_lock.release()
    return t


def set_openai_manager(inst):
    context_lock.acquire()
    context['inst']['openai.manager.OpenAIInteract'] = inst
    context_lock.release()


def get_openai_manager():
    context_lock.acquire()
    t = context['inst']['openai.manager.OpenAIInteract']
    context_lock.release()
    return t


def set_qqbot_manager(inst):
    context_lock.acquire()
    context['inst']['qqbot.manager.QQBotManager'] = inst
    context_lock.release()


def get_qqbot_manager():
    context_lock.acquire()
    t = context['inst']['qqbot.manager.QQBotManager']
    context_lock.release()
    return t


def set_plugin_host(inst):
    context_lock.acquire()
    context['plugin_host'] = inst
    context_lock.release()


def get_plugin_host():
    context_lock.acquire()
    t = context['plugin_host']
    context_lock.release()
    return t


def set_thread_ctl(inst):
    context_lock.acquire()
    context['pool_ctl'] = inst
    context_lock.release()


def get_thread_ctl() -> ThreadCtl:
    context_lock.acquire()
    t: ThreadCtl = context['pool_ctl']
    context_lock.release()
    return t
