from __future__ import annotations

from .. import migration


@migration.migration_class('anthropic-requester-config-completion', 3)
class AnthropicRequesterConfigCompletionMigration(migration.Migration):
    """OpenAI配置迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return (
            'anthropic-messages' not in self.ap.provider_cfg.data['requester']
            or 'anthropic' not in self.ap.provider_cfg.data['keys']
        )

    async def run(self):
        """执行迁移"""
        if 'anthropic-messages' not in self.ap.provider_cfg.data['requester']:
            self.ap.provider_cfg.data['requester']['anthropic-messages'] = {
                'base-url': 'https://api.anthropic.com',
                'args': {'max_tokens': 1024},
                'timeout': 120,
            }

        if 'anthropic' not in self.ap.provider_cfg.data['keys']:
            self.ap.provider_cfg.data['keys']['anthropic'] = []

        await self.ap.provider_cfg.dump_config()
