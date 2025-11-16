from __future__ import annotations

from .. import migration


@migration.migration_class('dify-thinking-config', 33)
class DifyThinkingConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""

        if 'options' not in self.ap.provider_cfg.data['dify-service-api']:
            return True

        if 'convert-thinking-tips' not in self.ap.provider_cfg.data['dify-service-api']['options']:
            return True

        return False

    async def run(self):
        """执行迁移"""
        self.ap.provider_cfg.data['dify-service-api']['options'] = {'convert-thinking-tips': 'plain'}
        await self.ap.provider_cfg.dump_config()
