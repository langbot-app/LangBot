from .. import migration

import sqlalchemy

from ...entity.persistence import pipeline as persistence_pipeline


@migration.migration_class(3)
class DBMigrateN8nConfig(migration.DBMigration):
    """N8n config"""

    async def upgrade(self):
        """Upgrade"""
        # read all pipelines
        pipelines = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_pipeline.LegacyPipeline))

        for pipeline in pipelines:
            serialized_pipeline = self.ap.persistence_mgr.serialize_model(persistence_pipeline.LegacyPipeline, pipeline)

            config = serialized_pipeline['config']

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

            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_pipeline.LegacyPipeline)
                .where(persistence_pipeline.LegacyPipeline.uuid == serialized_pipeline['uuid'])
                .values(
                    {
                        'config': config,
                        'for_version': self.ap.ver_mgr.get_current_version(),
                    }
                )
            )

    async def downgrade(self):
        """Downgrade"""
        pass
