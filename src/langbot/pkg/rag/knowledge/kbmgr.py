from __future__ import annotations
import traceback
import uuid
import zipfile
import io
from .services import parser, chunker
from langbot.pkg.core import app
from langbot.pkg.rag.knowledge.services.embedder import Embedder
from langbot.pkg.rag.knowledge.services.retriever import Retriever
import sqlalchemy
from langbot.pkg.entity.persistence import rag as persistence_rag
from langbot.pkg.core import taskmgr
from langbot.pkg.entity.rag import retriever as retriever_entities


class RuntimeKnowledgeBase:
    ap: app.Application

    knowledge_base_entity: persistence_rag.KnowledgeBase

    parser: parser.FileParser

    chunker: chunker.Chunker

    embedder: Embedder

    retriever: Retriever

    def __init__(self, ap: app.Application, knowledge_base_entity: persistence_rag.KnowledgeBase):
        self.ap = ap
        self.knowledge_base_entity = knowledge_base_entity
        self.parser = parser.FileParser(ap=self.ap)
        self.chunker = chunker.Chunker(ap=self.ap)
        self.embedder = Embedder(ap=self.ap)
        self.retriever = Retriever(ap=self.ap)
        # 传递kb_id给retriever
        self.retriever.kb_id = knowledge_base_entity.uuid

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

            task_context.set_current_action('Parsing file')
            # parse file
            text = await self.parser.parse(file.file_name, file.extension)
            if not text:
                raise Exception(f'No text extracted from file {file.file_name}')

            task_context.set_current_action('Chunking file')
            # chunk file
            chunks_texts = await self.chunker.chunk(text)
            if not chunks_texts:
                raise Exception(f'No chunks extracted from file {file.file_name}')

            task_context.set_current_action('Embedding chunks')

            embedding_model = await self.ap.model_mgr.get_embedding_model_by_uuid(
                self.knowledge_base_entity.embedding_model_uuid
            )
            # embed chunks
            await self.embedder.embed_and_store(
                kb_id=self.knowledge_base_entity.uuid,
                file_id=file.uuid,
                chunks=chunks_texts,
                embedding_model=embedding_model,
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
        extension = file_name.split('.')[-1].lower()

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

                file_extension = file_info.filename.split('.')[-1].lower()
                if file_extension not in supported_extensions:
                    self.ap.logger.debug(f'Skipping unsupported file in ZIP: {file_info.filename}')
                    continue

                try:
                    file_content = zip_ref.read(file_info.filename)

                    base_name = file_info.filename.replace('/', '_').replace('\\', '_')
                    extension = base_name.split('.')[-1]
                    file_name = base_name.split('.')[0]

                    if file_name.startswith('__MACOSX'):
                        continue

                    extracted_file_id = file_name + '_' + str(uuid.uuid4())[:8] + '.' + extension
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

    async def retrieve(self, query: str, top_k: int) -> list[retriever_entities.RetrieveResultEntry]:
        embedding_model = await self.ap.model_mgr.get_embedding_model_by_uuid(
            self.knowledge_base_entity.embedding_model_uuid
        )
        return await self.retriever.retrieve(self.knowledge_base_entity.uuid, query, embedding_model, top_k)

    async def delete_file(self, file_id: str):
        # delete vector
        await self.ap.vector_db_mgr.vector_db.delete_by_file_id(self.knowledge_base_entity.uuid, file_id)

        # delete chunk
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_rag.Chunk).where(persistence_rag.Chunk.file_id == file_id)
        )

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_rag.File).where(persistence_rag.File.uuid == file_id)
        )

    async def dispose(self):
        await self.ap.vector_db_mgr.vector_db.delete_collection(self.knowledge_base_entity.uuid)


class RAGManager:
    ap: app.Application

    knowledge_bases: list[RuntimeKnowledgeBase]

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.knowledge_bases = []

    async def initialize(self):
        await self.load_knowledge_bases_from_db()

    async def load_knowledge_bases_from_db(self):
        self.ap.logger.info('Loading knowledge bases from db...')

        self.knowledge_bases = []

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
            knowledge_base_entity = persistence_rag.KnowledgeBase(**knowledge_base_entity._mapping)
        elif isinstance(knowledge_base_entity, dict):
            knowledge_base_entity = persistence_rag.KnowledgeBase(**knowledge_base_entity)

        runtime_knowledge_base = RuntimeKnowledgeBase(ap=self.ap, knowledge_base_entity=knowledge_base_entity)

        await runtime_knowledge_base.initialize()

        self.knowledge_bases.append(runtime_knowledge_base)

        return runtime_knowledge_base

    async def get_knowledge_base_by_uuid(self, kb_uuid: str) -> RuntimeKnowledgeBase | None:
        for kb in self.knowledge_bases:
            if kb.knowledge_base_entity.uuid == kb_uuid:
                return kb
        return None

    async def remove_knowledge_base_from_runtime(self, kb_uuid: str):
        for kb in self.knowledge_bases:
            if kb.knowledge_base_entity.uuid == kb_uuid:
                self.knowledge_bases.remove(kb)
                return

    async def delete_knowledge_base(self, kb_uuid: str):
        for kb in self.knowledge_bases:
            if kb.knowledge_base_entity.uuid == kb_uuid:
                await kb.dispose()
                self.knowledge_bases.remove(kb)
                return
