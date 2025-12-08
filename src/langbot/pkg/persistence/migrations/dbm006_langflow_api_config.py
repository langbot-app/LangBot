from .. import migration

import sqlalchemy
import json


@migration.migration_class(6)
class DBMigrateLangflowApiConfig(migration.DBMigration):
    """Langflow API config"""

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

            # Ensure 'ai' exists
            if 'ai' not in config:
                config['ai'] = {}

            # Add 'langflow-api' if not exists
            if 'langflow-api' not in config['ai']:
                config['ai']['langflow-api'] = {
                    'base-url': 'http://localhost:7860',
                    'api-key': 'your-api-key',
                    'flow-id': 'your-flow-id',
                    'input-type': 'chat',
                    'output-type': 'chat',
                    'tweaks': '{}',
                }

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
