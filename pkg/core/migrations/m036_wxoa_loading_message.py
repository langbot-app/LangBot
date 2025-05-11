from __future__ import annotations

from .. import migration


@migration.migration_class('wxoa-loading-message', 36)
class WxoaLoadingMessageMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""

        for adapter in self.ap.platform_cfg.data['platform-adapters']:
            if adapter['adapter'] == 'officialaccount':
                if 'LoadingMessage' not in adapter:
                    return True
        return False

    async def run(self):
        """执行迁移"""
        for adapter in self.ap.platform_cfg.data['platform-adapters']:
            if adapter['adapter'] == 'officialaccount':
                if 'LoadingMessage' not in adapter:
                    adapter['LoadingMessage'] = 'AI正在思考中，请发送任意内容获取回复。'

        await self.ap.platform_cfg.dump_config()
