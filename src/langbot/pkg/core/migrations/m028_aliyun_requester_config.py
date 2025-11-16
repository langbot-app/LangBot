from __future__ import annotations

from .. import migration


@migration.migration_class('bailian-requester-config', 28)
class BailianRequesterConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""

        return 'bailian-chat-completions' not in self.ap.provider_cfg.data['requester']

    async def run(self):
        """执行迁移"""
        self.ap.provider_cfg.data['keys']['bailian'] = ['sk-xxxxxxx']

        self.ap.provider_cfg.data['requester']['bailian-chat-completions'] = {
            'base-url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            'args': {},
            'timeout': 120,
        }

        await self.ap.provider_cfg.dump_config()
