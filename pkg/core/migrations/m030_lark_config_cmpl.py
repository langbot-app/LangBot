from __future__ import annotations

from .. import migration


@migration.migration_class('lark-config-cmpl', 30)
class LarkConfigCmplMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""

        for adapter in self.ap.platform_cfg.data['platform-adapters']:
            if adapter['adapter'] == 'lark':
                if 'enable-webhook' not in adapter:
                    return True

        return False

    async def run(self):
        """执行迁移"""
        for adapter in self.ap.platform_cfg.data['platform-adapters']:
            if adapter['adapter'] == 'lark':
                if 'enable-webhook' not in adapter:
                    adapter['enable-webhook'] = False
                if 'port' not in adapter:
                    adapter['port'] = 2285
                if 'encrypt-key' not in adapter:
                    adapter['encrypt-key'] = 'xxxxxxxxx'

        await self.ap.platform_cfg.dump_config()
