import asyncio
import json

import httpx
import quart
import sqlalchemy

from ... import group
from ......core import taskmgr
from ......entity.persistence import metadata as persistence_metadata
from langbot_plugin.runtime.plugin.mgr import PluginInstallSource

LANGRAG_PLUGIN_AUTHOR = 'langbot-team'
LANGRAG_PLUGIN_NAME = 'LangRAG'
LANGRAG_PLUGIN_ID = f'{LANGRAG_PLUGIN_AUTHOR}/{LANGRAG_PLUGIN_NAME}'
DEFAULT_SPACE_URL = 'https://space.langbot.app'

# Old Retriever plugin_name -> New Connector plugin_name
EXTERNAL_PLUGIN_NAME_MAPPING = {
    'DifyDatasetsRetriever': 'DifyDatasetsConnector',
    'RAGFlowRetriever': 'RAGFlowConnector',
    'FastGPTRetriever': 'FastGPTConnector',
}

# Per-plugin: which old retriever_config fields belong to creation_settings.
# Remaining fields go to retrieval_settings.
# None means ALL fields go to creation_settings (no retrieval_schema).
EXTERNAL_PLUGIN_CREATION_FIELDS: dict[str, set[str] | None] = {
    'langbot-team/DifyDatasetsConnector': {'api_base_url', 'dify_apikey', 'dataset_id'},
    'langbot-team/RAGFlowConnector': {'api_base_url', 'api_key', 'dataset_ids'},
    'langbot-team/FastGPTConnector': None,  # all fields -> creation_settings
}


@group.group_class('knowledge/migration', '/api/v1/knowledge/migration')
class KnowledgeMigrationRouterGroup(group.RouterGroup):
    async def _get_migration_flag(self) -> bool:
        """Check if rag_plugin_migration_needed flag is set."""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_metadata.Metadata).where(
                persistence_metadata.Metadata.key == 'rag_plugin_migration_needed'
            )
        )
        row = result.first()
        return row is not None and row.value == 'true'

    async def _set_migration_flag(self, value: str):
        """Set rag_plugin_migration_needed flag."""
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_metadata.Metadata)
            .where(persistence_metadata.Metadata.key == 'rag_plugin_migration_needed')
            .values(value=value)
        )

    async def _table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        if self.ap.persistence_mgr.db.name == 'postgresql':
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :table_name);'
                ).bindparams(table_name=table_name)
            )
            return result.scalar()
        else:
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:table_name;").bindparams(
                    table_name=table_name
                )
            )
            return result.first() is not None

    async def _execute_rag_migration(self, task_context: taskmgr.TaskContext, install_plugin: bool = True):
        """Execute RAG migration: optionally install langrag plugin and restore backup data."""
        warnings = []

        if install_plugin:
            # Step 1: Install langrag plugin from marketplace
            task_context.trace('Installing LangRAG plugin from marketplace...', action='install-plugin')
            try:
                # Query marketplace for latest version
                space_url = self.ap.instance_config.data.get('space', {}).get('url', DEFAULT_SPACE_URL).rstrip('/')
                async with httpx.AsyncClient(trust_env=True, timeout=15) as client:
                    resp = await client.get(
                        f'{space_url}/api/v1/marketplace/plugins/{LANGRAG_PLUGIN_AUTHOR}/{LANGRAG_PLUGIN_NAME}'
                    )
                    resp.raise_for_status()
                    plugin_data = resp.json().get('data', {}).get('plugin', {})
                    plugin_version = plugin_data.get('latest_version')
                    if not plugin_version:
                        raise Exception('Could not determine latest LangRAG version from marketplace')

                install_info = {
                    'plugin_author': LANGRAG_PLUGIN_AUTHOR,
                    'plugin_name': LANGRAG_PLUGIN_NAME,
                    'plugin_version': plugin_version,
                }
                await self.ap.plugin_connector.install_plugin(
                    PluginInstallSource.MARKETPLACE, install_info, task_context=task_context
                )
            except Exception as e:
                # Plugin may already be installed
                self.ap.logger.warning(f'LangRAG plugin install returned: {e}')
                task_context.trace(f'Plugin install note: {e}')

            # Step 2: Wait for the plugin to be available
            task_context.trace('Waiting for LangRAG plugin to become available...', action='wait-plugin')
            max_retries = 30
            for i in range(max_retries):
                try:
                    engines = await self.ap.plugin_connector.list_knowledge_engines()
                    engine_ids = [e.get('plugin_id') for e in engines]
                    if LANGRAG_PLUGIN_ID in engine_ids:
                        task_context.trace('LangRAG plugin is ready.')
                        break
                except Exception:
                    pass
                if i == max_retries - 1:
                    raise Exception(
                        f'LangRAG plugin ({LANGRAG_PLUGIN_ID}) did not become available after {max_retries} retries'
                    )
                await asyncio.sleep(2)

        # Step 3: Restore internal knowledge bases from backup
        task_context.trace('Restoring internal knowledge bases...', action='restore-internal')
        if await self._table_exists('knowledge_bases_backup'):
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('SELECT * FROM knowledge_bases_backup;')
            )
            rows = result.fetchall()
            columns = result.keys()

            for row in rows:
                row_dict = dict(zip(columns, row))
                kb_uuid = row_dict.get('uuid')
                name = row_dict.get('name', 'Untitled')
                description = row_dict.get('description', '')
                emoji = row_dict.get('emoji', '\U0001f4da')
                embedding_model_uuid = row_dict.get('embedding_model_uuid', '')
                top_k = row_dict.get('top_k', 5)
                created_at = row_dict.get('created_at')
                updated_at = row_dict.get('updated_at')

                creation_settings = json.dumps({'embedding_model_uuid': embedding_model_uuid})
                retrieval_settings = json.dumps({'top_k': top_k})

                # Insert into knowledge_bases with the same UUID
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(
                        'INSERT INTO knowledge_bases '
                        '(uuid, name, description, emoji, created_at, updated_at, '
                        'knowledge_engine_plugin_id, collection_id, creation_settings, retrieval_settings) '
                        'VALUES (:uuid, :name, :description, :emoji, :created_at, :updated_at, '
                        ':plugin_id, :collection_id, :creation_settings, :retrieval_settings);'
                    ).bindparams(
                        uuid=kb_uuid,
                        name=name,
                        description=description,
                        emoji=emoji,
                        created_at=created_at,
                        updated_at=updated_at,
                        plugin_id=LANGRAG_PLUGIN_ID,
                        collection_id=kb_uuid,
                        creation_settings=creation_settings,
                        retrieval_settings=retrieval_settings,
                    )
                )

                # Notify langrag plugin to recognize this KB
                try:
                    config = {'embedding_model_uuid': embedding_model_uuid}
                    await self.ap.plugin_connector.rag_on_kb_create(LANGRAG_PLUGIN_ID, kb_uuid, config)
                    task_context.trace(f'Restored internal KB: {name} ({kb_uuid})')
                except Exception as e:
                    warning = f'Failed to notify plugin for KB {name} ({kb_uuid}): {e}'
                    warnings.append(warning)
                    task_context.trace(warning)

            # Reload all knowledge bases into runtime
            await self.ap.rag_mgr.load_knowledge_bases_from_db()

        # Step 4: Restore external knowledge bases (read from preserved original table)
        task_context.trace('Restoring external knowledge bases...', action='restore-external')
        if await self._table_exists('external_knowledge_bases'):
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('SELECT * FROM external_knowledge_bases;')
            )
            rows = result.fetchall()
            columns = result.keys()

            # Get current available engines for matching
            try:
                engines = await self.ap.plugin_connector.list_knowledge_engines()
                engine_id_set = {e.get('plugin_id') for e in engines}
            except Exception:
                engine_id_set = set()

            for row in rows:
                row_dict = dict(zip(columns, row))
                kb_uuid = row_dict.get('uuid')
                name = row_dict.get('name', 'Untitled')
                description = row_dict.get('description', '')
                emoji = row_dict.get('emoji', '\U0001f517')
                plugin_author = row_dict.get('plugin_author', '')
                plugin_name = row_dict.get('plugin_name', '')
                retriever_config = row_dict.get('retriever_config', {})
                created_at = row_dict.get('created_at')

                # Map old Retriever plugin name to new Connector plugin name
                mapped_plugin_name = EXTERNAL_PLUGIN_NAME_MAPPING.get(plugin_name, plugin_name)
                external_plugin_id = f'{plugin_author}/{mapped_plugin_name}'

                if external_plugin_id not in engine_id_set:
                    warning = (
                        f'External KB "{name}" ({kb_uuid}) uses plugin {external_plugin_id} '
                        f'which is not available as a Knowledge Engine. Skipped.'
                    )
                    warnings.append(warning)
                    task_context.trace(warning)
                    continue

                # Parse retriever_config
                if isinstance(retriever_config, str):
                    try:
                        retriever_config = json.loads(retriever_config)
                    except (json.JSONDecodeError, TypeError):
                        retriever_config = {}

                # Split retriever_config into creation_settings and retrieval_settings
                creation_fields = EXTERNAL_PLUGIN_CREATION_FIELDS.get(external_plugin_id)
                if creation_fields is None:
                    # All fields go to creation_settings (e.g. FastGPT has no retrieval_schema)
                    creation_settings_dict = retriever_config
                    retrieval_settings_dict = {}
                else:
                    creation_settings_dict = {k: v for k, v in retriever_config.items() if k in creation_fields}
                    retrieval_settings_dict = {k: v for k, v in retriever_config.items() if k not in creation_fields}

                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(
                        'INSERT INTO knowledge_bases '
                        '(uuid, name, description, emoji, created_at, updated_at, '
                        'knowledge_engine_plugin_id, collection_id, creation_settings, retrieval_settings) '
                        'VALUES (:uuid, :name, :description, :emoji, :created_at, :updated_at, '
                        ':plugin_id, :collection_id, :creation_settings, :retrieval_settings);'
                    ).bindparams(
                        uuid=kb_uuid,
                        name=name,
                        description=description,
                        emoji=emoji,
                        created_at=created_at,
                        updated_at=created_at,
                        plugin_id=external_plugin_id,
                        collection_id=kb_uuid,
                        creation_settings=json.dumps(creation_settings_dict),
                        retrieval_settings=json.dumps(retrieval_settings_dict),
                    )
                )

                try:
                    await self.ap.plugin_connector.rag_on_kb_create(external_plugin_id, kb_uuid, creation_settings_dict)
                    task_context.trace(f'Restored external KB: {name} ({kb_uuid})')
                except Exception as e:
                    warning = f'Failed to notify plugin for external KB {name} ({kb_uuid}): {e}'
                    warnings.append(warning)
                    task_context.trace(warning)

            # Reload again after external KBs
            await self.ap.rag_mgr.load_knowledge_bases_from_db()

        # Step 5: Clear migration flag
        await self._set_migration_flag('false')
        task_context.trace('RAG migration completed.', action='done')

        if warnings:
            task_context.trace(f'Completed with {len(warnings)} warning(s).')

    async def initialize(self) -> None:
        @self.route('/status', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            needed = await self._get_migration_flag()

            internal_kb_count = 0
            external_kb_count = 0

            if needed:
                if await self._table_exists('knowledge_bases_backup'):
                    result = await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.text('SELECT COUNT(*) FROM knowledge_bases_backup;')
                    )
                    internal_kb_count = result.scalar() or 0

                if await self._table_exists('external_knowledge_bases'):
                    result = await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.text('SELECT COUNT(*) FROM external_knowledge_bases;')
                    )
                    external_kb_count = result.scalar() or 0

            return self.success(
                data={
                    'needed': needed,
                    'internal_kb_count': internal_kb_count,
                    'external_kb_count': external_kb_count,
                }
            )

        @self.route('/execute', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            needed = await self._get_migration_flag()
            if not needed:
                return self.http_status(400, -1, 'RAG migration is not needed')

            data = await quart.request.get_json(silent=True) or {}
            install_plugin = data.get('install_plugin', True)

            ctx = taskmgr.TaskContext.new()
            wrapper = self.ap.task_mgr.create_user_task(
                self._execute_rag_migration(task_context=ctx, install_plugin=install_plugin),
                kind='rag-migration',
                name='rag-migration-execute',
                label='Migrating knowledge bases to plugin architecture',
                context=ctx,
            )

            return self.success(data={'task_id': wrapper.id})

        @self.route('/dismiss', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            needed = await self._get_migration_flag()
            if not needed:
                return self.http_status(400, -1, 'RAG migration is not needed')

            await self._set_migration_flag('false')
            return self.success()
