from __future__ import annotations

from .. import migration


@migration.migration_class('wx-official-account-config', 27)
class WXOfficialAccountConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""

        # for adapter in self.ap.platform_cfg.data['platform-adapters']:
        #     if adapter['adapter'] == 'officialaccount':
        #         return False

        # return True
        return False

    async def run(self):
        """执行迁移"""
        self.ap.platform_cfg.data['platform-adapters'].append(
            {
                'adapter': 'officialaccount',
                'enable': False,
                'token': '',
                'EncodingAESKey': '',
                'AppID': '',
                'AppSecret': '',
                'host': '0.0.0.0',
                'port': 2287,
            }
        )

        await self.ap.platform_cfg.dump_config()
