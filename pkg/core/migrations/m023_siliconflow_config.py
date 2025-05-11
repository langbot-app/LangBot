from __future__ import annotations

from .. import migration


@migration.migration_class('siliconflow-config', 23)
class SiliconFlowConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""

        return 'siliconflow-chat-completions' not in self.ap.provider_cfg.data['requester']

    async def run(self):
        """执行迁移"""
        self.ap.provider_cfg.data['keys']['siliconflow'] = ['xxxxxxx']

        self.ap.provider_cfg.data['requester']['siliconflow-chat-completions'] = {
            'base-url': 'https://api.siliconflow.cn/v1',
            'args': {},
            'timeout': 120,
        }

        await self.ap.provider_cfg.dump_config()
