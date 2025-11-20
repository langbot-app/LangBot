from __future__ import annotations

from .. import migration


@migration.migration_class('command-prefix-config', 11)
class CommandPrefixConfigMigration(migration.Migration):
    """迁移"""

    async def need_migrate(self) -> bool:
        """判断当前环境是否需要运行此迁移"""
        return 'command-prefix' not in self.ap.command_cfg.data

    async def run(self):
        """执行迁移"""

        self.ap.command_cfg.data['command-prefix'] = ['!', '！']

        await self.ap.command_cfg.dump_config()
