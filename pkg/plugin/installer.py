from __future__ import annotations

import abc

from ..core import app, taskmgr


class PluginInstaller(metaclass=abc.ABCMeta):
    """插件安装器抽象类"""

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def install_plugin(
        self,
        plugin_source: str,
        task_context: taskmgr.TaskContext = taskmgr.TaskContext.placeholder(),
    ):
        """安装插件"""
        raise NotImplementedError

    @abc.abstractmethod
    async def uninstall_plugin(
        self,
        plugin_name: str,
        task_context: taskmgr.TaskContext = taskmgr.TaskContext.placeholder(),
    ):
        """卸载插件"""
        raise NotImplementedError

    @abc.abstractmethod
    async def update_plugin(
        self,
        plugin_name: str,
        plugin_source: str = None,
        task_context: taskmgr.TaskContext = taskmgr.TaskContext.placeholder(),
    ):
        """更新插件"""
        raise NotImplementedError
