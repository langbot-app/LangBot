from __future__ import annotations

from .. import migration


@migration.migration_class('force-delay-config', 14)
class ForceDelayConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return isinstance(self.ap.platform_cfg.data['force-delay'], list)

    async def run(self):
        """执行迁移"""

        self.ap.platform_cfg.data['force-delay'] = {
            'min': self.ap.platform_cfg.data['force-delay'][0],
            'max': self.ap.platform_cfg.data['force-delay'][1],
        }

        await self.ap.platform_cfg.dump_config()
