from .. import migration

import sqlalchemy
import json


@migration.migration_class(3)
class DBMigrateN8nConfig(migration.DBMigration):
    """N8n config"""

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

            # Add 'n8n-service-api' if not exists
            if 'n8n-service-api' not in config['ai']:
                config['ai']['n8n-service-api'] = {
                    'webhook-url': 'http://your-n8n-webhook-url',
                    'auth-type': 'none',
                    'basic-username': '',
                    'basic-password': '',
                    'jwt-secret': '',
                    'jwt-algorithm': 'HS256',
                    'header-name': '',
                    'header-value': '',
                    'timeout': 120,
                    'output-key': 'response',
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
