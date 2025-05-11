from __future__ import annotations

from .. import migration


@migration.migration_class('gitee-ai-config', 15)
class GiteeAIConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return (
            'gitee-ai-chat-completions' not in self.ap.provider_cfg.data['requester']
            or 'gitee-ai' not in self.ap.provider_cfg.data['keys']
        )

    async def run(self):
        """执行迁移"""
        self.ap.provider_cfg.data['requester']['gitee-ai-chat-completions'] = {
            'base-url': 'https://ai.gitee.com/v1',
            'args': {},
            'timeout': 120,
        }

        self.ap.provider_cfg.data['keys']['gitee-ai'] = ['XXXXX']

        await self.ap.provider_cfg.dump_config()
