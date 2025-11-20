from __future__ import annotations


from .. import stage, app
from .. import migration
from ...utils import importutil
from .. import migrations

importutil.import_modules_in_pkg(migrations)


@stage.stage_class('MigrationStage')
class MigrationStage(stage.BootingStage):
    """Migration stage

    These migrations are legacy, only performed in version 3.x
    """

    async def run(self, ap: app.Application):
        """Run migration"""

        if any(
            [
                ap.command_cfg is None,
                ap.pipeline_cfg is None,
                ap.platform_cfg is None,
                ap.provider_cfg is None,
                ap.system_cfg is None,
            ]
        ):  # only run migration when version is 3.x
            return

        migrations = migration.preregistered_migrations

        # Sort by migration number
        migrations.sort(key=lambda x: x.number)

        for migration_cls in migrations:
            migration_instance = migration_cls(ap)

            if await migration_instance.need_migrate():
                await migration_instance.run()
                print(f'Migration {migration_instance.name} executed')
