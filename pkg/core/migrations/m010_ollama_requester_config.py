from __future__ import annotations

from .. import migration


@migration.migration_class('ollama-requester-config', 10)
class MsgTruncatorConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return 'ollama-chat' not in self.ap.provider_cfg.data['requester']

    async def run(self):
        """执行迁移"""

        self.ap.provider_cfg.data['requester']['ollama-chat'] = {
            'base-url': 'http://127.0.0.1:11434',
            'args': {},
            'timeout': 600,
        }

        await self.ap.provider_cfg.dump_config()
