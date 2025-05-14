from __future__ import annotations

from .. import migration


@migration.migration_class('qcg-center-url-config', 7)
class QCGCenterURLConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return 'qcg-center-url' not in self.ap.system_cfg.data

    async def run(self):
        """执行迁移"""

        if 'qcg-center-url' not in self.ap.system_cfg.data:
            self.ap.system_cfg.data['qcg-center-url'] = 'https://api.qchatgpt.rockchin.top/api/v2'

        await self.ap.system_cfg.dump_config()
