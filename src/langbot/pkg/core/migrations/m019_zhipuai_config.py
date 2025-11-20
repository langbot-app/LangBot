from __future__ import annotations

from .. import migration


@migration.migration_class('zhipuai-config', 19)
class ZhipuaiConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return 'zhipuai-chat-completions' not in self.ap.provider_cfg.data['requester']

    async def run(self):
        """执行迁移"""
        self.ap.provider_cfg.data['requester']['zhipuai-chat-completions'] = {
            'base-url': 'https://open.bigmodel.cn/api/paas/v4',
            'args': {},
            'timeout': 120,
        }
        self.ap.provider_cfg.data['keys']['zhipuai'] = ['xxxxxxx']

        await self.ap.provider_cfg.dump_config()
