from __future__ import annotations

import threading
from . import threadctl

from ..database import manager as db_mgr
from ..openai import manager as openai_mgr
from ..qqbot import manager as qqbot_mgr
from ..config import  manager as config_mgr
from ..plugin import host as plugin_host
from .center import v2 as center_v2


context = {
    'inst': {
        'database.manager.DatabaseManager': None,
        'openai.manager.OpenAIInteract': None,
        'qqbot.manager.QQBotManager': None,
        'config.manager.ConfigManager': None,
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


def set_database_manager(inst: db_mgr.DatabaseManager):
    context_lock.acquire()
    context['inst']['database.manager.DatabaseManager'] = inst
    context_lock.release()


def get_database_manager() -> db_mgr.DatabaseManager:
    context_lock.acquire()
    t = context['inst']['database.manager.DatabaseManager']
    context_lock.release()
    return t


def set_openai_manager(inst: openai_mgr.OpenAIInteract):
    context_lock.acquire()
    context['inst']['openai.manager.OpenAIInteract'] = inst
    context_lock.release()


def get_openai_manager() -> openai_mgr.OpenAIInteract:
    context_lock.acquire()
    t = context['inst']['openai.manager.OpenAIInteract']
    context_lock.release()
    return t


def set_qqbot_manager(inst: qqbot_mgr.QQBotManager):
    context_lock.acquire()
    context['inst']['qqbot.manager.QQBotManager'] = inst
    context_lock.release()


def get_qqbot_manager() -> qqbot_mgr.QQBotManager:
    context_lock.acquire()
    t = context['inst']['qqbot.manager.QQBotManager']
    context_lock.release()
    return t


def set_config_manager(inst: config_mgr.ConfigManager):
    context_lock.acquire()
    context['inst']['config.manager.ConfigManager'] = inst
    context_lock.release()


def get_config_manager() -> config_mgr.ConfigManager:
    context_lock.acquire()
    t = context['inst']['config.manager.ConfigManager']
    context_lock.release()
    return t


def set_plugin_host(inst: plugin_host.PluginHost):
    context_lock.acquire()
    context['plugin_host'] = inst
    context_lock.release()


def get_plugin_host() -> plugin_host.PluginHost:
    context_lock.acquire()
    t = context['plugin_host']
    context_lock.release()
    return t


def set_thread_ctl(inst: threadctl.ThreadCtl):
    context_lock.acquire()
    context['pool_ctl'] = inst
    context_lock.release()


def get_thread_ctl() -> threadctl.ThreadCtl:
    context_lock.acquire()
    t: threadctl.ThreadCtl = context['pool_ctl']
    context_lock.release()
    return t


def set_center_v2_api(inst: center_v2.V2CenterAPI):
    context_lock.acquire()
    context['center_v2_api'] = inst
    context_lock.release()


def get_center_v2_api() -> center_v2.V2CenterAPI:
    context_lock.acquire()
    t: center_v2.V2CenterAPI = context['center_v2_api']
    context_lock.release()
    return t