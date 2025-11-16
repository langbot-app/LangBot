from __future__ import annotations

from .. import migration


@migration.migration_class('qqofficial-config', 26)
class QQOfficialConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""

        # for adapter in self.ap.platform_cfg.data['platform-adapters']:
        #     if adapter['adapter'] == 'qqofficial':
        #         return False

        # return True
        return False

    async def run(self):
        """执行迁移"""
        self.ap.platform_cfg.data['platform-adapters'].append(
            {
                'adapter': 'qqofficial',
                'enable': False,
                'appid': '',
                'secret': '',
                'port': 2284,
                'token': '',
            }
        )

        await self.ap.platform_cfg.dump_config()
