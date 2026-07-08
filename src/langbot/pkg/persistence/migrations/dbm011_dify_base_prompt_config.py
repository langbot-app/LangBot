from .. import migration

import sqlalchemy
import json


@migration.migration_class(11)
class DBMigrateDifyApiConfig(migration.DBMigration):
    """Dify base prompt config"""

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

            # Ensure nested structure exists
            if 'ai' not in config:
                config['ai'] = {}
            if 'dify-service-api' not in config['ai']:
                config['ai']['dify-service-api'] = {}

            # Add 'base-prompt' if not exists
            if 'base-prompt' not in config['ai']['dify-service-api']:
                config['ai']['dify-service-api']['base-prompt'] = (
                    'When the file content is readable, please read the content of this file. When the file is an image, describe the content of this image.',
                )

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
