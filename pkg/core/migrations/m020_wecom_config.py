from __future__ import annotations

from .. import migration


@migration.migration_class('wecom-config', 20)
class WecomConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""

        # for adapter in self.ap.platform_cfg.data['platform-adapters']:
        #     if adapter['adapter'] == 'wecom':
        #         return False

        # return True
        return False

    async def run(self):
        """执行迁移"""
        self.ap.platform_cfg.data['platform-adapters'].append(
            {
                'adapter': 'wecom',
                'enable': False,
                'host': '0.0.0.0',
                'port': 2290,
                'corpid': '',
                'secret': '',
                'token': '',
                'EncodingAESKey': '',
                'contacts_secret': '',
            }
        )

        await self.ap.platform_cfg.dump_config()
