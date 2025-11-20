from __future__ import annotations

from .. import migration


@migration.migration_class('deepseek-config-completion', 5)
class DeepseekConfigCompletionMigration(migration.Migration):
    """OpenAI配置迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return (
            'deepseek-chat-completions' not in self.ap.provider_cfg.data['requester']
            or 'deepseek' not in self.ap.provider_cfg.data['keys']
        )

    async def run(self):
        """执行迁移"""
        if 'deepseek-chat-completions' not in self.ap.provider_cfg.data['requester']:
            self.ap.provider_cfg.data['requester']['deepseek-chat-completions'] = {
                'base-url': 'https://api.deepseek.com',
                'args': {},
                'timeout': 120,
            }

        if 'deepseek' not in self.ap.provider_cfg.data['keys']:
            self.ap.provider_cfg.data['keys']['deepseek'] = []

        await self.ap.provider_cfg.dump_config()
