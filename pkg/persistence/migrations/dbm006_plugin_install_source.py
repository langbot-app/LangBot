import sqlalchemy
from .. import migration


@migration.migration_class(6)
class DBMigratePluginInstallSource(migration.DBMigration):
    """插件安装来源"""

    async def upgrade(self):
        """升级"""
        # 查询表结构获取所有列名（异步执行 SQL）
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.text('PRAGMA table_info(plugin_settings);'))
        # fetchall() 是同步方法，无需 await
        columns = [row[1] for row in result.fetchall()]

        # 检查并添加 install_source 列
        if 'install_source' not in columns:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    "ALTER TABLE plugin_settings ADD COLUMN install_source VARCHAR(255) NOT NULL DEFAULT 'github'"
                )
            )

        # 检查并添加 install_info 列
        if 'install_info' not in columns:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("ALTER TABLE plugin_settings ADD COLUMN install_info JSON NOT NULL DEFAULT '{}'")
            )

    async def downgrade(self):
        """降级"""
        pass
