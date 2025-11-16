from __future__ import annotations

from .. import migration


@migration.migration_class('lark-config', 21)
class LarkConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""

        # for adapter in self.ap.platform_cfg.data['platform-adapters']:
        #     if adapter['adapter'] == 'lark':
        #         return False

        # return True
        return False

    async def run(self):
        """执行迁移"""
        self.ap.platform_cfg.data['platform-adapters'].append(
            {
                'adapter': 'lark',
                'enable': False,
                'app_id': 'cli_abcdefgh',
                'app_secret': 'XXXXXXXXXX',
                'bot_name': 'LangBot',
                'enable-webhook': False,
                'port': 2285,
                'encrypt-key': 'xxxxxxxxx',
            }
        )

        await self.ap.platform_cfg.dump_config()
