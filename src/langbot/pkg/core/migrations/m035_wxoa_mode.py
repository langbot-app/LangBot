from __future__ import annotations

from .. import migration


@migration.migration_class('wxoa-mode', 35)
class WxoaModeMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""

        for adapter in self.ap.platform_cfg.data['platform-adapters']:
            if adapter['adapter'] == 'officialaccount':
                if 'Mode' not in adapter:
                    return True
        return False

    async def run(self):
        """执行迁移"""
        for adapter in self.ap.platform_cfg.data['platform-adapters']:
            if adapter['adapter'] == 'officialaccount':
                if 'Mode' not in adapter:
                    adapter['Mode'] = 'drop'

        await self.ap.platform_cfg.dump_config()
