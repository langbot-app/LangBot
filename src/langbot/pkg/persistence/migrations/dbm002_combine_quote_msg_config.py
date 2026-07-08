from .. import migration

import sqlalchemy
import json


@migration.migration_class(2)
class DBMigrateCombineQuoteMsgConfig(migration.DBMigration):
    """Combine quote message config"""

    async def upgrade(self):
        """Upgrade"""
        # Read all pipelines using raw SQL
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('SELECT uuid, config FROM legacy_pipelines')
        )
        pipelines = result.fetchall()

        current_version = self.ap.ver_mgr.get_current_version()

        for pipeline_row in pipelines:
            uuid = pipeline_row[0]
            config = json.loads(pipeline_row[1]) if isinstance(pipeline_row[1], str) else pipeline_row[1]

            # Ensure 'trigger' exists
            if 'trigger' not in config:
                config['trigger'] = {}

            # Ensure 'misc' exists in 'trigger'
            if 'misc' not in config['trigger']:
                config['trigger']['misc'] = {}

            # Add 'combine-quote-message' if not exists
            if 'combine-quote-message' not in config['trigger']['misc']:
                config['trigger']['misc']['combine-quote-message'] = False

            # Update using raw SQL with compatibility for both SQLite and PostgreSQL
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
