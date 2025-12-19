from .. import migration

import sqlalchemy
import json


@migration.migration_class(10)
class DBMigratePipelineMultiKnowledgeBase(migration.DBMigration):
    """Pipeline support multiple knowledge base binding"""

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

            # Convert knowledge-base from string to array
            if 'ai' in config and 'local-agent' in config['ai']:
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
        # Read all pipelines using raw SQL
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('SELECT uuid, config FROM legacy_pipelines')
        )
        pipelines = result.fetchall()

        current_version = self.ap.ver_mgr.get_current_version()

        for pipeline_row in pipelines:
            uuid = pipeline_row[0]
            config = json.loads(pipeline_row[1]) if isinstance(pipeline_row[1], str) else pipeline_row[1]

            # Convert knowledge-bases from array back to string
            if 'ai' in config and 'local-agent' in config['ai']:
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
