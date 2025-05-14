from __future__ import annotations

from .. import migration


@migration.migration_class('ppio-config', 40)
class PPIOConfigMigration(migration.Migration):
    """PPIO配置迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return (
            'ppio-chat-completions' not in self.ap.provider_cfg.data['requester']
            or 'ppio' not in self.ap.provider_cfg.data['keys']
        )

    async def run(self):
        """执行迁移"""
        if 'ppio-chat-completions' not in self.ap.provider_cfg.data['requester']:
            self.ap.provider_cfg.data['requester']['ppio-chat-completions'] = {
                'base-url': 'https://api.ppinfra.com/v3/openai',
                'args': {},
                'timeout': 120,
            }

        if 'ppio' not in self.ap.provider_cfg.data['keys']:
            self.ap.provider_cfg.data['keys']['ppio'] = []

        await self.ap.provider_cfg.dump_config()
