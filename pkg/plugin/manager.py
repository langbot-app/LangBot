from __future__ import annotations

import typing

from ..core import app
from . import context, loader, events, installer, setting, models
from .loaders import legacy
from .installers import github


class PluginManager:

    ap: app.Application

    loader: loader.PluginLoader

    installer: installer.PluginInstaller

    setting: setting.SettingManager

    api_host: context.APIHost

    plugins: list[context.RuntimeContainer]

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.loader = legacy.PluginLoader(ap)
        self.installer = github.GitHubRepoInstaller(ap)
        self.setting = setting.SettingManager(ap)
        self.api_host = context.APIHost(ap)
        self.plugins = []

    async def initialize(self):
        await self.loader.initialize()
        await self.installer.initialize()
        await self.setting.initialize()
        await self.api_host.initialize()

        setattr(models, 'require_ver', self.api_host.require_ver)

    async def load_plugins(self):
        self.plugins = await self.loader.load_plugins()

        await self.setting.sync_setting(self.plugins)

        # 按优先级倒序
        self.plugins.sort(key=lambda x: x.priority, reverse=True)

    async def initialize_plugins(self):
        for plugin in self.plugins:
            try:
                plugin.plugin_inst = plugin.plugin_class(self.api_host)
            except Exception as e:
                self.ap.logger.error(f'插件 {plugin.plugin_name} 初始化失败: {e}')
                self.ap.logger.exception(e)
                continue

    async def install_plugin(
        self,
        plugin_source: str,
    ):
        """安装插件
        """
        await self.installer.install_plugin(plugin_source)

    async def uninstall_plugin(
        self,
        plugin_name: str,
    ):
        """卸载插件
        """
        await self.installer.uninstall_plugin(plugin_name)

    async def update_plugin(
        self,
        plugin_name: str,
        plugin_source: str=None,
    ):
        """更新插件
        """
        await self.installer.update_plugin(plugin_name, plugin_source)

    def get_plugin_by_name(self, plugin_name: str) -> context.RuntimeContainer:
        """通过插件名获取插件
        """
        for plugin in self.plugins:
            if plugin.plugin_name == plugin_name:
                return plugin
        return None

    async def emit_event(self, event: events.BaseEventModel) -> context.EventContext:
        """触发事件
        """

        ctx = context.EventContext(
            host=self.api_host,
            event=event
        )
        
        for plugin in self.plugins:
            if plugin.enabled:
                if event.__class__ in plugin.event_handlers:
                    try:
                        await plugin.event_handlers[event.__class__](
                            plugin.plugin_inst,
                            ctx
                        )
                    except Exception as e:
                        self.ap.logger.error(f'插件 {plugin.plugin_name} 触发事件 {event.__class__.__name__} 时发生错误: {e}')
                        self.ap.logger.exception(e)
                    
                    if ctx.is_prevented_postorder():
                        self.ap.logger.debug(f'插件 {plugin.plugin_name} 阻止了后序插件的执行')
                        break
        
        self.ap.logger.debug(f'事件 {event.__class__.__name__}({ctx.eid}) 处理完成，返回值 {ctx.__return_value__}')

        return ctx