from __future__ import annotations

from .. import migration


@migration.migration_class('msg-truncator-cfg-migration', 9)
class MsgTruncatorConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return 'msg-truncate' not in self.ap.pipeline_cfg.data

    async def run(self):
        """执行迁移"""

        self.ap.pipeline_cfg.data['msg-truncate'] = {
            'method': 'round',
            'round': {'max-round': 10},
        }

        await self.ap.pipeline_cfg.dump_config()
