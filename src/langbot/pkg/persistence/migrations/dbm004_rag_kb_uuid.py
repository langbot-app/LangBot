from .. import migration

import sqlalchemy
import json


@migration.migration_class(4)
class DBMigrateRAGKBUUID(migration.DBMigration):
    """RAG知识库UUID"""

    async def upgrade(self):
        """升级"""
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
            if 'local-agent' not in config['ai']:
                config['ai']['local-agent'] = {}

            # Add 'knowledge-base' if not exists
            if 'knowledge-base' not in config['ai']['local-agent']:
                config['ai']['local-agent']['knowledge-base'] = ''

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
        """降级"""
        pass
