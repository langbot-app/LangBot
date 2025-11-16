from __future__ import annotations

from urllib.parse import urlparse

from .. import migration


@migration.migration_class('gewechat-file-url-config', 34)
class GewechatFileUrlConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""

        for adapter in self.ap.platform_cfg.data['platform-adapters']:
            if adapter['adapter'] == 'gewechat':
                if 'gewechat_file_url' not in adapter:
                    return True
        return False

    async def run(self):
        """执行迁移"""
        for adapter in self.ap.platform_cfg.data['platform-adapters']:
            if adapter['adapter'] == 'gewechat':
                if 'gewechat_file_url' not in adapter:
                    parsed_url = urlparse(adapter['gewechat_url'])
                    adapter['gewechat_file_url'] = f'{parsed_url.scheme}://{parsed_url.hostname}:2532'

        await self.ap.platform_cfg.dump_config()
