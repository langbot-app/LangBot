from __future__ import annotations

from .. import migration


@migration.migration_class('dify-api-timeout-params', 17)
class DifyAPITimeoutParamsMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return (
            'timeout' not in self.ap.provider_cfg.data['dify-service-api']['chat']
            or 'timeout' not in self.ap.provider_cfg.data['dify-service-api']['workflow']
            or 'agent' not in self.ap.provider_cfg.data['dify-service-api']
        )

    async def run(self):
        """执行迁移"""
        self.ap.provider_cfg.data['dify-service-api']['chat']['timeout'] = 120
        self.ap.provider_cfg.data['dify-service-api']['workflow']['timeout'] = 120
        self.ap.provider_cfg.data['dify-service-api']['agent'] = {
            'api-key': 'app-1234567890',
            'timeout': 120,
        }

        await self.ap.provider_cfg.dump_config()
