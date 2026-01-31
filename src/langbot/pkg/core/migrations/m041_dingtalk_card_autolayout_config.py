from __future__ import annotations

from .. import migration


@migration.migration_class('dify-thinking-config', 33)
class DingTalkCardAutoLayoutMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return True

    async def run(self):
        """执行迁移"""
        self.ap.platform_cfg.data['platform-adapters']["app"]["dingtalk"]["card_autolayout"] = False
            
        await self.ap.platform_cfg.dump_config()
