from __future__ import annotations

from .. import migration


@migration.migration_class('modelscope-config-completion', 39)
class ModelScopeConfigCompletionMigration(migration.Migration):
    """ModelScope配置迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return (
            'modelscope-chat-completions' not in self.ap.provider_cfg.data['requester']
            or 'modelscope' not in self.ap.provider_cfg.data['keys']
        )

    async def run(self):
        """执行迁移"""
        if 'modelscope-chat-completions' not in self.ap.provider_cfg.data['requester']:
            self.ap.provider_cfg.data['requester']['modelscope-chat-completions'] = {
                'base-url': 'https://api-inference.modelscope.cn/v1',
                'args': {},
                'timeout': 120,
            }

        if 'modelscope' not in self.ap.provider_cfg.data['keys']:
            self.ap.provider_cfg.data['keys']['modelscope'] = []

        await self.ap.provider_cfg.dump_config()
