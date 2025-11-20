from .. import migration

import sqlalchemy

from ...entity.persistence import pipeline as persistence_pipeline


@migration.migration_class(10)
class DBMigratePipelineMultiKnowledgeBase(migration.DBMigration):
    """Pipeline support multiple knowledge base binding"""

    async def upgrade(self):
        """Upgrade"""
        # read all pipelines
        pipelines = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_pipeline.LegacyPipeline))

        for pipeline in pipelines:
            serialized_pipeline = self.ap.persistence_mgr.serialize_model(persistence_pipeline.LegacyPipeline, pipeline)

            config = serialized_pipeline['config']

            # Convert knowledge-base from string to array
            if 'local-agent' in config['ai']:
                current_kb = config['ai']['local-agent'].get('knowledge-base', '')

                # If it's already a list, skip
                if isinstance(current_kb, list):
                    continue

                # Convert string to list
                if current_kb and current_kb != '__none__':
                    config['ai']['local-agent']['knowledge-bases'] = [current_kb]
                else:
                    config['ai']['local-agent']['knowledge-bases'] = []

                # Remove old field
                if 'knowledge-base' in config['ai']['local-agent']:
                    del config['ai']['local-agent']['knowledge-base']

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
        # read all pipelines
        pipelines = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_pipeline.LegacyPipeline))

        for pipeline in pipelines:
            serialized_pipeline = self.ap.persistence_mgr.serialize_model(persistence_pipeline.LegacyPipeline, pipeline)

            config = serialized_pipeline['config']

            # Convert knowledge-bases from array back to string
            if 'local-agent' in config['ai']:
                current_kbs = config['ai']['local-agent'].get('knowledge-bases', [])

                # If it's already a string, skip
                if isinstance(current_kbs, str):
                    continue

                # Convert list to string (take first one or empty)
                if current_kbs and len(current_kbs) > 0:
                    config['ai']['local-agent']['knowledge-base'] = current_kbs[0]
                else:
                    config['ai']['local-agent']['knowledge-base'] = ''

                # Remove new field
                if 'knowledge-bases' in config['ai']['local-agent']:
                    del config['ai']['local-agent']['knowledge-bases']

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
