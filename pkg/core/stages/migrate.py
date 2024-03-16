from __future__ import annotations

import importlib

from .. import stage, app
from ...config import migration
from ...config.migrations import m1_sensitive_word_migration


@stage.stage_class("MigrationStage")
class MigrationStage(stage.BootingStage):
    """迁移阶段
    """

    async def run(self, ap: app.Application):
        """启动
        """

        migrations = migration.preregistered_migrations

        # 按照迁移号排序
        migrations.sort(key=lambda x: x.number)

        for migration_cls in migrations:
            migration_instance = migration_cls(ap)

            if await migration_instance.need_migrate():
                await migration_instance.run()
