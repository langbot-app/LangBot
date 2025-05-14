from __future__ import annotations

from .. import migration


@migration.migration_class('xai-config', 18)
class XaiConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return 'xai-chat-completions' not in self.ap.provider_cfg.data['requester']

    async def run(self):
        """执行迁移"""
        self.ap.provider_cfg.data['requester']['xai-chat-completions'] = {
            'base-url': 'https://api.x.ai/v1',
            'args': {},
            'timeout': 120,
        }
        self.ap.provider_cfg.data['keys']['xai'] = ['xai-1234567890']

        await self.ap.provider_cfg.dump_config()
