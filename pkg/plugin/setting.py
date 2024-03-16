from __future__ import annotations

from ..core import app
from ..config import manager as cfg_mgr
from . import context


class SettingManager:
    """插件设置管理器"""

    ap: app.Application

    settings: cfg_mgr.ConfigManager

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        self.settings = self.ap.plugin_setting_meta

    async def sync_setting(
        self,
        plugin_containers: list[context.RuntimeContainer],
    ):
        """同步设置
        """

        not_matched_source_record = []

        for value in self.settings.data['plugins']:
            
            if 'name' not in value:  # 只有远程地址的，应用到pkg_path相同的插件容器上
                matched = False

                for plugin_container in plugin_containers:
                    if plugin_container.pkg_path == value['pkg_path']:
                        matched = True

                        plugin_container.plugin_source = value['source']
                        break

                if not matched:
                    not_matched_source_record.append(value)
            else:  # 正常的插件设置
                for plugin_container in plugin_containers:
                    if plugin_container.plugin_name == value['name']:
                        plugin_container.set_from_setting_dict(value)

        self.settings.data = {
            'plugins': [
                p.to_setting_dict()
                for p in plugin_containers
            ]
        }

        self.settings.data['plugins'].extend(not_matched_source_record)

        await self.settings.dump_config()

    async def dump_container_setting(
        self,
        plugin_containers: list[context.RuntimeContainer]
    ):
        """保存插件容器设置
        """

        for plugin in plugin_containers:
            for ps in self.settings.data['plugins']:
                if ps['name'] == plugin.plugin_name:
                    plugin_dict = plugin.to_setting_dict()

                    for key in plugin_dict:
                        ps[key] = plugin_dict[key]

                    break

        await self.settings.dump_config()

    async def record_installed_plugin_source(
        self,
        pkg_path: str,
        source: str
    ):
        found = False

        for value in self.settings.data['plugins']:
            if value['pkg_path'] == pkg_path:
                value['source'] = source
                found = True
                break
        
        if not found:
        
            self.settings.data['plugins'].append(
                {
                    'pkg_path': pkg_path,
                    'source': source
                }
            )
        await self.settings.dump_config()