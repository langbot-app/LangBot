from .. import migration

import sqlalchemy

from ...entity.persistence import pipeline as persistence_pipeline


@migration.migration_class(2)
class DBMigrateCombineQuoteMsgConfig(migration.DBMigration):
    """引用消息合并配置"""

    async def upgrade(self):
        """升级"""
        # read all pipelines
        pipelines = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_pipeline.LegacyPipeline))

        for pipeline in pipelines:
            serialized_pipeline = self.ap.persistence_mgr.serialize_model(persistence_pipeline.LegacyPipeline, pipeline)

            config = serialized_pipeline['config']

            if 'misc' not in config['trigger']:
                config['trigger']['misc'] = {}

            if 'combine-quote-message' not in config['trigger']['misc']:
                config['trigger']['misc']['combine-quote-message'] = False

            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_pipeline.LegacyPipeline)
                .where(persistence_pipeline.LegacyPipeline.uuid == serialized_pipeline['uuid'])
                .values({'config': config, 'for_version': self.ap.ver_mgr.get_current_version()})
            )

    async def downgrade(self):
        """降级"""
        pass
