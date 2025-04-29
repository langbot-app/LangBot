from __future__ import annotations

from .. import migration


@migration.migration_class('runner-config', 12)
class RunnerConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return 'runner' not in self.ap.provider_cfg.data

    async def run(self):
        """执行迁移"""

        self.ap.provider_cfg.data['runner'] = 'local-agent'

        await self.ap.provider_cfg.dump_config()
