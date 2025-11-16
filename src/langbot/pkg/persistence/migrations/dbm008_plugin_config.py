from .. import migration


@migration.migration_class(8)
class DBMigratePluginConfig(migration.DBMigration):
    """插件配置"""

    async def upgrade(self):
        """升级"""

        if 'plugin' not in self.ap.instance_config.data:
            self.ap.instance_config.data['plugin'] = {
                'runtime_ws_url': 'ws://langbot_plugin_runtime:5400/control/ws',
                'enable_marketplace': True,
                'cloud_service_url': 'https://space.langbot.app',
            }

            await self.ap.instance_config.dump_config()

    async def downgrade(self):
        """降级"""
        pass
