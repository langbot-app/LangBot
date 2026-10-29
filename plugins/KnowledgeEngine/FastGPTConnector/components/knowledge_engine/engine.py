from __future__ import annotations

import json
import logging

from components.shared_state import (
    AmbiguousMutationError,
    ConfigStore,
    FenceLifecycleError,
    is_ambiguous_http_failure,
    normalize_api_base_url,
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


class FastGPTConnector(ConfigStore, KnowledgeEngine):
    """Knowledge Engine powered by FastGPT Datasets.

    Supports retrieval via FastGPT's search API, document ingestion by
    uploading files to FastGPT datasets, and document deletion by removing
    collections.
    """

    @classmethod
    def get_capabilities(cls) -> list[str]:
        return [KnowledgeEngineCapability.DOC_INGESTION, KnowledgeEngineCapability.DOC_PARSING]

    # ========== Lifecycle Hooks ==========

    @serialized
    async def on_knowledge_base_create(self, kb_id: str, config: dict) -> None:
        """Persist knowledge-base config in installation-bound Host storage."""
        logger.info(f"[FastGPTKnowledgeEngine] Knowledge base created: {kb_id}")
        await self._save_config(kb_id, config)

    @serialized(allow_fenced=True)
    async def on_knowledge_base_delete(self, kb_id: str) -> None:
        """Tombstone the stored config and clear any fence for this knowledge base."""
        logger.info(f"[FastGPTKnowledgeEngine] Knowledge base deleted: {kb_id}")
        await self._save_config(kb_id, None)
        # Deleting the knowledge base is the operator path out of a fence: the
        # pending ambiguity is moot once it no longer exists.
        await self._state.clear_fence(self.plugin, kb_id)

    async def retrieve(self, context: RetrievalContext) -> RetrievalResponse:
        """Execute retrieval against FastGPT Dataset API."""
        config = context.creation_settings

        api_base_url = config.get("api_base_url", "http://localhost:3000").rstrip("/")
        api_key = config.get("api_key")
        dataset_id = config.get("dataset_id")
        limit = config.get("limit", 5000)
        similarity = config.get("similarity", 0.0)
        search_mode = config.get("search_mode", "embedding")
        using_rerank = config.get("using_rerank", False)
        dataset_search_using_extension_query = config.get("dataset_search_using_extension_query", False)
        dataset_search_extension_model = config.get("dataset_search_extension_model", "")
        dataset_search_extension_bg = config.get("dataset_search_extension_bg", "")

        if not api_key or not dataset_id:
            logger.error(
                f"[FastGPTKnowledgeEngine] Missing required configuration. "
                f"Config keys: {list(config.keys())}"
            )
            return RetrievalResponse(results=[], total_found=0)

        url = f"{api_base_url}/api/core/dataset/searchTest"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "datasetId": dataset_id,
            "text": context.query,
            "limit": int(limit),
            "similarity": float(similarity),
            "searchMode": search_mode,
            "usingReRank": bool(using_rerank),
        }

        if dataset_search_using_extension_query:
            payload["datasetSearchUsingExtensionQuery"] = True
            if dataset_search_extension_model:
                payload["datasetSearchExtensionModel"] = dataset_search_extension_model
            if dataset_search_extension_bg:
                payload["datasetSearchExtensionBg"] = dataset_search_extension_bg

        results: list[RetrievalResultEntry] = []
        try:
            async with self.http_client() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=30.0)
                response.raise_for_status()
                result = response.json()

                if result.get("code", 200) != 200:
                    raise ValueError("FastGPT search returned an unsuccessful response")
                data = result.get("data", [])
                records = data.get("list", []) if isinstance(data, dict) else data
                for record in records:
                    content_parts = []
                    if record.get("q"):
                        content_parts.append(record["q"])
                    if record.get("a"):
                        content_parts.append(record["a"])
                    content_text = "\n".join(content_parts) if content_parts else ""

                    score = record.get("score")
                    if isinstance(score, list):
                        # Current FastGPT returns typed scores; older versions
                        # returned a scalar. Prefer the final reranker when present.
                        typed_scores = {item.get("type"): item.get("value") for item in score if isinstance(item, dict)}
                        score = next((typed_scores[k] for k in ("rerank", "embedding", "fullText") if typed_scores.get(k) is not None), 0.0)
                    if score is None:
                        score = 0.0

                    results.append(
                        RetrievalResultEntry(
                            id=record.get("id", ""),
                            content=[ContentElement.from_text(content_text)],
                            metadata={
                                "dataset_id": record.get("datasetId", ""),
                                "collection_id": record.get("collectionId", ""),
                                "source_name": record.get("sourceName", ""),
                                "source_id": record.get("sourceId", ""),
                            },
                            distance=1.0 - float(score),
                            score=float(score),
                        )
                    )

            logger.info(f"[FastGPTKnowledgeEngine] Retrieved {len(results)} chunks from FastGPT.")
        except Exception:
            logger.exception("[FastGPTKnowledgeEngine] Error during retrieval")

        return RetrievalResponse(results=results, total_found=len(results))

    @serialized
    async def ingest(self, context: IngestionContext) -> IngestionResult:
        """Upload a file to FastGPT dataset as a new collection."""
        doc_id = context.file_object.metadata.document_id
        filename = context.file_object.metadata.filename

        config = context.creation_settings
        api_base_url = config.get("api_base_url", "http://localhost:3000").rstrip("/")
        api_key = config.get("api_key")
        dataset_id = config.get("dataset_id")

        if not api_key or not dataset_id:
            logger.error(
                f"[FastGPTKnowledgeEngine] Missing required configuration for ingestion. "
                f"Config keys: {list(config.keys())}"
            )
            return IngestionResult(
                document_id=doc_id,
                status=DocumentStatus.FAILED,
                error_message="Missing api_key or dataset_id in configuration.",
            )

        kb_id = context.knowledge_base_id
        await self._save_config(kb_id, config)
        if await self._load_document(kb_id, doc_id) is not None:
            raise RuntimeError('Existing upload intent; reconcile before retry')

        # 1. Read file content from Host
        try:
            file_bytes = await self.plugin.get_knowledge_file_stream(context.file_object.storage_path)
        except Exception as e:
            logger.error(f"[FastGPTKnowledgeEngine] Failed to read file: {e}")
            return IngestionResult(
                document_id=doc_id,
                status=DocumentStatus.FAILED,
                error_message=f"Could not read file: {e}",
            )

        upstream_target = normalize_api_base_url(api_base_url)
        await self._save_document(kb_id, doc_id, {'upstream_id': '', 'dataset_id': dataset_id,
            'status': 'pending', 'api_base_url': upstream_target})
        # 2. Upload file to FastGPT dataset
        url = f"{api_base_url}/api/core/dataset/collection/create/localFile"
        headers = {
            "Authorization": f"Bearer {api_key}",
        }
        data_json = json.dumps({
            "datasetId": dataset_id,
            "trainingType": "chunk",
            "chunkSettingMode": "auto",
            "chunkSize": 512,
        })

        async def upload():
            async with self.http_client() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    files={"file": (filename, file_bytes)},
                    data={"data": data_json},
                    timeout=120.0,
                )
                response.raise_for_status()
                result = response.json()
            if result.get("code") != 200:
                # The provider answered: the upload was rejected, so no Host
                # record is written and the fence can be released.
                return None, None, result.get("message") or "Unknown error from FastGPT"
            resp_data = result.get("data", {})
            collection_id = resp_data.get("collectionId", "")
            if not isinstance(collection_id, str) or not collection_id:
                raise AmbiguousMutationError("FastGPT upload omitted upstream collection ID; outcome requires reconciliation")
            insert_len = (resp_data.get("results") or {}).get("insertLen", 0)
            # The mapping is recorded before the fence is released: a
            # cancellation or a Host failure here must not leave an uploaded
            # collection with no durable record of it.
            try:
                await self._save_document(kb_id, doc_id, {'upstream_id': collection_id,
                    'dataset_id': dataset_id, 'status': 'created',
                    'api_base_url': upstream_target})
            except Exception as exc:
                # The collection already exists. A Host persistence error must
                # preserve the fence and surface as interrupted, not return the
                # unrelated Host UUID as a failed upstream document identity.
                raise AmbiguousMutationError(
                    'FastGPT collection created but mapping commit failed; reconcile before retry'
                ) from exc
            return collection_id, insert_len, None

        try:
            # Pre-persisted intent: the wrapped operation covers the request, the
            # response validation and the Host mapping write, so the fence is
            # released only once the outcome has been recorded.
            collection_id, insert_len, error = await self._state.dispatched(
                self.plugin, kb_id, upload, 'FastGPT upload outcome unknown'
            )

            if error is not None:
                logger.error(f"[FastGPTKnowledgeEngine] Upload failed: {error}")
                return IngestionResult(
                    document_id=doc_id,
                    status=DocumentStatus.FAILED,
                    error_message=error,
                )

            logger.info(
                f"[FastGPTKnowledgeEngine] File uploaded: {filename} -> "
                f"collectionId={collection_id}, insertLen={insert_len}"
            )

            return IngestionResult(
                document_id=collection_id,
                status=DocumentStatus.PROCESSING,
                chunks_created=insert_len,
            )

        except (AmbiguousMutationError, FenceLifecycleError):
            # An already-dispatched upload with an unknown outcome, or a mutation
            # that was never dispatched: the caller must see it.
            raise
        except httpx.HTTPStatusError as e:
            if is_ambiguous_http_failure(e):
                # A 5xx or gateway answer is not proof the upload was not
                # applied, so it is not a rejection: the fence stays and the
                # caller must see the unknown outcome.
                raise AmbiguousMutationError(
                    f"FastGPT upload outcome unknown for {filename}: {e}"
                ) from e
            logger.error(f"[FastGPTKnowledgeEngine] Upload rejected for {filename}: {e}")
            return IngestionResult(
                document_id=doc_id,
                status=DocumentStatus.FAILED,
                error_message=str(e),
            )
        except Exception as e:
            logger.error(f"[FastGPTKnowledgeEngine] Ingestion failed for {filename}: {e}")
            return IngestionResult(
                document_id=doc_id,
                status=DocumentStatus.FAILED,
                error_message=str(e),
            )

    @serialized
    async def delete_document(self, kb_id: str, document_id: str) -> bool:
        """Delete a collection from FastGPT dataset."""
        mapping = await self._load_document(kb_id, document_id)
        if not mapping or not mapping['upstream_id'] or mapping['status'] != 'created':
            return False
        config = await self._load_config(kb_id)
        if not config:
            logger.error(
                f"[FastGPTKnowledgeEngine] No stored config for kb_id={kb_id}. "
                "Cannot delete document."
            )
            return False

        api_base_url = config.get("api_base_url", "http://localhost:3000").rstrip("/")
        api_key = config.get("api_key")

        if not api_key:
            logger.error("[FastGPTKnowledgeEngine] Missing api_key in stored config.")
            return False

        url = f"{api_base_url}/api/core/dataset/collection/delete"
        if mapping['dataset_id'] != config.get('dataset_id'):
            raise RuntimeError('Dataset changed; reconcile before deletion')
        if mapping.get('api_base_url') != normalize_api_base_url(api_base_url):
            # The mapping names the upstream instance that owns the collection;
            # replaying the delete against another target would remove an
            # unrelated collection, so this must fail before any remote request.
            raise RuntimeError('Upstream target changed; reconcile before deletion')
        headers = {"Authorization": f"Bearer {api_key}"}

        async def delete_upstream():
            async with self.http_client() as client:
                response = await client.delete(
                    url, params={"id": mapping['upstream_id']}, headers=headers, timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
            if result.get("code") != 200:
                # The provider answered: the delete was rejected, so there is
                # nothing to record and the fence can be released.
                return False, result.get("message") or "Unknown error"
            # The tombstone is recorded before the fence is released: a
            # cancellation or a Host failure here must not leave a deleted
            # collection that the mapping still calls created.
            await self._save_document(kb_id, mapping['host_document_id'], {**mapping, 'status': 'deleted'})
            return True, None

        try:
            deleted, error = await self._state.dispatched(
                self.plugin, kb_id, delete_upstream, 'FastGPT delete outcome unknown'
            )

            if not deleted:
                logger.error(
                    f"[FastGPTKnowledgeEngine] Delete failed for collection={document_id}: {error}"
                )
                return False

            logger.info(
                f"[FastGPTKnowledgeEngine] Collection deleted: {document_id}"
            )
            return True

        except (AmbiguousMutationError, FenceLifecycleError):
            # The delete was dispatched with an unknown outcome, or never
            # dispatched at all: the caller must not read this as a plain failure.
            raise
        except httpx.HTTPStatusError as e:
            if is_ambiguous_http_failure(e):
                # A 5xx or gateway answer is not proof the delete was not
                # applied, so it is not a rejection: the fence stays and the
                # caller must see the unknown outcome.
                raise AmbiguousMutationError(
                    f"FastGPT delete outcome unknown for collection={document_id}: {e}"
                ) from e
            # The provider answered, so the delete was rejected deterministically.
            logger.error(
                f"[FastGPTKnowledgeEngine] Delete rejected for collection={document_id}: {e}"
            )
            return False
        except Exception:
            logger.exception(
                f"[FastGPTKnowledgeEngine] Error deleting collection={document_id}"
            )
            return False
