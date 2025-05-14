from __future__ import annotations

from .. import migration


@migration.migration_class('http-api-config', 13)
class HttpApiConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return 'http-api' not in self.ap.system_cfg.data or 'persistence' not in self.ap.system_cfg.data

    async def run(self):
        """执行迁移"""

        self.ap.system_cfg.data['http-api'] = {
            'enable': True,
            'host': '0.0.0.0',
            'port': 5300,
            'jwt-expire': 604800,
        }

        self.ap.system_cfg.data['persistence'] = {
            'sqlite': {'path': 'data/persistence.db'},
            'use': 'sqlite',
        }

        await self.ap.system_cfg.dump_config()
