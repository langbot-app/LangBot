from __future__ import annotations

from .. import migration


@migration.migration_class('gewechat-config', 25)
class GewechatConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""

        # for adapter in self.ap.platform_cfg.data['platform-adapters']:
        #     if adapter['adapter'] == 'gewechat':
        #         return False

        # return True
        return False

    async def run(self):
        """执行迁移"""
        self.ap.platform_cfg.data['platform-adapters'].append(
            {
                'adapter': 'gewechat',
                'enable': False,
                'gewechat_url': 'http://your-gewechat-server:2531',
                'gewechat_file_url': 'http://your-gewechat-server:2532',
                'port': 2286,
                'callback_url': 'http://your-callback-url:2286/gewechat/callback',
                'app_id': '',
                'token': '',
            }
        )

        await self.ap.platform_cfg.dump_config()
