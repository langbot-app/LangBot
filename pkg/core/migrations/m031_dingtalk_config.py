from __future__ import annotations

from .. import migration


@migration.migration_class('dingtalk-config', 31)
class DingTalkConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""

        # for adapter in self.ap.platform_cfg.data['platform-adapters']:
        #     if adapter['adapter'] == 'dingtalk':
        #         return False

        # return True
        return False

    async def run(self):
        """执行迁移"""
        self.ap.platform_cfg.data['platform-adapters'].append(
            {
                'adapter': 'dingtalk',
                'enable': False,
                'client_id': '',
                'client_secret': '',
                'robot_code': '',
                'robot_name': '',
            }
        )

        await self.ap.platform_cfg.dump_config()
