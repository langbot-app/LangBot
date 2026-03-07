from .. import migration

import sqlalchemy
import json


@migration.migration_class(21)
class DBMigrateMergeExceptionHandling(migration.DBMigration):
    """Merge hide-exception and block-failed-request-output into a single exception-handling select option.

    Conversion logic:
    - block-failed-request-output=true  ->  exception-handling: hide
    - hide-exception=true               ->  exception-handling: show-hint
    - hide-exception=false              ->  exception-handling: show-error
    """

    async def upgrade(self):
        """Upgrade"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('SELECT uuid, config FROM legacy_pipelines')
        )
        pipelines = result.fetchall()

        current_version = self.ap.ver_mgr.get_current_version()

        for pipeline_row in pipelines:
            uuid = pipeline_row[0]
            config = json.loads(pipeline_row[1]) if isinstance(pipeline_row[1], str) else pipeline_row[1]

            if 'output' not in config:
                config['output'] = {}
            if 'misc' not in config['output']:
                config['output']['misc'] = {}

            misc = config['output']['misc']

            # Determine new exception-handling value from legacy fields
            hide_exception = misc.get('hide-exception', True)
            block_failed = misc.get('block-failed-request-output', False)

            if block_failed:
                exception_handling = 'hide'
            elif hide_exception:
                exception_handling = 'show-hint'
            else:
                exception_handling = 'show-error'

            misc['exception-handling'] = exception_handling

            # Remove legacy fields
            misc.pop('hide-exception', None)
            misc.pop('block-failed-request-output', None)

            if self.ap.persistence_mgr.db.name == 'postgresql':
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(
                        'UPDATE legacy_pipelines SET config = :config::jsonb, for_version = :for_version WHERE uuid = :uuid'
                    ),
                    {'config': json.dumps(config), 'for_version': current_version, 'uuid': uuid},
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(
                        'UPDATE legacy_pipelines SET config = :config, for_version = :for_version WHERE uuid = :uuid'
                    ),
                    {'config': json.dumps(config), 'for_version': current_version, 'uuid': uuid},
                )

    async def downgrade(self):
        """Downgrade"""
        pass
