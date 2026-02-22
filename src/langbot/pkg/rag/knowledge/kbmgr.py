from __future__ import annotations
import mimetypes
import os.path
import traceback
import uuid
import zipfile
import io
from typing import Any
from langbot.pkg.core import app
import sqlalchemy


from langbot.pkg.entity.persistence import rag as persistence_rag
from langbot.pkg.core import taskmgr
from langbot_plugin.api.entities.builtin.rag import context as rag_context
from .base import KnowledgeBaseInterface


class RuntimeKnowledgeBase(KnowledgeBaseInterface):
    ap: app.Application

    knowledge_base_entity: persistence_rag.KnowledgeBase

    def __init__(self, ap: app.Application, knowledge_base_entity: persistence_rag.KnowledgeBase):
        super().__init__(ap)
        self.knowledge_base_entity = knowledge_base_entity

    async def initialize(self):
        pass

    async def _store_file_task(self, file: persistence_rag.File, task_context: taskmgr.TaskContext):
        try:
            # set file status to processing
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_rag.File)
                .where(persistence_rag.File.uuid == file.uuid)
                .values(status='processing')
            )

            task_context.set_current_action('Processing file')

            # Get file size from storage
            file_size = await self.ap.storage_mgr.storage_provider.size(file.file_name)

            # Detect MIME type from extension
            mime_type, _ = mimetypes.guess_type(file.file_name)
            if mime_type is None:
                mime_type = 'application/octet-stream'

            # Call plugin to ingest document
            await self._ingest_document(
                {
                    'document_id': file.uuid,
                    'filename': file.file_name,
                    'extension': file.extension,
                    'file_size': file_size,
                    'mime_type': mime_type,
                },
                file.file_name,  # storage path
            )

            # set file status to completed
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_rag.File)
                .where(persistence_rag.File.uuid == file.uuid)
                .values(status='completed')
            )

        except Exception as e:
            self.ap.logger.error(f'Error storing file {file.uuid}: {e}')
            traceback.print_exc()
            # set file status to failed
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_rag.File)
                .where(persistence_rag.File.uuid == file.uuid)
                .values(status='failed')
            )

            raise
        finally:
            # delete file from storage
            await self.ap.storage_mgr.storage_provider.delete(file.file_name)

    async def store_file(self, file_id: str) -> str:
        # pre checking
        if not await self.ap.storage_mgr.storage_provider.exists(file_id):
            raise Exception(f'File {file_id} not found')

        file_name = file_id
        _, ext = os.path.splitext(file_name)
        extension = ext.lstrip('.').lower() if ext else ''

        if extension == 'zip':
            return await self._store_zip_file(file_id)

        file_uuid = str(uuid.uuid4())
        kb_id = self.knowledge_base_entity.uuid

        file_obj_data = {
            'uuid': file_uuid,
            'kb_id': kb_id,
            'file_name': file_name,
            'extension': extension,
            'status': 'pending',
        }

        file_obj = persistence_rag.File(**file_obj_data)

        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_rag.File).values(file_obj_data))

        # run background task asynchronously
        ctx = taskmgr.TaskContext.new()
        wrapper = self.ap.task_mgr.create_user_task(
            self._store_file_task(file_obj, task_context=ctx),
            kind='knowledge-operation',
            name=f'knowledge-store-file-{file_id}',
            label=f'Store file {file_id}',
            context=ctx,
        )
        return wrapper.id

    async def _store_zip_file(self, zip_file_id: str) -> str:
        """Handle ZIP file by extracting each document and storing them separately."""
        self.ap.logger.info(f'Processing ZIP file: {zip_file_id}')

        zip_bytes = await self.ap.storage_mgr.storage_provider.load(zip_file_id)

        supported_extensions = {'txt', 'pdf', 'docx', 'md', 'html'}
        stored_file_tasks = []

        # use utf-8 encoding
        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r', metadata_encoding='utf-8') as zip_ref:
            for file_info in zip_ref.filelist:
                # skip directories and hidden files
                if file_info.is_dir() or file_info.filename.startswith('.'):
                    continue

                _, file_ext = os.path.splitext(file_info.filename)
                file_extension = file_ext.lstrip('.').lower()
                if file_extension not in supported_extensions:
                    self.ap.logger.debug(f'Skipping unsupported file in ZIP: {file_info.filename}')
                    continue

                try:
                    file_content = zip_ref.read(file_info.filename)

                    base_name = file_info.filename.replace('/', '_').replace('\\', '_')
                    file_stem, file_ext = os.path.splitext(base_name)
                    extension = file_ext.lstrip('.')

                    if file_stem.startswith('__MACOSX'):
                        continue

                    extracted_file_id = file_stem + '_' + str(uuid.uuid4())[:8] + '.' + extension
                    # save file to storage

                    await self.ap.storage_mgr.storage_provider.save(extracted_file_id, file_content)

                    task_id = await self.store_file(extracted_file_id)
                    stored_file_tasks.append(task_id)

                    self.ap.logger.info(
                        f'Extracted and stored file from ZIP: {file_info.filename} -> {extracted_file_id}'
                    )

                except Exception as e:
                    self.ap.logger.warning(f'Failed to extract file {file_info.filename} from ZIP: {e}')
                    continue

        if not stored_file_tasks:
            raise Exception('No supported files found in ZIP archive')

        self.ap.logger.info(f'Successfully processed ZIP file {zip_file_id}, extracted {len(stored_file_tasks)} files')
        await self.ap.storage_mgr.storage_provider.delete(zip_file_id)

        return stored_file_tasks[0] if stored_file_tasks else ''

    async def retrieve(
        self, query: str, top_k: int, settings: dict | None = None
    ) -> list[rag_context.RetrievalResultEntry]:
        # Merge top_k into settings or use as default
        retrieve_settings = {'top_k': top_k}
        if settings:
            retrieve_settings.update(settings)

        response = await self._retrieve(query, retrieve_settings)

        results_data = response.get('results', [])
        entries = []
        for r in results_data:
            if isinstance(r, dict):
                entries.append(rag_context.RetrievalResultEntry(**r))
            elif isinstance(r, rag_context.RetrievalResultEntry):
                entries.append(r)
        return entries

    async def delete_file(self, file_id: str):
        await self._delete_document(file_id)

        # Also cleanup DB record
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_rag.File).where(persistence_rag.File.uuid == file_id)
        )

    def get_uuid(self) -> str:
        """Get the UUID of the knowledge base"""
        return self.knowledge_base_entity.uuid

    def get_name(self) -> str:
        """Get the name of the knowledge base"""
        return self.knowledge_base_entity.name

    def get_rag_engine_plugin_id(self) -> str:
        """Get the RAG engine plugin ID"""
        return self.knowledge_base_entity.rag_engine_plugin_id or ''

    async def dispose(self):
        """Dispose the knowledge base, notifying the plugin to cleanup."""
        await self._on_kb_delete()

    # ========== Plugin Communication Methods ==========

    async def _on_kb_create(self) -> None:
        """Notify plugin about KB creation."""
        plugin_id = self.knowledge_base_entity.rag_engine_plugin_id
        if not plugin_id:
            return

        try:
            config = self.knowledge_base_entity.creation_settings or {}
            self.ap.logger.info(
                f'Calling RAG plugin {plugin_id}: on_knowledge_base_create(kb_id={self.knowledge_base_entity.uuid})'
            )
            await self.ap.plugin_connector.rag_on_kb_create(plugin_id, self.knowledge_base_entity.uuid, config)
        except Exception as e:
            self.ap.logger.error(f'Failed to notify plugin {plugin_id} on KB create: {e}')
            raise

    async def _on_kb_delete(self) -> None:
        """Notify plugin about KB deletion."""
        plugin_id = self.knowledge_base_entity.rag_engine_plugin_id
        if not plugin_id:
            return

        try:
            self.ap.logger.info(
                f'Calling RAG plugin {plugin_id}: on_knowledge_base_delete(kb_id={self.knowledge_base_entity.uuid})'
            )
            await self.ap.plugin_connector.rag_on_kb_delete(plugin_id, self.knowledge_base_entity.uuid)
        except Exception as e:
            self.ap.logger.error(f'Failed to notify plugin {plugin_id} on KB delete: {e}')

    async def _ingest_document(
        self,
        file_metadata: dict[str, Any],
        storage_path: str,
    ) -> dict[str, Any]:
        """Call plugin to ingest document."""
        kb = self.knowledge_base_entity
        plugin_id = kb.rag_engine_plugin_id
        if not plugin_id:
            self.ap.logger.error(f'No RAG plugin ID configured for KB {kb.uuid}. Ingestion failed.')
            raise ValueError('RAG Plugin ID required')

        self.ap.logger.info(f'Calling RAG plugin {plugin_id}: ingest(doc={file_metadata.get("filename")})')

        # Inject knowledge_base_id into file metadata as required by SDK schema
        file_metadata['knowledge_base_id'] = kb.uuid

        context_data = {
            'file_object': {
                'metadata': file_metadata,
                'storage_path': storage_path,
            },
            'knowledge_base_id': kb.uuid,
            'collection_id': kb.collection_id or kb.uuid,
            'chunking_strategy': kb.creation_settings.get('chunking_strategy', 'fixed_size')
            if kb.creation_settings
            else 'fixed_size',
            'custom_settings': kb.creation_settings or {},
        }

        try:
            result = await self.ap.plugin_connector.call_rag_ingest(plugin_id, context_data)
            return result
        except Exception as e:
            self.ap.logger.error(f'Plugin ingestion failed: {e}')
            raise

    async def _retrieve(
        self,
        query: str,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        """Call plugin to retrieve documents.

        Raises:
            ValueError: If no RAG plugin is configured for this KB.
            Exception: If the plugin retrieval call fails.
        """
        kb = self.knowledge_base_entity
        plugin_id = kb.rag_engine_plugin_id
        if not plugin_id:
            raise ValueError(f'No RAG plugin ID configured for KB {kb.uuid}. Retrieval failed.')

        retrieval_context = {
            'query': query,
            'knowledge_base_id': kb.uuid,
            'collection_id': kb.collection_id or kb.uuid,
            'top_k': settings.get('top_k') or kb.top_k or 5,
            'retrieval_settings': settings,
            'creation_settings': kb.creation_settings or {},
        }

        result = await self.ap.plugin_connector.call_rag_retrieve(
            plugin_id,
            retrieval_context,
        )
        return result

    async def _delete_document(self, document_id: str) -> bool:
        """Call plugin to delete document."""
        kb = self.knowledge_base_entity
        plugin_id = kb.rag_engine_plugin_id
        if not plugin_id:
            return False

        self.ap.logger.info(f'Calling RAG plugin {plugin_id}: delete_document(doc_id={document_id})')

        try:
            return await self.ap.plugin_connector.call_rag_delete_document(plugin_id, document_id, kb.uuid)
        except Exception as e:
            self.ap.logger.error(f'Plugin document deletion failed: {e}')
            return False


class RAGManager:
    ap: app.Application

    knowledge_bases: dict[str, KnowledgeBaseInterface]

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.knowledge_bases = {}

    async def initialize(self):
        await self.load_knowledge_bases_from_db()

    async def get_all_knowledge_base_details(self) -> list[dict]:
        """Get all knowledge bases with enriched RAG engine details."""
        # 1. Get raw KBs from DB
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_rag.KnowledgeBase))
        knowledge_bases = result.all()

        # 2. Get all available RAG engines for enrichment
        engine_map = {}
        if self.ap.plugin_connector.is_enable_plugin:
            try:
                engines = await self.ap.plugin_connector.list_rag_engines()
                engine_map = {e['plugin_id']: e for e in engines}
            except Exception as e:
                self.ap.logger.warning(f'Failed to list RAG engines: {e}')

        # 3. Serialize and enrich
        kb_list = []
        for kb in knowledge_bases:
            kb_dict = self.ap.persistence_mgr.serialize_model(persistence_rag.KnowledgeBase, kb)
            self._enrich_kb_dict(kb_dict, engine_map)
            kb_list.append(kb_dict)

        return kb_list

    async def get_knowledge_base_details(self, kb_uuid: str) -> dict | None:
        """Get specific knowledge base with enriched RAG engine details."""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.KnowledgeBase).where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )
        kb = result.first()
        if not kb:
            return None

        kb_dict = self.ap.persistence_mgr.serialize_model(persistence_rag.KnowledgeBase, kb)

        # Fetch engines
        engine_map = {}
        if self.ap.plugin_connector.is_enable_plugin:
            try:
                engines = await self.ap.plugin_connector.list_rag_engines()
                engine_map = {e['plugin_id']: e for e in engines}
            except Exception as e:
                self.ap.logger.warning(f'Failed to list RAG engines: {e}')

        self._enrich_kb_dict(kb_dict, engine_map)
        return kb_dict

    @staticmethod
    def _to_i18n_name(name) -> dict:
        """Ensure name is always an I18nObject-compatible dict.

        If *name* is already a dict (with ``en_US`` / ``zh_Hans`` keys) it is
        returned as-is.  A plain string is wrapped into an I18nObject so the
        frontend ``extractI18nObject`` helper never receives an unexpected type.
        """
        if isinstance(name, dict):
            return name
        return {'en_US': str(name), 'zh_Hans': str(name)}

    def _enrich_kb_dict(self, kb_dict: dict, engine_map: dict) -> None:
        """Helper to inject engine info into KB dict."""
        plugin_id = kb_dict.get('rag_engine_plugin_id')

        # Default fallback structure — name must be I18nObject for frontend compatibility
        fallback_name = self._to_i18n_name(plugin_id or 'Internal (Legacy)')
        fallback_info = {
            'plugin_id': plugin_id,
            'name': fallback_name,
            'capabilities': [],
        }

        if not plugin_id:
            kb_dict['rag_engine'] = fallback_info
            return

        engine_info = engine_map.get(plugin_id)
        if engine_info:
            kb_dict['rag_engine'] = {
                'plugin_id': plugin_id,
                'name': self._to_i18n_name(engine_info.get('name', plugin_id)),
                'capabilities': engine_info.get('capabilities', []),
            }
        else:
            kb_dict['rag_engine'] = fallback_info

    async def create_knowledge_base(
        self,
        name: str,
        rag_engine_plugin_id: str,
        creation_settings: dict,
        description: str = '',
        embedding_model_uuid: str = '',
    ) -> persistence_rag.KnowledgeBase:
        """Create a new knowledge base using a RAG plugin."""
        # Validate that the RAG engine plugin exists
        if self.ap.plugin_connector.is_enable_plugin:
            try:
                engines = await self.ap.plugin_connector.list_rag_engines()
                engine_ids = [e.get('plugin_id') for e in engines]
                if rag_engine_plugin_id not in engine_ids:
                    raise ValueError(f'RAG engine plugin {rag_engine_plugin_id} not found')
            except ValueError:
                raise
            except Exception as e:
                self.ap.logger.warning(f'Failed to validate RAG engine plugin existence: {e}')

        kb_uuid = str(uuid.uuid4())
        # Use UUID as collection ID by default for isolation
        collection_id = kb_uuid

        kb_data = {
            'uuid': kb_uuid,
            'name': name,
            'description': description,
            'rag_engine_plugin_id': rag_engine_plugin_id,
            'collection_id': collection_id,
            'creation_settings': creation_settings,
            'embedding_model_uuid': embedding_model_uuid,
        }

        # Create Entity
        kb = persistence_rag.KnowledgeBase(**kb_data)

        # Persist
        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_rag.KnowledgeBase).values(kb_data))

        # Load into Runtime
        runtime_kb = await self.load_knowledge_base(kb)

        # Notify Plugin — rollback DB record and runtime entry on failure
        try:
            await runtime_kb._on_kb_create()
        except Exception:
            self.knowledge_bases.pop(kb_uuid, None)
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_rag.KnowledgeBase).where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
            )
            raise

        self.ap.logger.info(f'Created new Knowledge Base {name} ({kb_uuid}) using plugin {rag_engine_plugin_id}')
        return kb

    async def load_knowledge_bases_from_db(self):
        self.ap.logger.info('Loading knowledge bases from db...')

        self.knowledge_bases = {}

        # Load knowledge bases
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_rag.KnowledgeBase))
        knowledge_bases = result.all()

        for knowledge_base in knowledge_bases:
            try:
                await self.load_knowledge_base(knowledge_base)
            except Exception as e:
                self.ap.logger.error(
                    f'Error loading knowledge base {knowledge_base.uuid}: {e}\n{traceback.format_exc()}'
                )

    async def load_knowledge_base(
        self,
        knowledge_base_entity: persistence_rag.KnowledgeBase | sqlalchemy.Row | dict,
    ) -> RuntimeKnowledgeBase:
        if isinstance(knowledge_base_entity, sqlalchemy.Row):
            # Safe access to _mapping for SQLAlchemy 1.4+
            knowledge_base_entity = persistence_rag.KnowledgeBase(**knowledge_base_entity._mapping)
        elif isinstance(knowledge_base_entity, dict):
            # Filter out non-database fields (like rag_engine which is computed)
            filtered_dict = {
                k: v for k, v in knowledge_base_entity.items() if k in persistence_rag.KnowledgeBase.ALL_DB_FIELDS
            }
            knowledge_base_entity = persistence_rag.KnowledgeBase(**filtered_dict)

        runtime_knowledge_base = RuntimeKnowledgeBase(ap=self.ap, knowledge_base_entity=knowledge_base_entity)

        await runtime_knowledge_base.initialize()

        self.knowledge_bases[runtime_knowledge_base.get_uuid()] = runtime_knowledge_base

        return runtime_knowledge_base

    async def get_knowledge_base_by_uuid(self, kb_uuid: str) -> KnowledgeBaseInterface | None:
        return self.knowledge_bases.get(kb_uuid)

    async def remove_knowledge_base_from_runtime(self, kb_uuid: str):
        self.knowledge_bases.pop(kb_uuid, None)

    async def delete_knowledge_base(self, kb_uuid: str):
        kb = self.knowledge_bases.pop(kb_uuid, None)
        if kb is not None:
            await kb.dispose()
        else:
            self.ap.logger.warning(f'Knowledge base {kb_uuid} not found in runtime, skipping plugin notification')
