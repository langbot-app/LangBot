from __future__ import annotations

import importlib

from .. import stage, app
from .. import migration
from ..migrations import m001_sensitive_word_migration, m002_openai_config_migration, m003_anthropic_requester_cfg_completion, m004_moonshot_cfg_completion
from ..migrations import m005_deepseek_cfg_completion, m006_vision_config, m007_qcg_center_url, m008_ad_fixwin_config_migrate, m009_msg_truncator_cfg
from ..migrations import m010_ollama_requester_config, m011_command_prefix_config, m012_runner_config


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
