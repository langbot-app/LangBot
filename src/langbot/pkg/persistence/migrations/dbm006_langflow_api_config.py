from .. import migration

import sqlalchemy

from ...entity.persistence import pipeline as persistence_pipeline


@migration.migration_class(6)
class DBMigrateLangflowApiConfig(migration.DBMigration):
    """Langflow API config"""

    async def upgrade(self):
        """Upgrade"""
        # read all pipelines
        pipelines = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_pipeline.LegacyPipeline))

        for pipeline in pipelines:
            serialized_pipeline = self.ap.persistence_mgr.serialize_model(persistence_pipeline.LegacyPipeline, pipeline)

            config = serialized_pipeline['config']

            if 'langflow-api' not in config['ai']:
                config['ai']['langflow-api'] = {
                    'base-url': 'http://localhost:7860',
                    'api-key': 'your-api-key',
                    'flow-id': 'your-flow-id',
                    'input-type': 'chat',
                    'output-type': 'chat',
                    'tweaks': '{}',
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
