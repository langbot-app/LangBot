from __future__ import annotations

from .. import migration


@migration.migration_class('mcp-config', 37)
class MCPConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return 'mcp' not in self.ap.provider_cfg.data

    async def run(self):
        """执行迁移"""
        self.ap.provider_cfg.data['mcp'] = {'servers': []}

        await self.ap.provider_cfg.dump_config()
