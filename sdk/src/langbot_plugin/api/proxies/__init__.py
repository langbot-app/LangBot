"""此包包含了对于 LangBot 向插件提供的 API 的代理类。"""

from langbot_plugin.api.proxies.langbot_api import LangBotAPIProxy
from langbot_plugin.api.proxies.workspace import WorkspaceOperationsProxy
from langbot_plugin.api.proxies.runner import (
    RunnerAdminAPIProxy,
    RunnerAPIProxy,
)

__all__ = [
    "LangBotAPIProxy",
    "RunnerAPIProxy",
    "RunnerAdminAPIProxy",
    "WorkspaceOperationsProxy",
]
