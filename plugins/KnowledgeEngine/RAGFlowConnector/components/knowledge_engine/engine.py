from __future__ import annotations

import logging

from components.shared_state import (
    AmbiguousMutationError,
    ConfigStore,
    FenceLifecycleError,
    serialized,
)

import httpx

from langbot_plugin.api.definition.components.knowledge_engine import KnowledgeEngine, KnowledgeEngineCapability
from langbot_plugin.api.entities.builtin.rag import (
    IngestionContext,
    IngestionResult,
    DocumentStatus,
    RetrievalContext,
    RetrievalResultEntry,
    RetrievalResponse,
)
from langbot_plugin.api.entities.builtin.provider.message import ContentElement

logger = logging.getLogger(__name__)


def _normalize_base_url(api_base_url: str) -> str:
    """Reduce a configured base URL to ``scheme://host[:port]/path``.

    A document mapping must name the upstream it was created on, so the stored
    form is canonical: scheme and host casing, a default port and a trailing
    slash never distinguish one deployment from another. An address without a
    host is stored stripped, so a later comparison still detects a change.
    """
    url = httpx.URL(api_base_url)
    if not url.host:
        return api_base_url.rstrip("/")
    default_port = {'http': 80, 'https': 443}.get(url.scheme)
    port = f":{url.port}" if url.port is not None and url.port != default_port else ""
    return f"{url.scheme}://{url.host}{port}{url.path.rstrip('/')}"


class RAGFlowConnector(ConfigStore, KnowledgeEngine):
    """Knowledge Engine powered by RAGFlow.

    Supports retrieval, document ingestion (upload + parse), and deletion
    via the RAGFlow HTTP API.
    """

    @classmethod
    def get_capabilities(cls) -> list[str]:
        return [KnowledgeEngineCapability.DOC_INGESTION, KnowledgeEngineCapability.DOC_PARSING]

    # ========== Lifecycle Hooks ==========

    @serialized
    async def on_knowledge_base_create(self, kb_id: str, config: dict) -> None:
        """Persist installation-bound configuration and validate dataset IDs."""
        logger.info(f"[RAGFlowKnowledgeEngine] Knowledge base created: {kb_id}")
        await self._save_config(kb_id, config)

        # Validate dataset IDs
        api_base_url = config.get("api_base_url", "http://localhost:9380").rstrip("/")
        api_key = config.get("api_key")
        dataset_ids_str = config.get("dataset_ids", "")

        if not api_key or not dataset_ids_str:
            return

        dataset_ids = [did.strip() for did in dataset_ids_str.split(",") if did.strip()]
        if not dataset_ids:
            return

        try:
            async with self.http_client() as client:
                resp = await client.get(
                    f"{api_base_url}/api/v1/datasets",
                    headers={"Authorization": f"Bearer {api_key}"},
                    params={"page": 1, "page_size": 100},
                    timeout=15.0,
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("code") != 0:
                    logger.warning(
                        f"[RAGFlowKnowledgeEngine] Failed to validate datasets: {data.get('message')}"
                    )
                    return

                existing_ids = {ds["id"] for ds in data.get("data", [])}
                for did in dataset_ids:
                    if did in existing_ids:
                        logger.info(f"[RAGFlowKnowledgeEngine] Dataset {did} validated OK")
                    else:
                        logger.warning(
                            f"[RAGFlowKnowledgeEngine] Dataset {did} NOT found in RAGFlow! "
                            "Please check the dataset ID."
                        )
        except Exception as e:
            logger.warning(f"[RAGFlowKnowledgeEngine] Dataset validation failed: {e}")

    @serialized(allow_fenced=True)
    async def on_knowledge_base_delete(self, kb_id: str) -> None:
        """Tombstone the stored configuration and clear any fence for this KB."""
        logger.info(f"[RAGFlowKnowledgeEngine] Knowledge base deleted: {kb_id}")
        await self._save_config(kb_id, None)
        # Deleting the knowledge base is the operator path out of a fence: the
        # pending ambiguity is moot once it no longer exists.
        await self._state.clear_fence(self.plugin, kb_id)

    async def retrieve(self, context: RetrievalContext) -> RetrievalResponse:
        """Execute retrieval against RAGFlow API."""
        config = context.creation_settings
        retrieval = context.retrieval_settings

        api_base_url = config.get("api_base_url", "http://localhost:9380").rstrip("/")
        api_key = config.get("api_key")
        dataset_ids_str = config.get("dataset_ids", "")
        top_k = retrieval.get("top_k", 1024)
        similarity_threshold = retrieval.get("similarity_threshold", 0.2)
        vector_similarity_weight = retrieval.get("vector_similarity_weight", 0.3)
        page_size = retrieval.get("page_size", 30)
        keyword = retrieval.get("keyword", False)
        rerank_id = retrieval.get("rerank_id", "")
        use_kg = retrieval.get("use_kg", False)

        if not api_key or not dataset_ids_str:
            logger.error(
                f"[RAGFlowKnowledgeEngine] Missing required configuration. "
                f"Config keys: {list(config.keys())}"
            )
            return RetrievalResponse(results=[], total_found=0)

        dataset_ids = [did.strip() for did in dataset_ids_str.split(",") if did.strip()]

        if not dataset_ids:
            logger.error("[RAGFlowKnowledgeEngine] No valid dataset IDs provided")
            return RetrievalResponse(results=[], total_found=0)

        url = f"{api_base_url}/api/v1/retrieval"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "question": context.query,
            "dataset_ids": dataset_ids,
            "page": 1,
            "page_size": int(page_size),
            "similarity_threshold": float(similarity_threshold),
            "vector_similarity_weight": float(vector_similarity_weight),
            "top_k": int(top_k),
            "keyword": keyword,
            "highlight": False,
            "use_kg": use_kg,
        }
        if rerank_id:
            payload["rerank_id"] = rerank_id

        results: list[RetrievalResultEntry] = []
        try:
            async with self.http_client() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=30.0)
                response.raise_for_status()
                data = response.json()

                if data.get("code") != 0:
                    logger.error(
                        f"[RAGFlowKnowledgeEngine] API returned error code: {data.get('code')}"
                    )
                    return RetrievalResponse(results=[], total_found=0)

                logger.info(
                    f"[RAGFlowKnowledgeEngine] Request: vector_weight={vector_similarity_weight}, "
                    f"top_k={top_k}, page_size={page_size}, threshold={similarity_threshold}, "
                    f"keyword={keyword}, rerank_id={rerank_id or 'None'}, use_kg={use_kg}, "
                    f"Response chunks: {len(data.get('data', {}).get('chunks', []))}"
                )

                for chunk in data.get("data", {}).get("chunks", []):
                    similarity = chunk.get("similarity")
                    if similarity is None:
                        similarity = 0.0

                    results.append(
                        RetrievalResultEntry(
                            id=chunk.get("id", ""),
                            content=[ContentElement.from_text(chunk.get("content", ""))],
                            metadata={
                                "document_id": chunk.get("document_id", ""),
                                "kb_id": chunk.get("kb_id", ""),
                                "document_keyword": chunk.get("document_keyword", ""),
                                "important_keywords": chunk.get("important_keywords", []),
                                "term_similarity": chunk.get("term_similarity", 0.0),
                                "vector_similarity": chunk.get("vector_similarity", 0.0),
                                "image_id": chunk.get("image_id"),
                            },
                            distance=1.0 - float(similarity),
                            score=float(similarity),
                        )
                    )

            logger.info(f"[RAGFlowKnowledgeEngine] Retrieved {len(results)} chunks from RAGFlow.")
        except Exception:
            logger.exception("[RAGFlowKnowledgeEngine] Error during retrieval")

        return RetrievalResponse(results=results, total_found=len(results))

    @serialized
    async def ingest(self, context: IngestionContext) -> IngestionResult:
        """Upload a file to RAGFlow and trigger parsing."""
        doc_id = context.file_object.metadata.document_id
        filename = context.file_object.metadata.filename

        config = context.creation_settings
        api_base_url = config.get("api_base_url", "http://localhost:9380").rstrip("/")
        api_key = config.get("api_key")
        dataset_ids_str = config.get("dataset_ids", "")

        if not api_key or not dataset_ids_str:
            logger.error(
                f"[RAGFlowKnowledgeEngine] Missing required configuration for ingestion. "
                f"Config keys: {list(config.keys())}"
            )
            return IngestionResult(
                document_id=doc_id,
                status=DocumentStatus.FAILED,
                error_message="Missing api_key or dataset_ids in configuration.",
            )

        dataset_ids = [did.strip() for did in dataset_ids_str.split(",") if did.strip()]
        if not dataset_ids:
            logger.error("[RAGFlowKnowledgeEngine] No valid dataset IDs provided for ingestion")
            return IngestionResult(
                document_id=doc_id,
                status=DocumentStatus.FAILED,
                error_message="No valid dataset IDs provided.",
            )

        # Use the first dataset as the ingestion target
        target_dataset_id = dataset_ids[0]
        # The mapping names the canonical upstream it was created on, so a later
        # configuration change cannot be mistaken for the same deployment.
        upstream_target = _normalize_base_url(api_base_url)

        # The Host knowledge-base id is the identity every entry point shares — the
        # create hook, deletion and the fence/lock scope — so the collection id,
        # which is a vector-store identity that need not equal it, is not used.
        kb_id = context.knowledge_base_id
        await self._save_config(kb_id, config)
        if await self._load_document(kb_id, doc_id) is not None:
            raise RuntimeError('Existing upload intent; reconcile before retry')

        # 1. Read file content from Host
        try:
            file_bytes = await self.plugin.get_knowledge_file_stream(context.file_object.storage_path)
        except Exception as e:
            logger.error(f"[RAGFlowKnowledgeEngine] Failed to get file content: {e}")
            return IngestionResult(
                document_id=doc_id,
                status=DocumentStatus.FAILED,
                error_message=f"Could not read file: {e}",
            )

        await self._save_document(kb_id, doc_id, {'upstream_id': '',
            'dataset_id': target_dataset_id, 'api_base_url': upstream_target,
            'status': 'pending'})
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            async with self.http_client() as client:
                # 2. Upload file to RAGFlow dataset
                upload_url = f"{api_base_url}/api/v1/datasets/{target_dataset_id}/documents"
                files = {"file": (filename, file_bytes)}

                async def upload():
                    response = await client.post(
                        upload_url, headers=headers, files=files, timeout=60.0
                    )
                    response.raise_for_status()
                    data = response.json()
                    if data.get("code") != 0:
                        # The provider answered: the upload was rejected, so no
                        # Host record is written and the fence can be released.
                        return None, data.get("message") or "Unknown upload error"
                    # Extract the document ID returned by RAGFlow
                    docs = data.get("data", [])
                    ragflow_doc_id = docs[0].get("id") if docs and isinstance(docs[0], dict) else None
                    if not isinstance(ragflow_doc_id, str) or not ragflow_doc_id:
                        raise AmbiguousMutationError("RAGFlow upload omitted upstream document ID; outcome requires reconciliation")
                    # The mapping is recorded before the fence is released: a
                    # cancellation or a Host failure here must not leave an
                    # uploaded document with no durable record of it.
                    await self._save_document(kb_id, doc_id, {'upstream_id': ragflow_doc_id,
                        'dataset_id': target_dataset_id, 'api_base_url': upstream_target,
                        'status': 'created'})
                    return ragflow_doc_id, None

                # The intent is persisted before the upload leaves, and the fence
                # is released only once the response was validated and the mapping
                # recorded.
                ragflow_doc_id, upload_error = await self._state.dispatched(
                    self.plugin, kb_id, upload, 'RAGFlow upload outcome unknown',
                )
                if upload_error is not None:
                    logger.error(f"[RAGFlowKnowledgeEngine] Upload failed: {upload_error}")
                    return IngestionResult(
                        document_id=doc_id,
                        status=DocumentStatus.FAILED,
                        error_message=f"RAGFlow upload error: {upload_error}",
                    )

                # 3. Trigger parsing
                chunks_url = f"{api_base_url}/api/v1/datasets/{target_dataset_id}/chunks"

                async def trigger_parse():
                    response = await client.post(
                        chunks_url,
                        headers={**headers, "Content-Type": "application/json"},
                        json={"document_ids": [ragflow_doc_id]},
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    data = response.json()
                    if data.get("code") != 0:
                        # The provider answered: parsing did not start, so the
                        # fence can be released.
                        return data.get("message") or "Unknown parsing error"
                    return None

                parse_error = await self._state.dispatched(
                    self.plugin, kb_id,
                    trigger_parse, 'RAGFlow parsing trigger outcome unknown',
                )
                if parse_error is not None:
                    logger.warning(
                        f"[RAGFlowKnowledgeEngine] Parsing trigger returned error: {parse_error}"
                    )
                    # Document was uploaded but parsing failed to start
                    return IngestionResult(
                        document_id=ragflow_doc_id,
                        status=DocumentStatus.FAILED,
                        error_message=f"RAGFlow parsing trigger error: {parse_error}",
                    )

                logger.info(
                    f"[RAGFlowKnowledgeEngine] File '{filename}' uploaded and parsing triggered "
                    f"(ragflow_doc_id={ragflow_doc_id})"
                )

                # Auto-trigger GraphRAG construction if enabled
                auto_graphrag = config.get("auto_graphrag", False)
                if auto_graphrag:
                    graphrag_url = f"{api_base_url}/api/v1/datasets/{target_dataset_id}/run_graphrag"

                    async def trigger_graphrag():
                        response = await client.post(
                            graphrag_url,
                            headers={**headers, "Content-Type": "application/json"},
                            timeout=30.0,
                        )
                        response.raise_for_status()
                        data = response.json()
                        if data.get("code") != 0:
                            # The provider answered: GraphRAG did not start. That
                            # is a resolved answer, not an unresolved state.
                            return None, data.get("message") or "unknown reason"
                        task = (data.get("data") or {}).get("graphrag_task_id", "unknown")
                        return task, None

                    # An unresolved GraphRAG outcome is not swallowed: it keeps
                    # its own fence and the chain must not continue over it (the
                    # RAPTOR dispatch would refuse it, and a later success must
                    # never clear this fence).
                    graphrag_task_id, graphrag_error = await self._state.dispatched(
                        self.plugin, kb_id, trigger_graphrag,
                        'RAGFlow GraphRAG trigger outcome unknown',
                    )
                    if graphrag_error is None:
                        logger.info(
                            f"[RAGFlowKnowledgeEngine] GraphRAG construction triggered "
                            f"(task_id={graphrag_task_id})"
                        )
                    else:
                        logger.warning(
                            f"[RAGFlowKnowledgeEngine] GraphRAG trigger returned: {graphrag_error}"
                        )

                # Auto-trigger RAPTOR construction if enabled
                auto_raptor = config.get("auto_raptor", False)
                if auto_raptor:
                    raptor_url = f"{api_base_url}/api/v1/datasets/{target_dataset_id}/run_raptor"

                    async def trigger_raptor():
                        response = await client.post(
                            raptor_url,
                            headers={**headers, "Content-Type": "application/json"},
                            timeout=30.0,
                        )
                        response.raise_for_status()
                        data = response.json()
                        if data.get("code") != 0:
                            # The provider answered: RAPTOR did not start.
                            return None, data.get("message") or "unknown reason"
                        task = (data.get("data") or {}).get("raptor_task_id", "unknown")
                        return task, None

                    raptor_task_id, raptor_error = await self._state.dispatched(
                        self.plugin, kb_id, trigger_raptor,
                        'RAGFlow RAPTOR trigger outcome unknown',
                    )
                    if raptor_error is None:
                        logger.info(
                            f"[RAGFlowKnowledgeEngine] RAPTOR construction triggered "
                            f"(task_id={raptor_task_id})"
                        )
                    else:
                        logger.warning(
                            f"[RAGFlowKnowledgeEngine] RAPTOR trigger returned: {raptor_error}"
                        )

                return IngestionResult(
                    document_id=ragflow_doc_id,
                    status=DocumentStatus.PROCESSING,
                )

        except (AmbiguousMutationError, FenceLifecycleError):
            # An already-dispatched mutation with an unknown outcome, or a
            # mutation that was never dispatched: the caller must see it.
            raise
        except Exception as e:
            # An ambiguous failure already left its pre-dispatch fence in place.
            logger.error(f"[RAGFlowKnowledgeEngine] Ingestion failed for {filename}: {e}")
            return IngestionResult(
                document_id=doc_id,
                status=DocumentStatus.FAILED,
                error_message=str(e),
            )

    @serialized
    async def delete_document(self, kb_id: str, document_id: str) -> bool:
        """Delete a document from RAGFlow."""
        mapping = await self._load_document(kb_id, document_id)
        if not mapping or not mapping['upstream_id'] or mapping['status'] != 'created':
            return False
        config = await self._load_config(kb_id)
        if not config:
            logger.error(
                f"[RAGFlowKnowledgeEngine] No stored config for kb_id={kb_id}, "
                "cannot delete document"
            )
            return False

        api_base_url = config.get("api_base_url", "http://localhost:9380").rstrip("/")
        api_key = config.get("api_key")
        dataset_ids_str = config.get("dataset_ids", "")

        if not api_key or not dataset_ids_str:
            logger.error(
                f"[RAGFlowKnowledgeEngine] Missing api_key or dataset_ids for kb_id={kb_id}"
            )
            return False

        dataset_ids = [did.strip() for did in dataset_ids_str.split(",") if did.strip()]
        if not dataset_ids:
            logger.error(
                f"[RAGFlowKnowledgeEngine] No valid dataset IDs for kb_id={kb_id}"
            )
            return False

        target_dataset_id = dataset_ids[0]

        if mapping['dataset_id'] != target_dataset_id:
            # Local validation before any remote call: deterministic, no fence.
            raise RuntimeError('Dataset changed; reconcile before deletion')
        if mapping.get('api_base_url') != _normalize_base_url(api_base_url):
            # The recorded upstream is not the configured one, so the document id
            # does not necessarily exist here; mappings written before the target
            # was recorded are equally unresolvable.
            raise RuntimeError('Upstream target changed; reconcile before deletion')

        url = f"{api_base_url}/api/v1/datasets/{target_dataset_id}/documents"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async def delete_upstream():
            async with self.http_client() as client:
                response = await client.request(
                    "DELETE", url, headers=headers,
                    json={"ids": [mapping['upstream_id']]},
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
            if data.get("code") != 0:
                # The provider answered: the delete was rejected, so there is
                # nothing to record and the fence can be released.
                return False, data.get("message") or "Unknown error"
            # The tombstone is recorded before the fence is released: a
            # cancellation or a Host failure here must not leave a deleted
            # document that the mapping still calls created.
            await self._save_document(kb_id, mapping['host_document_id'], {**mapping, 'status': 'deleted'})
            return True, None

        try:
            deleted, error = await self._state.dispatched(
                self.plugin, kb_id, delete_upstream, 'RAGFlow delete outcome unknown',
            )

            if not deleted:
                logger.error(
                    f"[RAGFlowKnowledgeEngine] Delete failed for doc={document_id}: {error}"
                )
                return False

            logger.info(
                f"[RAGFlowKnowledgeEngine] Document {document_id} deleted from "
                f"dataset {target_dataset_id}"
            )
            return True

        except (AmbiguousMutationError, FenceLifecycleError):
            # The delete was dispatched with an unknown outcome, or never
            # dispatched at all: the caller must not read this as a plain failure.
            raise
        except httpx.HTTPStatusError as e:
            # The provider answered, so this is not a transport ambiguity: a 4xx
            # rejection is a resolved failure whose fence was released, while a
            # 5xx keeps its fence (the provider or an intermediary may have
            # committed the delete and then failed), so the next mutation for
            # this knowledge base is still refused.
            logger.error(
                f"[RAGFlowKnowledgeEngine] Delete rejected for doc={document_id}: {e}"
            )
            return False
        except Exception:
            # An ambiguous failure already left its pre-dispatch fence in place.
            logger.exception(
                f"[RAGFlowKnowledgeEngine] Error deleting document {document_id}"
            )
            return False
