from __future__ import annotations
import io
import mimetypes
import os.path
import traceback
import uuid
import zipfile
from typing import Any

import sqlalchemy
from langbot_plugin.api.entities.builtin.rag import context as rag_context

from langbot.pkg.api.http.authz import WorkspaceRequiredError
from langbot.pkg.api.http.context import ExecutionContext, RequestContext
from langbot.pkg.api.http.service.tenant import TenantContext, require_workspace_uuid
from langbot.pkg.core import app, taskmgr
from langbot.pkg.entity.persistence import rag as persistence_rag
from langbot.pkg.workspace.errors import WorkspaceNotFoundError

from .base import KnowledgeBaseInterface


class RuntimeKnowledgeBase(KnowledgeBaseInterface):
    ap: app.Application

    knowledge_base_entity: persistence_rag.KnowledgeBase

    def __init__(
        self,
        ap: app.Application,
        knowledge_base_entity: persistence_rag.KnowledgeBase,
        execution_context: ExecutionContext,
    ):
        super().__init__(ap)
        self.knowledge_base_entity = knowledge_base_entity
        self.execution_context = execution_context

    async def initialize(self):
        pass

    async def _assert_execution_context(self, execution_context: ExecutionContext) -> None:
        """Reject stale or cross-Workspace runtime access."""

        if not isinstance(execution_context, ExecutionContext):
            raise WorkspaceRequiredError('ExecutionContext is required for knowledge runtime access')
        if (
            execution_context.instance_uuid != self.execution_context.instance_uuid
            or execution_context.workspace_uuid != self.execution_context.workspace_uuid
            or execution_context.placement_generation != self.execution_context.placement_generation
        ):
            raise WorkspaceNotFoundError('Knowledge base not found')
        if self.knowledge_base_entity.workspace_uuid != execution_context.workspace_uuid:
            raise WorkspaceNotFoundError('Knowledge base not found')
        binding = await self.ap.workspace_service.get_execution_binding(
            execution_context.workspace_uuid,
            expected_generation=execution_context.placement_generation,
        )
        if binding.instance_uuid != execution_context.instance_uuid:
            raise WorkspaceNotFoundError('Knowledge base not found')

    async def _require_plugin_runtime_context(
        self,
        execution_context: ExecutionContext,
    ) -> ExecutionContext:
        """Fence every singleton Plugin Runtime call to this runtime KB."""

        await self._assert_execution_context(execution_context)
        return await self.ap.plugin_connector.require_workspace_context(execution_context)

    def _require_upload_object_key(
        self,
        execution_context: ExecutionContext,
        object_key: str,
    ) -> None:
        """Reject raw, cross-Workspace, stale, or non-upload object keys."""

        try:
            self.ap.storage_mgr.require_scoped_object_key(
                execution_context,
                object_key,
                expected_owner_type='upload_document',
            )
        except (WorkspaceRequiredError, ValueError) as exc:
            raise WorkspaceNotFoundError('Upload not found') from exc

    async def _store_file_task(
        self,
        execution_context: ExecutionContext,
        file: persistence_rag.File,
        task_context: taskmgr.TaskContext,
        parser_plugin_id: str | None = None,
    ):
        await self._assert_execution_context(execution_context)
        self._require_upload_object_key(execution_context, file.file_name)
        try:
            # set file status to processing
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_rag.File)
                .where(persistence_rag.File.workspace_uuid == execution_context.workspace_uuid)
                .where(persistence_rag.File.uuid == file.uuid)
                .values(status='processing')
            )

            task_context.set_current_action('Processing file')

            # Get file size from storage
            file_size = await self.ap.storage_mgr.size_scoped_object_key(
                execution_context,
                file.file_name,
                expected_owner_type='upload_document',
            )

            # Detect MIME type from extension
            mime_type, _ = mimetypes.guess_type(file.file_name)
            if mime_type is None:
                mime_type = 'application/octet-stream'

            # If a parser plugin is specified, call it before ingestion
            parsed_content = None
            if parser_plugin_id:
                task_context.set_current_action('Parsing file')
                file_bytes = await self.ap.storage_mgr.load_scoped_object_key(
                    execution_context,
                    file.file_name,
                    expected_owner_type='upload_document',
                )
                parse_context = {
                    'mime_type': mime_type,
                    'filename': file.file_name,
                    'metadata': {},
                }
                await self._require_plugin_runtime_context(execution_context)
                parsed_content = await self.ap.plugin_connector.call_parser(parser_plugin_id, parse_context, file_bytes)

            # Call plugin to ingest document
            result = await self._ingest_document(
                execution_context,
                {
                    'document_id': file.uuid,
                    'filename': file.file_name,
                    'extension': file.extension,
                    'file_size': file_size,
                    'mime_type': mime_type,
                },
                file.file_name,  # storage path
                parsed_content=parsed_content,
            )

            # Check plugin result status
            if result.get('status') == 'failed':
                error_msg = result.get('error_message', 'Plugin ingestion returned failed status')
                raise Exception(error_msg)

            # set file status to completed
            await self._assert_execution_context(execution_context)
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_rag.File)
                .where(persistence_rag.File.workspace_uuid == execution_context.workspace_uuid)
                .where(persistence_rag.File.uuid == file.uuid)
                .values(status='completed')
            )

        except Exception as e:
            self.ap.logger.error(f'Error storing file {file.uuid}: {e}')
            traceback.print_exc()
            # A stale placement is fenced from all writes, including failure
            # status updates from an old background task.
            try:
                await self._assert_execution_context(execution_context)
            except Exception:
                self.ap.logger.warning(f'Skipping stale RAG task status update for file {file.uuid}')
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.update(persistence_rag.File)
                    .where(persistence_rag.File.workspace_uuid == execution_context.workspace_uuid)
                    .where(persistence_rag.File.uuid == file.uuid)
                    .values(status='failed')
                )

            raise
        finally:
            # An old background task must not touch an upload after its
            # placement generation has been fenced off.
            try:
                await self._assert_execution_context(execution_context)
                await self.ap.storage_mgr.delete_scoped_object_key(
                    execution_context,
                    file.file_name,
                    expected_owner_type='upload_document',
                )
            except (WorkspaceRequiredError, WorkspaceNotFoundError):
                self.ap.logger.warning(f'Skipping stale RAG upload cleanup for file {file.uuid}')

    async def store_file(
        self,
        execution_context: ExecutionContext,
        file_id: str,
        parser_plugin_id: str | None = None,
    ) -> str:
        await self._assert_execution_context(execution_context)
        self._require_upload_object_key(execution_context, file_id)
        # pre checking
        if not await self.ap.storage_mgr.exists_scoped_object_key(
            execution_context,
            file_id,
            expected_owner_type='upload_document',
        ):
            raise WorkspaceNotFoundError('Upload not found')

        file_name = file_id
        _, ext = os.path.splitext(file_name)
        extension = ext.lstrip('.').lower() if ext else ''

        if extension == 'zip':
            return await self._store_zip_file(execution_context, file_id, parser_plugin_id=parser_plugin_id)

        file_uuid = str(uuid.uuid4())
        kb_id = self.knowledge_base_entity.uuid

        file_obj_data = {
            'uuid': file_uuid,
            'workspace_uuid': execution_context.workspace_uuid,
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
            self._store_file_task(
                execution_context,
                file_obj,
                task_context=ctx,
                parser_plugin_id=parser_plugin_id,
            ),
            kind='knowledge-operation',
            name=f'knowledge-store-file-{file_id}',
            label=f'Store file {file_id}',
            context=ctx,
            instance_uuid=execution_context.instance_uuid,
            workspace_uuid=execution_context.workspace_uuid,
            placement_generation=execution_context.placement_generation,
        )
        return wrapper.id

    async def _store_zip_file(
        self,
        execution_context: ExecutionContext,
        zip_file_id: str,
        parser_plugin_id: str | None = None,
    ) -> str:
        """Handle ZIP file by extracting each document and storing them separately."""
        await self._assert_execution_context(execution_context)
        self._require_upload_object_key(execution_context, zip_file_id)
        self.ap.logger.info(f'Processing ZIP file: {zip_file_id}')

        zip_bytes = await self.ap.storage_mgr.load_scoped_object_key(
            execution_context,
            zip_file_id,
            expected_owner_type='upload_document',
        )

        supported_extensions = {'txt', 'pdf', 'docx', 'md', 'html'}
        stored_file_tasks = []

        try:
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
                        extracted_object_key = await self.ap.storage_mgr.save_scoped(
                            execution_context,
                            owner_type='upload_document',
                            owner=f'knowledge-base:{self.knowledge_base_entity.uuid}',
                            key=extracted_file_id,
                            value=file_content,
                        )

                        try:
                            task_id = await self.store_file(
                                execution_context,
                                extracted_object_key,
                                parser_plugin_id=parser_plugin_id,
                            )
                        except Exception:
                            await self.ap.storage_mgr.delete_scoped_object_key(
                                execution_context,
                                extracted_object_key,
                                expected_owner_type='upload_document',
                            )
                            raise
                        stored_file_tasks.append(task_id)

                        self.ap.logger.info(
                            f'Extracted and stored file from ZIP: {file_info.filename} -> {extracted_object_key}'
                        )

                    except Exception as e:
                        self.ap.logger.warning(f'Failed to extract file {file_info.filename} from ZIP: {e}')
                        continue

            if not stored_file_tasks:
                raise Exception('No supported files found in ZIP archive')

            self.ap.logger.info(
                f'Successfully processed ZIP file {zip_file_id}, extracted {len(stored_file_tasks)} files'
            )
            return stored_file_tasks[0] if stored_file_tasks else ''
        finally:
            try:
                await self._assert_execution_context(execution_context)
                await self.ap.storage_mgr.delete_scoped_object_key(
                    execution_context,
                    zip_file_id,
                    expected_owner_type='upload_document',
                )
            except FileNotFoundError:
                pass
            except (WorkspaceRequiredError, WorkspaceNotFoundError):
                self.ap.logger.warning(f'Skipping stale RAG ZIP cleanup for upload {zip_file_id}')
            except Exception as e:
                self.ap.logger.warning(f'Failed to cleanup ZIP file {zip_file_id}: {e}')

    async def retrieve(
        self,
        execution_context: ExecutionContext,
        query: str,
        settings: dict | None = None,
    ) -> list[rag_context.RetrievalResultEntry]:
        await self._assert_execution_context(execution_context)
        # Merge stored retrieval_settings with per-request overrides
        stored = self.knowledge_base_entity.retrieval_settings or {}
        merged = {**stored, **(settings or {})}
        if 'top_k' not in merged:
            merged['top_k'] = 5  # fallback default

        response = await self._retrieve(execution_context, query, merged)

        results_data = response.get('results', [])
        entries = []
        for r in results_data:
            if isinstance(r, dict):
                entries.append(rag_context.RetrievalResultEntry(**r))
            elif isinstance(r, rag_context.RetrievalResultEntry):
                entries.append(r)
        return entries

    async def delete_file(self, execution_context: ExecutionContext, file_id: str):
        await self._assert_execution_context(execution_context)
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.File.uuid)
            .where(persistence_rag.File.workspace_uuid == execution_context.workspace_uuid)
            .where(persistence_rag.File.kb_id == self.knowledge_base_entity.uuid)
            .where(persistence_rag.File.uuid == file_id)
            .limit(1)
        )
        if result.first() is None:
            raise WorkspaceNotFoundError('Knowledge file not found')
        await self._delete_document(execution_context, file_id)

        # Also cleanup DB record
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_rag.File)
            .where(persistence_rag.File.workspace_uuid == execution_context.workspace_uuid)
            .where(persistence_rag.File.kb_id == self.knowledge_base_entity.uuid)
            .where(persistence_rag.File.uuid == file_id)
        )

    def get_uuid(self) -> str:
        """Get the UUID of the knowledge base"""
        return self.knowledge_base_entity.uuid

    def get_name(self) -> str:
        """Get the name of the knowledge base"""
        return self.knowledge_base_entity.name

    def get_knowledge_engine_plugin_id(self) -> str:
        """Get the Knowledge Engine plugin ID"""
        return self.knowledge_base_entity.knowledge_engine_plugin_id or ''

    async def dispose(self, execution_context: ExecutionContext):
        """Dispose the knowledge base, notifying the plugin to cleanup."""
        await self._assert_execution_context(execution_context)
        await self._on_kb_delete(execution_context)

    # ========== Plugin Communication Methods ==========

    async def _on_kb_create(self, execution_context: ExecutionContext) -> None:
        """Notify plugin about KB creation."""
        await self._assert_execution_context(execution_context)
        plugin_id = self.knowledge_base_entity.knowledge_engine_plugin_id
        if not plugin_id:
            return

        try:
            config = self.knowledge_base_entity.creation_settings or {}
            self.ap.logger.info(
                f'Calling RAG plugin {plugin_id}: on_knowledge_base_create(kb_id={self.knowledge_base_entity.uuid})'
            )
            await self._require_plugin_runtime_context(execution_context)
            await self.ap.plugin_connector.rag_on_kb_create(plugin_id, self.knowledge_base_entity.uuid, config)
        except Exception as e:
            self.ap.logger.error(f'Failed to notify plugin {plugin_id} on KB create: {e}')
            raise

    async def _on_kb_delete(self, execution_context: ExecutionContext) -> None:
        """Notify plugin about KB deletion."""
        await self._assert_execution_context(execution_context)
        plugin_id = self.knowledge_base_entity.knowledge_engine_plugin_id
        if not plugin_id:
            return

        await self._require_plugin_runtime_context(execution_context)
        try:
            self.ap.logger.info(
                f'Calling RAG plugin {plugin_id}: on_knowledge_base_delete(kb_id={self.knowledge_base_entity.uuid})'
            )
            await self.ap.plugin_connector.rag_on_kb_delete(plugin_id, self.knowledge_base_entity.uuid)
        except Exception as e:
            self.ap.logger.error(f'Failed to notify plugin {plugin_id} on KB delete: {e}')

    async def _ingest_document(
        self,
        execution_context: ExecutionContext,
        file_metadata: dict[str, Any],
        storage_path: str,
        parsed_content: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call plugin to ingest document."""
        await self._assert_execution_context(execution_context)
        kb = self.knowledge_base_entity
        plugin_id = kb.knowledge_engine_plugin_id
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
            'creation_settings': kb.creation_settings or {},
            'parsed_content': parsed_content,
        }

        await self._require_plugin_runtime_context(execution_context)
        try:
            result = await self.ap.plugin_connector.call_rag_ingest(plugin_id, context_data)
            return result
        except Exception as e:
            self.ap.logger.error(f'Plugin ingestion failed: {e}')
            raise

    async def _retrieve(
        self,
        execution_context: ExecutionContext,
        query: str,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        """Call plugin to retrieve documents.

        Raises:
            ValueError: If no RAG plugin is configured for this KB.
            Exception: If the plugin retrieval call fails.
        """
        await self._assert_execution_context(execution_context)
        kb = self.knowledge_base_entity
        plugin_id = kb.knowledge_engine_plugin_id
        if not plugin_id:
            raise ValueError(f'No RAG plugin ID configured for KB {kb.uuid}. Retrieval failed.')

        # Session context (e.g. session_name) stays in retrieval_settings
        # for plugins that need it. Do NOT move them into filters, as filters
        # are passed directly to vector_search by some plugins (e.g. LangRAG)
        # and would cause empty results when the metadata field doesn't exist.
        plugin_settings = dict(settings)
        filters = plugin_settings.pop('filters', {})

        retrieval_context = {
            'query': query,
            'knowledge_base_id': kb.uuid,
            'collection_id': kb.collection_id or kb.uuid,
            'retrieval_settings': plugin_settings,
            'creation_settings': kb.creation_settings or {},
            'filters': filters,
        }

        await self._require_plugin_runtime_context(execution_context)
        result = await self.ap.plugin_connector.call_rag_retrieve(
            plugin_id,
            retrieval_context,
        )
        return result

    async def _delete_document(self, execution_context: ExecutionContext, document_id: str) -> bool:
        """Call plugin to delete document."""
        await self._assert_execution_context(execution_context)
        kb = self.knowledge_base_entity
        plugin_id = kb.knowledge_engine_plugin_id
        if not plugin_id:
            return False

        self.ap.logger.info(f'Calling RAG plugin {plugin_id}: delete_document(doc_id={document_id})')

        await self._require_plugin_runtime_context(execution_context)
        try:
            return await self.ap.plugin_connector.call_rag_delete_document(plugin_id, document_id, kb.uuid)
        except Exception as e:
            self.ap.logger.error(f'Plugin document deletion failed: {e}')
            return False


class RAGManager:
    ap: app.Application

    knowledge_bases: dict[tuple[str, str], RuntimeKnowledgeBase]

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.knowledge_bases = {}

    async def initialize(self):
        await self.load_knowledge_bases_from_db()

    async def _to_execution_context(
        self,
        context: RequestContext | ExecutionContext,
    ) -> ExecutionContext:
        if isinstance(context, RequestContext):
            execution_context = ExecutionContext.from_request(context)
        elif isinstance(context, ExecutionContext):
            execution_context = context
        else:
            raise WorkspaceRequiredError('RequestContext or ExecutionContext is required')

        binding = await self.ap.workspace_service.get_execution_binding(
            execution_context.workspace_uuid,
            expected_generation=execution_context.placement_generation,
        )
        if binding.instance_uuid != execution_context.instance_uuid:
            raise WorkspaceNotFoundError('Workspace not found')
        return execution_context

    async def _get_engine_map(self, context: TenantContext) -> dict[str, dict]:
        engine_map: dict[str, dict] = {}
        connector = getattr(self.ap, 'plugin_connector', None)
        if connector is not None and connector.is_enable_plugin:
            await connector.require_workspace_context(context)
            try:
                engines = await connector.list_knowledge_engines()
                engine_map = {engine['plugin_id']: engine for engine in engines}
            except Exception as e:
                self.ap.logger.warning(f'Failed to list Knowledge Engines: {e}')
        return engine_map

    async def get_all_knowledge_base_details(self, context: TenantContext) -> list[dict]:
        """Get all knowledge bases with enriched Knowledge Engine details."""
        workspace_uuid = require_workspace_uuid(context)
        # 1. Get raw KBs from DB
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.KnowledgeBase).where(
                persistence_rag.KnowledgeBase.workspace_uuid == workspace_uuid
            )
        )
        knowledge_bases = result.all()

        # 2. Get all available Knowledge Engines for enrichment
        engine_map = await self._get_engine_map(context)

        # 3. Serialize and enrich
        kb_list = []
        for kb in knowledge_bases:
            kb_dict = self.ap.persistence_mgr.serialize_model(persistence_rag.KnowledgeBase, kb)
            self._enrich_kb_dict(kb_dict, engine_map)
            kb_list.append(kb_dict)

        return kb_list

    async def get_knowledge_base_details(self, context: TenantContext, kb_uuid: str) -> dict | None:
        """Get specific knowledge base with enriched Knowledge Engine details."""
        workspace_uuid = require_workspace_uuid(context)
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.KnowledgeBase)
            .where(persistence_rag.KnowledgeBase.workspace_uuid == workspace_uuid)
            .where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )
        kb = result.first()
        if not kb:
            return None

        kb_dict = self.ap.persistence_mgr.serialize_model(persistence_rag.KnowledgeBase, kb)

        # Fetch engines
        engine_map = await self._get_engine_map(context)

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
        plugin_id = kb_dict.get('knowledge_engine_plugin_id')

        # Default fallback structure — name must be I18nObject for frontend compatibility
        fallback_name = self._to_i18n_name(plugin_id or 'Internal (Legacy)')
        fallback_info = {
            'plugin_id': plugin_id,
            'name': fallback_name,
            'capabilities': [],
        }

        if not plugin_id:
            kb_dict['knowledge_engine'] = fallback_info
            return

        engine_info = engine_map.get(plugin_id)
        if engine_info:
            kb_dict['knowledge_engine'] = {
                'plugin_id': plugin_id,
                'name': self._to_i18n_name(engine_info.get('name', plugin_id)),
                'capabilities': engine_info.get('capabilities', []),
            }
        else:
            kb_dict['knowledge_engine'] = fallback_info

    async def create_knowledge_base(
        self,
        context: RequestContext | ExecutionContext,
        name: str,
        knowledge_engine_plugin_id: str,
        creation_settings: dict,
        retrieval_settings: dict | None = None,
        description: str = '',
    ) -> persistence_rag.KnowledgeBase:
        """Create a new knowledge base using a RAG plugin."""
        execution_context = await self._to_execution_context(context)
        # Validate that the Knowledge Engine plugin exists
        if self.ap.plugin_connector.is_enable_plugin:
            await self.ap.plugin_connector.require_workspace_context(execution_context)
            try:
                engines = await self.ap.plugin_connector.list_knowledge_engines()
                engine_ids = [e.get('plugin_id') for e in engines]
                if knowledge_engine_plugin_id not in engine_ids:
                    raise ValueError(f'Knowledge Engine plugin {knowledge_engine_plugin_id} not found')
            except ValueError:
                raise
            except Exception as e:
                self.ap.logger.warning(f'Failed to validate Knowledge Engine plugin existence: {e}')

        kb_uuid = str(uuid.uuid4())
        # Use UUID as collection ID by default for isolation
        collection_id = kb_uuid

        kb_data = {
            'uuid': kb_uuid,
            'workspace_uuid': execution_context.workspace_uuid,
            'name': name,
            'description': description,
            'knowledge_engine_plugin_id': knowledge_engine_plugin_id,
            'collection_id': collection_id,
            'creation_settings': creation_settings,
            'retrieval_settings': retrieval_settings or {},
        }

        # Create Entity
        kb = persistence_rag.KnowledgeBase(**kb_data)

        # Persist
        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_rag.KnowledgeBase).values(kb_data))

        # Load into Runtime
        runtime_kb = await self.load_knowledge_base(execution_context, kb)

        # Notify Plugin — rollback DB record and runtime entry on failure
        try:
            await runtime_kb._on_kb_create(execution_context)
        except Exception:
            self.knowledge_bases.pop((execution_context.workspace_uuid, kb_uuid), None)
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_rag.KnowledgeBase)
                .where(persistence_rag.KnowledgeBase.workspace_uuid == execution_context.workspace_uuid)
                .where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
            )
            raise

        self.ap.logger.info(f'Created new Knowledge Base {name} ({kb_uuid}) using plugin {knowledge_engine_plugin_id}')
        return kb

    async def load_knowledge_bases_from_db(self):
        self.ap.logger.info('Loading knowledge bases from db...')

        self.knowledge_bases = {}

        # Load knowledge bases
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_rag.KnowledgeBase))
        knowledge_bases = result.all()

        for knowledge_base in knowledge_bases:
            try:
                binding = await self.ap.workspace_service.get_execution_binding(knowledge_base.workspace_uuid)
                execution_context = ExecutionContext(
                    instance_uuid=binding.instance_uuid,
                    workspace_uuid=binding.workspace_uuid,
                    placement_generation=binding.placement_generation,
                )
                await self.load_knowledge_base(execution_context, knowledge_base)
            except Exception as e:
                self.ap.logger.error(
                    f'Error loading knowledge base {knowledge_base.uuid}: {e}\n{traceback.format_exc()}'
                )

    async def load_knowledge_base(
        self,
        context: RequestContext | ExecutionContext,
        knowledge_base_entity: persistence_rag.KnowledgeBase | sqlalchemy.Row | dict,
    ) -> RuntimeKnowledgeBase:
        if isinstance(knowledge_base_entity, sqlalchemy.Row):
            # Safe access to _mapping for SQLAlchemy 1.4+
            knowledge_base_entity = persistence_rag.KnowledgeBase(**knowledge_base_entity._mapping)
        elif isinstance(knowledge_base_entity, dict):
            # Filter out non-database fields (like knowledge_engine which is computed)
            filtered_dict = {
                k: v for k, v in knowledge_base_entity.items() if k in persistence_rag.KnowledgeBase.ALL_DB_FIELDS
            }
            knowledge_base_entity = persistence_rag.KnowledgeBase(**filtered_dict)

        execution_context = await self._to_execution_context(context)
        if knowledge_base_entity.workspace_uuid != execution_context.workspace_uuid:
            raise WorkspaceNotFoundError('Knowledge base not found')
        runtime_knowledge_base = RuntimeKnowledgeBase(
            ap=self.ap,
            knowledge_base_entity=knowledge_base_entity,
            execution_context=execution_context,
        )

        await runtime_knowledge_base.initialize()

        self.knowledge_bases[(execution_context.workspace_uuid, runtime_knowledge_base.get_uuid())] = (
            runtime_knowledge_base
        )

        return runtime_knowledge_base

    async def get_knowledge_base_by_uuid(
        self,
        context: RequestContext | ExecutionContext,
        kb_uuid: str,
    ) -> RuntimeKnowledgeBase | None:
        execution_context = await self._to_execution_context(context)
        return self.knowledge_bases.get((execution_context.workspace_uuid, kb_uuid))

    async def remove_knowledge_base_from_runtime(
        self,
        context: RequestContext | ExecutionContext,
        kb_uuid: str,
    ) -> None:
        execution_context = await self._to_execution_context(context)
        self.knowledge_bases.pop((execution_context.workspace_uuid, kb_uuid), None)

    async def delete_knowledge_base(
        self,
        context: RequestContext | ExecutionContext,
        kb_uuid: str,
    ) -> None:
        execution_context = await self._to_execution_context(context)
        kb = self.knowledge_bases.pop((execution_context.workspace_uuid, kb_uuid), None)
        if kb is not None:
            await kb.dispose(execution_context)
        else:
            self.ap.logger.warning(f'Knowledge base {kb_uuid} not found in runtime, skipping plugin notification')
