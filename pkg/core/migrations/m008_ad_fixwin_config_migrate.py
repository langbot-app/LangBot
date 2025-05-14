from __future__ import annotations

from .. import migration


@migration.migration_class('ad-fixwin-cfg-migration', 8)
class AdFixwinConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return isinstance(self.ap.pipeline_cfg.data['rate-limit']['fixwin']['default'], int)

    async def run(self):
        """执行迁移"""

        for session_name in self.ap.pipeline_cfg.data['rate-limit']['fixwin']:
            temp_dict = {
                'window-size': 60,
                'limit': self.ap.pipeline_cfg.data['rate-limit']['fixwin'][session_name],
            }

            self.ap.pipeline_cfg.data['rate-limit']['fixwin'][session_name] = temp_dict

        await self.ap.pipeline_cfg.dump_config()
