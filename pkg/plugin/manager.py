from __future__ import annotations

import typing
import traceback

from ..core import app, taskmgr
from . import context, loader, events, installer, setting, models
from .loaders import classic
from .installers import github


class PluginManager:
    """插件管理器"""

    ap: app.Application

    loader: loader.PluginLoader

    installer: installer.PluginInstaller

    setting: setting.SettingManager

    api_host: context.APIHost

    def plugins(
        self,
        enabled: bool=None,
        status: context.RuntimeContainerStatus=None,
    ) -> list[context.RuntimeContainer]:
        """获取插件列表
        """
        plugins = self.loader.plugins

        if enabled is not None:
            plugins = [plugin for plugin in plugins if plugin.enabled == enabled]
        
        if status is not None:
            plugins = [plugin for plugin in plugins if plugin.status == status]

        return plugins

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.loader = classic.PluginLoader(ap)
        self.installer = github.GitHubRepoInstaller(ap)
        self.setting = setting.SettingManager(ap)
        self.api_host = context.APIHost(ap)

    async def initialize(self):
        await self.loader.initialize()
        await self.installer.initialize()
        await self.setting.initialize()
        await self.api_host.initialize()

        setattr(models, 'require_ver', self.api_host.require_ver)

    async def load_plugins(self):
        await self.loader.load_plugins()

        await self.setting.sync_setting(self.loader.plugins)

        # 按优先级倒序
        self.loader.plugins.sort(key=lambda x: x.priority, reverse=True)

        self.ap.logger.debug(f'优先级排序后的插件列表 {self.loader.plugins}')

    async def initialize_plugin(self, plugin: context.RuntimeContainer):
        self.ap.logger.debug(f'初始化插件 {plugin.plugin_name}')
        plugin.plugin_inst = plugin.plugin_class(self.api_host)
        plugin.plugin_inst.ap = self.ap
        plugin.plugin_inst.host = self.api_host
        await plugin.plugin_inst.initialize()
        plugin.status = context.RuntimeContainerStatus.INITIALIZED

    async def initialize_plugins(self):
        for plugin in self.plugins():
            if not plugin.enabled:
                self.ap.logger.debug(f'插件 {plugin.plugin_name} 未启用，跳过初始化')
                continue
            try:
                await self.initialize_plugin(plugin)
            except Exception as e:
                self.ap.logger.error(f'插件 {plugin.plugin_name} 初始化失败: {e}')
                self.ap.logger.exception(e)
                continue

    async def destroy_plugin(self, plugin: context.RuntimeContainer):
        if plugin.status != context.RuntimeContainerStatus.INITIALIZED:
            return
        
        self.ap.logger.debug(f'释放插件 {plugin.plugin_name}')
        await plugin.plugin_inst.destroy()
        plugin.plugin_inst = None
        plugin.status = context.RuntimeContainerStatus.MOUNTED
    
    async def destroy_plugins(self):
        for plugin in self.plugins():
            if plugin.status != context.RuntimeContainerStatus.INITIALIZED:
                self.ap.logger.debug(f'插件 {plugin.plugin_name} 未初始化，跳过释放')
                continue

            try:
                await self.destroy_plugin(plugin)
            except Exception as e:
                self.ap.logger.error(f'插件 {plugin.plugin_name} 释放失败: {e}')
                self.ap.logger.exception(e)
                continue

    async def install_plugin(
        self,
        plugin_source: str,
        task_context: taskmgr.TaskContext = taskmgr.TaskContext.placeholder(),
    ):
        """安装插件
        """
        await self.installer.install_plugin(plugin_source, task_context)

        await self.ap.ctr_mgr.plugin.post_install_record(
            {
                "name": "unknown",
                "remote": plugin_source,
                "author": "unknown",
                "version": "HEAD"
            }
        )

    async def uninstall_plugin(
        self,
        plugin_name: str,
        task_context: taskmgr.TaskContext = taskmgr.TaskContext.placeholder(),
    ):
        """卸载插件
        """
        await self.installer.uninstall_plugin(plugin_name, task_context)

        plugin_container = self.get_plugin_by_name(plugin_name)

        await self.ap.ctr_mgr.plugin.post_remove_record(
            {
                "name": plugin_name,
                "remote": plugin_container.plugin_source,
                "author": plugin_container.plugin_author,
                "version": plugin_container.plugin_version
            }
        )

    async def update_plugin(
        self,
        plugin_name: str,
        plugin_source: str=None,
        task_context: taskmgr.TaskContext = taskmgr.TaskContext.placeholder(),
    ):
        """更新插件
        """
        await self.installer.update_plugin(plugin_name, plugin_source, task_context)
        
        plugin_container = self.get_plugin_by_name(plugin_name)

        await self.ap.ctr_mgr.plugin.post_update_record(
            plugin={
                "name": plugin_name,
                "remote": plugin_container.plugin_source,
                "author": plugin_container.plugin_author,
                "version": plugin_container.plugin_version
            },
            old_version=plugin_container.plugin_version,
            new_version="HEAD"
        )


    def get_plugin_by_name(self, plugin_name: str) -> context.RuntimeContainer:
        """通过插件名获取插件
        """
        for plugin in self.plugins():
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
        
        emitted_plugins: list[context.RuntimeContainer] = []

        for plugin in self.plugins(
            enabled=True,
            status=context.RuntimeContainerStatus.INITIALIZED
        ):
            if event.__class__ in plugin.event_handlers:
                self.ap.logger.debug(f'插件 {plugin.plugin_name} 处理事件 {event.__class__.__name__}')
                
                is_prevented_default_before_call = ctx.is_prevented_default()

                try:
                    await plugin.event_handlers[event.__class__](
                        plugin.plugin_inst,
                        ctx
                    )
                except Exception as e:
                    self.ap.logger.error(f'插件 {plugin.plugin_name} 处理事件 {event.__class__.__name__} 时发生错误: {e}')
                    self.ap.logger.debug(f"Traceback: {traceback.format_exc()}")
                
                emitted_plugins.append(plugin)

                if not is_prevented_default_before_call and ctx.is_prevented_default():
                    self.ap.logger.debug(f'插件 {plugin.plugin_name} 阻止了默认行为执行')

                if ctx.is_prevented_postorder():
                    self.ap.logger.debug(f'插件 {plugin.plugin_name} 阻止了后序插件的执行')
                    break

        for key in ctx.__return_value__.keys():
            if hasattr(ctx.event, key):
                setattr(ctx.event, key, ctx.__return_value__[key][0])
        
        self.ap.logger.debug(f'事件 {event.__class__.__name__}({ctx.eid}) 处理完成，返回值 {ctx.__return_value__}')

        if emitted_plugins:
            plugins_info: list[dict] = [
                {
                    'name': plugin.plugin_name,
                    'remote': plugin.plugin_source,
                    'version': plugin.plugin_version,
                    'author': plugin.plugin_author
                } for plugin in emitted_plugins
            ]

            await self.ap.ctr_mgr.usage.post_event_record(
                plugins=plugins_info,
                event_name=event.__class__.__name__
            )

        return ctx

    async def update_plugin_switch(self, plugin_name: str, new_status: bool):
        if self.get_plugin_by_name(plugin_name) is not None:
            for plugin in self.plugins():
                if plugin.plugin_name == plugin_name:
                    if plugin.enabled == new_status:
                        return False
                    
                    # 初始化/释放插件
                    if new_status:
                        await self.initialize_plugin(plugin)
                    else:
                        await self.destroy_plugin(plugin)

                    plugin.enabled = new_status
                    
                    await self.setting.dump_container_setting(self.loader.plugins)

                    break

            return True
        else:
            return False

    async def reorder_plugins(self, plugins: list[dict]):
        
        for plugin in plugins:
            plugin_name = plugin.get('name')
            plugin_priority = plugin.get('priority')

            for plugin in self.loader.plugins:
                if plugin.plugin_name == plugin_name:
                    plugin.priority = plugin_priority
                    break

        self.loader.plugins.sort(key=lambda x: x.priority, reverse=True)

        await self.setting.dump_container_setting(self.loader.plugins)
