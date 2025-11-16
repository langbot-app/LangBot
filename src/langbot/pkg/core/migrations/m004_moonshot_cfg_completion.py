from __future__ import annotations

from .. import migration


@migration.migration_class('moonshot-config-completion', 4)
class MoonshotConfigCompletionMigration(migration.Migration):
    """OpenAI配置迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return (
            'moonshot-chat-completions' not in self.ap.provider_cfg.data['requester']
            or 'moonshot' not in self.ap.provider_cfg.data['keys']
        )

    async def run(self):
        """执行迁移"""
        if 'moonshot-chat-completions' not in self.ap.provider_cfg.data['requester']:
            self.ap.provider_cfg.data['requester']['moonshot-chat-completions'] = {
                'base-url': 'https://api.moonshot.cn/v1',
                'args': {},
                'timeout': 120,
            }

        if 'moonshot' not in self.ap.provider_cfg.data['keys']:
            self.ap.provider_cfg.data['keys']['moonshot'] = []

        await self.ap.provider_cfg.dump_config()
