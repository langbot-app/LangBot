from __future__ import annotations

import traceback

import sqlalchemy

from ..core import app, taskmgr
from . import context, loader, events, installer, models
from .loaders import classic, manifest
from .installers import github
from ..entity.persistence import plugin as persistence_plugin


class PluginManager:
    """插件管理器"""

    ap: app.Application

    loaders: list[loader.PluginLoader]

    installer: installer.PluginInstaller

    api_host: context.APIHost

    plugin_containers: list[context.RuntimeContainer]

    def plugins(
        self,
        enabled: bool = None,
        status: context.RuntimeContainerStatus = None,
    ) -> list[context.RuntimeContainer]:
        """获取插件列表"""
        plugins = self.plugin_containers

        if enabled is not None:
            plugins = [plugin for plugin in plugins if plugin.enabled == enabled]

        if status is not None:
            plugins = [plugin for plugin in plugins if plugin.status == status]

        return plugins

    def get_plugin(
        self,
        author: str,
        plugin_name: str,
    ) -> context.RuntimeContainer:
        """通过作者和插件名获取插件"""
        for plugin in self.plugins():
            if plugin.plugin_author == author and plugin.plugin_name == plugin_name:
                return plugin
        return None

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.loaders = [
            classic.PluginLoader(ap),
            manifest.PluginManifestLoader(ap),
        ]
        self.installer = github.GitHubRepoInstaller(ap)
        self.api_host = context.APIHost(ap)
        self.plugin_containers = []

    async def initialize(self):
        for loader in self.loaders:
            await loader.initialize()
        await self.installer.initialize()
        await self.api_host.initialize()

        setattr(models, 'require_ver', self.api_host.require_ver)

    async def load_plugins(self):
        self.ap.logger.info('Loading all plugins...')

        for loader in self.loaders:
            await loader.load_plugins()
            self.plugin_containers.extend(loader.plugins)

        await self.load_plugin_settings(self.plugin_containers)

        # 按优先级倒序
        self.plugin_containers.sort(key=lambda x: x.priority, reverse=False)

        self.ap.logger.debug(f'优先级排序后的插件列表 {self.plugin_containers}')

    async def load_plugin_settings(self, plugin_containers: list[context.RuntimeContainer]):
        for plugin_container in plugin_containers:
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_plugin.PluginSetting)
                .where(persistence_plugin.PluginSetting.plugin_author == plugin_container.plugin_author)
                .where(persistence_plugin.PluginSetting.plugin_name == plugin_container.plugin_name)
            )

            setting = result.first()

            if setting is None:
                new_setting_data = {
                    'plugin_author': plugin_container.plugin_author,
                    'plugin_name': plugin_container.plugin_name,
                    'enabled': plugin_container.enabled,
                    'priority': plugin_container.priority,
                    'config': plugin_container.plugin_config,
                }

                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.insert(persistence_plugin.PluginSetting).values(**new_setting_data)
                )
                continue
            else:
                plugin_container.enabled = setting.enabled
                plugin_container.priority = setting.priority
                plugin_container.plugin_config = setting.config

    async def dump_plugin_container_setting(self, plugin_container: context.RuntimeContainer):
        """保存单个插件容器的设置到数据库"""
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_plugin.PluginSetting)
            .where(persistence_plugin.PluginSetting.plugin_author == plugin_container.plugin_author)
            .where(persistence_plugin.PluginSetting.plugin_name == plugin_container.plugin_name)
            .values(
                enabled=plugin_container.enabled,
                priority=plugin_container.priority,
                config=plugin_container.plugin_config,
            )
        )

    async def initialize_plugin(self, plugin: context.RuntimeContainer):
        self.ap.logger.debug(f'初始化插件 {plugin.plugin_name}')
        plugin.plugin_inst = plugin.plugin_class(self.api_host)
        plugin.plugin_inst.config = plugin.plugin_config
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
        plugin.plugin_inst.__del__()
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
        """安装插件"""
        await self.installer.install_plugin(plugin_source, task_context)

        # TODO statistics

        task_context.trace('重载插件..', 'reload-plugin')
        await self.ap.reload(scope='plugin')

    async def uninstall_plugin(
        self,
        plugin_name: str,
        task_context: taskmgr.TaskContext = taskmgr.TaskContext.placeholder(),
    ):
        """卸载插件"""

        plugin_container = self.get_plugin_by_name(plugin_name)

        if plugin_container is None:
            raise ValueError(f'插件 {plugin_name} 不存在')

        await self.destroy_plugin(plugin_container)
        await self.installer.uninstall_plugin(plugin_name, task_context)

        # TODO statistics

        task_context.trace('重载插件..', 'reload-plugin')
        await self.ap.reload(scope='plugin')

    async def update_plugin(
        self,
        plugin_name: str,
        plugin_source: str = None,
        task_context: taskmgr.TaskContext = taskmgr.TaskContext.placeholder(),
    ):
        """更新插件"""
        await self.installer.update_plugin(plugin_name, plugin_source, task_context)

        # TODO statistics

        task_context.trace('重载插件..', 'reload-plugin')
        await self.ap.reload(scope='plugin')

    def get_plugin_by_name(self, plugin_name: str) -> context.RuntimeContainer:
        """通过插件名获取插件"""
        for plugin in self.plugins():
            if plugin.plugin_name == plugin_name:
                return plugin
        return None

    async def emit_event(self, event: events.BaseEventModel) -> context.EventContext:
        """触发事件"""

        ctx = context.EventContext(host=self.api_host, event=event)

        emitted_plugins: list[context.RuntimeContainer] = []

        for plugin in self.plugins(enabled=True, status=context.RuntimeContainerStatus.INITIALIZED):
            if event.__class__ in plugin.event_handlers:
                self.ap.logger.debug(f'插件 {plugin.plugin_name} 处理事件 {event.__class__.__name__}')

                is_prevented_default_before_call = ctx.is_prevented_default()

                try:
                    await plugin.event_handlers[event.__class__](plugin.plugin_inst, ctx)
                except Exception as e:
                    self.ap.logger.error(
                        f'插件 {plugin.plugin_name} 处理事件 {event.__class__.__name__} 时发生错误: {e}'
                    )
                    self.ap.logger.debug(f'Traceback: {traceback.format_exc()}')

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

        # TODO statistics

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

                    await self.dump_plugin_container_setting(plugin)

                    break

            return True
        else:
            return False

    async def reorder_plugins(self, plugins: list[dict]):
        for plugin in plugins:
            plugin_name = plugin.get('name')
            plugin_priority = plugin.get('priority')

            for plugin in self.plugin_containers:
                if plugin.plugin_name == plugin_name:
                    plugin.priority = plugin_priority
                    break

        self.plugin_containers.sort(key=lambda x: x.priority, reverse=False)

        for plugin in self.plugin_containers:
            await self.dump_plugin_container_setting(plugin)

    async def set_plugin_config(self, plugin_container: context.RuntimeContainer, new_config: dict):
        plugin_container.plugin_config = new_config

        plugin_container.plugin_inst.config = new_config

        await self.dump_plugin_container_setting(plugin_container)
