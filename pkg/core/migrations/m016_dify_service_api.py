from __future__ import annotations

from .. import migration


@migration.migration_class('dify-service-api-config', 16)
class DifyServiceAPICfgMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return 'dify-service-api' not in self.ap.provider_cfg.data

    async def run(self):
        """执行迁移"""
        self.ap.provider_cfg.data['dify-service-api'] = {
            'base-url': 'https://api.dify.ai/v1',
            'app-type': 'chat',
            'chat': {'api-key': 'app-1234567890'},
            'workflow': {'api-key': 'app-1234567890', 'output-key': 'summary'},
        }

        await self.ap.provider_cfg.dump_config()
