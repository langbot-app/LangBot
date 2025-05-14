from __future__ import annotations

from .. import migration


@migration.migration_class('discord-config', 24)
class DiscordConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""

        # for adapter in self.ap.platform_cfg.data['platform-adapters']:
        #     if adapter['adapter'] == 'discord':
        #         return False

        # return True
        return False

    async def run(self):
        """执行迁移"""
        self.ap.platform_cfg.data['platform-adapters'].append(
            {
                'adapter': 'discord',
                'enable': False,
                'client_id': '1234567890',
                'token': 'XXXXXXXXXX',
            }
        )

        await self.ap.platform_cfg.dump_config()
