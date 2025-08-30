from .. import migration


@migration.migration_class(4)
class DBMigratePluginConfig(migration.DBMigration):
    """插件配置"""

    async def upgrade(self):
        """升级"""

        if 'plugin' not in self.ap.instance_config.data:
            self.ap.instance_config.data['plugin'] = {
                'runtime_ws_url': 'ws://localhost:5400/control/ws',
            }

            await self.ap.instance_config.dump_config()

    async def downgrade(self):
        """降级"""
        pass
