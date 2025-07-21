from .. import migration

import sqlalchemy

from ...entity.persistence import pipeline as persistence_pipeline


@migration.migration_class(4)
class DBMigrateRAGKBUUID(migration.DBMigration):
    """RAG知识库UUID"""

    async def upgrade(self):
        """升级"""
        # read all pipelines
        pipelines = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_pipeline.LegacyPipeline))

        for pipeline in pipelines:
            serialized_pipeline = self.ap.persistence_mgr.serialize_model(persistence_pipeline.LegacyPipeline, pipeline)

            config = serialized_pipeline['config']

            if 'knowledge-base' not in config['ai']['local-agent']:
                config['ai']['local-agent']['knowledge-base'] = ''

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
        """降级"""
        pass
