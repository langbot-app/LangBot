from .. import migration

import sqlalchemy

from ...entity.persistence import pipeline as persistence_pipeline


@migration.migration_class(11)
class DBMigrateDifyApiConfig(migration.DBMigration):
    """Langflow API config"""

    async def upgrade(self):
        """Upgrade"""
        # read all pipelines
        pipelines = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_pipeline.LegacyPipeline))

        for pipeline in pipelines:
            serialized_pipeline = self.ap.persistence_mgr.serialize_model(persistence_pipeline.LegacyPipeline, pipeline)

            config = serialized_pipeline['config']

            if 'base-prompt' not in config['ai']['dify-service-api']:
                config['ai']['dify-service-api']['base-prompt'] = (
                    'When the file content is readable, please read the content of this file. When the file is an image, describe the content of this image.',
                )

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
