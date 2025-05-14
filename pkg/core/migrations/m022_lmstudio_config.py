from __future__ import annotations

from .. import migration


@migration.migration_class('lmstudio-config', 22)
class LmStudioConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""

        return 'lmstudio-chat-completions' not in self.ap.provider_cfg.data['requester']

    async def run(self):
        """执行迁移"""
        self.ap.provider_cfg.data['requester']['lmstudio-chat-completions'] = {
            'base-url': 'http://127.0.0.1:1234/v1',
            'args': {},
            'timeout': 120,
        }

        await self.ap.provider_cfg.dump_config()
