from __future__ import annotations

from .. import migration


@migration.migration_class("volcengine-requester-config", 32)
class VolcengineRequesterConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        
        return 'volcengine-chat-completions' not in self.ap.provider_cfg.data['requester']

    async def run(self):
        """执行迁移"""
        self.ap.provider_cfg.data['keys']['volcengine'] = [
            "xxxxxxxx"
        ]

        self.ap.provider_cfg.data['requester']['volcengine-chat-completions'] = {
            "base-url": "https://ark.cn-beijing.volces.com/api/v3",
            "args": {},
            "timeout": 120
        }

        await self.ap.provider_cfg.dump_config()
