from __future__ import annotations

import json
import logging
from urllib.parse import urlsplit, urlunsplit

from components.shared_state import (
    AmbiguousMutationError,
    ConfigStore,
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


def _normalize_api_base_url(url: str) -> str:
    """Canonical provider target: ``scheme://host[:port]/path``, no trailing slash.

    Used to bind a stored document mapping to the upstream instance that created
    it, so a later configuration change is detected before any remote call.
    """
    parts = urlsplit(url or '')
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip('/'), '', ''))


class DifyDatasetsConnector(ConfigStore, KnowledgeEngine):
    """Knowledge Engine powered by Dify Datasets.

    Supports retrieval, document ingestion (file upload), and deletion
    via the Dify Dataset API.
    """

    @classmethod
    def get_capabilities(cls) -> list[str]:
        return [KnowledgeEngineCapability.DOC_INGESTION, KnowledgeEngineCapability.DOC_PARSING]

    # ========== Lifecycle Hooks ==========

    @serialized
    async def on_knowledge_base_create(self, kb_id: str, config: dict) -> None:
        """Persist the knowledge-base config for deletion after worker restart."""
        await self._save_config(kb_id, config)
        logger.info(f"[DifyDatasetsConnector] Knowledge base created: {kb_id}")

    @serialized(allow_fenced=True)
    async def on_knowledge_base_delete(self, kb_id: str) -> None:
        """Tombstone the stored config and clear any fence for this knowledge base."""
        await self._save_config(kb_id, None)
        # Deleting the knowledge base is the operator path out of a fence: the
        # pending ambiguity is moot once it no longer exists.
        await self._state.clear_fence(self.plugin, kb_id)
        logger.info(f"[DifyDatasetsConnector] Knowledge base deleted: {kb_id}")

    # ========== Helper Methods ==========

    async def _fetch_dataset_reranking_config(
        self, api_base_url: str, api_key: str, dataset_id: str
    ) -> dict:
        """Fetch the reranking model config from the Dify dataset settings."""
        url = f"{api_base_url}/datasets/{dataset_id}"
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            async with self.http_client() as client:
                response = await client.get(url, headers=headers, timeout=15.0)
                response.raise_for_status()
                data = response.json()
            retrieval_model = data.get("retrieval_model_dict") or data.get("retrieval_model") or {}
            reranking = retrieval_model.get("reranking_model", {})
            mode = retrieval_model.get("reranking_mode")
            logger.info(
                f"[DifyDatasetsConnector] Fetched dataset reranking config: "
                f"mode={mode}, provider={reranking.get('reranking_provider_name')}, "
                f"model={reranking.get('reranking_model_name')}"
            )
            return {
                "reranking_mode": mode or "reranking_model",
                "reranking_model": reranking,
            }
        except Exception:
            logger.exception("[DifyDatasetsConnector] Failed to fetch dataset reranking config")
            return {
                "reranking_mode": "reranking_model",
                "reranking_model": {"reranking_provider_name": "", "reranking_model_name": ""},
            }

    # ========== Core Methods ==========

    async def retrieve(self, context: RetrievalContext) -> RetrievalResponse:
        """Execute retrieval against Dify Dataset API."""
        config = context.creation_settings
        retrieval = context.retrieval_settings

        api_base_url = config.get("api_base_url", "https://api.dify.ai/v1").rstrip("/")
        api_key = config.get("dify_apikey")
        dataset_id = config.get("dataset_id")
        top_k = retrieval.get("top_k", 5)
        score_threshold_enabled = retrieval.get("score_threshold_enabled", False)
        score_threshold = retrieval.get("score_threshold", 0.5)
        search_method = retrieval.get("search_method", "semantic_search")
        reranking_enable = retrieval.get("reranking_enable", False)

        if not api_key or not dataset_id:
            logger.error(
                f"[DifyDatasetsConnector] Missing required configuration. "
                f"Config keys: {list(config.keys())}"
            )
            return RetrievalResponse(results=[], total_found=0)

        # Fetch reranking model config from Dify dataset when reranking is enabled
        reranking_mode = None
        reranking_model = {"reranking_provider_name": "", "reranking_model_name": ""}
        if reranking_enable:
            reranking_config = await self._fetch_dataset_reranking_config(
                api_base_url, api_key, dataset_id
            )
            reranking_mode = reranking_config["reranking_mode"]
            reranking_model = reranking_config["reranking_model"]

        url = f"{api_base_url}/datasets/{dataset_id}/retrieve"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "query": context.query,
            "retrieval_model": {
                "search_method": search_method,
                "reranking_enable": reranking_enable,
                "reranking_mode": reranking_mode,
                "reranking_model": reranking_model,
                "weights": None,
                "top_k": int(top_k),
                "score_threshold_enabled": score_threshold_enabled,
                "score_threshold": float(score_threshold),
            },
        }

        results: list[RetrievalResultEntry] = []
        try:
            async with self.http_client() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=30.0)
                response.raise_for_status()
                data = response.json()

                logger.info(
                    f"[DifyDatasetsConnector] Request: search_method={search_method}, top_k={top_k}, "
                    f"score_threshold_enabled={score_threshold_enabled}, score_threshold={score_threshold}, "
                    f"reranking_enable={reranking_enable}, reranking_mode={reranking_mode}, "
                    f"reranking_model={reranking_model}, "
                    f"Response records count: {len(data.get('records', []))}"
                )

                for record in data.get("records", []):
                    segment = record.get("segment", {})
                    document = segment.get("document", {})

                    score = record.get("score")
                    if score is None:
                        score = 0.0

                    results.append(
                        RetrievalResultEntry(
                            id=segment.get("id", ""),
                            content=[ContentElement.from_text(segment.get("content", ""))],
                            metadata={
                                "document_id": segment.get("document_id", ""),
                                "document_name": document.get("name", ""),
                                "segment_id": segment.get("id", ""),
                                "keywords": segment.get("keywords", []),
                                "answer": segment.get("answer"),
                            },
                            distance=1.0 - float(score),
                            score=float(score),
                        )
                    )

            logger.info(f"[DifyDatasetsConnector] Retrieved {len(results)} chunks from Dify.")
        except Exception:
            logger.exception("[DifyDatasetsConnector] Error during retrieval")

        return RetrievalResponse(results=results, total_found=len(results))

    @serialized
    async def ingest(self, context: IngestionContext) -> IngestionResult:
        """Upload a file to a Dify dataset for indexing."""
        doc_id = context.file_object.metadata.document_id
        filename = context.file_object.metadata.filename
        config = context.creation_settings

        api_base_url = config.get("api_base_url", "https://api.dify.ai/v1").rstrip("/")
        upstream_target = _normalize_api_base_url(api_base_url)
        api_key = config.get("dify_apikey")
        dataset_id = config.get("dataset_id")

        if not api_key or not dataset_id:
            logger.error(
                f"[DifyDatasetsConnector] Missing required configuration for ingestion. "
                f"Config keys: {list(config.keys())}"
            )
            return IngestionResult(
                document_id=doc_id,
                status=DocumentStatus.FAILED,
                error_message="Missing required config: dify_apikey or dataset_id.",
            )

        # Persist config for deletion after worker restart
        kb_id = context.get_collection_id()
        await self._save_config(kb_id, config)
        if await self._load_document(kb_id, doc_id) is not None:
            raise RuntimeError('Existing upload intent; reconcile before retry')

        # 1. Read file content from Host
        try:
            file_bytes = await self.plugin.get_knowledge_file_stream(context.file_object.storage_path)
        except Exception as e:
            logger.error(f"[DifyDatasetsConnector] Failed to read file content: {e}")
            return IngestionResult(
                document_id=doc_id,
                status=DocumentStatus.FAILED,
                error_message=f"Could not read file: {e}",
            )

        # Intent is durable before remote I/O; an ambiguous timeout cannot create
        # a second document on retry without explicit upstream reconciliation.
        await self._save_document(kb_id, doc_id, {'upstream_id': '', 'dataset_id': dataset_id,
            'status': 'pending'})
        # 2. Upload to Dify dataset
        url = f"{api_base_url}/datasets/{dataset_id}/document/create-by-file"
        headers = {
            "Authorization": f"Bearer {api_key}",
        }

        try:
            data_payload = json.dumps({
                "indexing_technique": "high_quality",
                "process_rule": {"mode": "automatic"},
            })

            async def upload():
                async with self.http_client() as client:
                    response = await client.post(
                        url,
                        headers=headers,
                        files={"file": (filename, file_bytes)},
                        data={"data": data_payload},
                        timeout=120.0,
                    )
                    response.raise_for_status()
                    return response.json()

            resp_data = await self._state.dispatched(
                self.plugin, kb_id, upload, 'Dify upload outcome unknown')

            dify_document = resp_data.get("document", {})
            dify_doc_id = dify_document.get("id")
            if not isinstance(dify_doc_id, str) or not dify_doc_id:
                raise AmbiguousMutationError("Dify upload omitted upstream document ID; outcome requires reconciliation")
            await self._save_document(kb_id, doc_id, {'upstream_id': dify_doc_id,
                'dataset_id': dataset_id, 'status': 'created',
                'api_base_url': upstream_target})

            logger.info(
                f"[DifyDatasetsConnector] File uploaded: {filename} -> "
                f"dify_doc_id={dify_doc_id}, status={dify_document.get('indexing_status')}"
            )

            return IngestionResult(
                document_id=dify_doc_id,
                status=DocumentStatus.PROCESSING,
            )

        except httpx.HTTPStatusError as e:
            # The provider answered, so this rejection is deterministic: no fence.
            error_body = e.response.text
            logger.error(
                f"[DifyDatasetsConnector] Dify API error during ingestion: "
                f"status={e.response.status_code}, body={error_body}"
            )
            return IngestionResult(
                document_id=doc_id,
                status=DocumentStatus.FAILED,
                error_message=f"Dify API error {e.response.status_code}: {error_body}",
            )
        except AmbiguousMutationError:
            # Already-dispatched upload with an unknown outcome: fence this KB.
            raise
        except Exception as e:
            logger.error(f"[DifyDatasetsConnector] Ingestion failed for {filename}: {e}")
            return IngestionResult(
                document_id=doc_id,
                status=DocumentStatus.FAILED,
                error_message=str(e),
            )

    @serialized
    async def delete_document(self, kb_id: str, document_id: str) -> bool:
        """Delete a document from a Dify dataset."""
        mapping = await self._load_document(kb_id, document_id)
        if not mapping or not mapping['upstream_id'] or mapping['status'] != 'created':
            return False
        config = await self._load_config(kb_id)
        if not config:
            logger.warning(
                f"[DifyDatasetsConnector] No stored config for kb_id={kb_id}. "
                "Cannot delete document without API credentials."
            )
            return False

        api_base_url = config.get("api_base_url", "https://api.dify.ai/v1").rstrip("/")
        api_key = config.get("dify_apikey")
        dataset_id = config.get("dataset_id")

        if not api_key or not dataset_id:
            logger.error(
                f"[DifyDatasetsConnector] Missing required configuration for deletion. "
                f"Config keys: {list(config.keys())}"
            )
            return False

        if mapping['dataset_id'] != dataset_id:
            raise RuntimeError('Dataset changed; reconcile before deletion')
        # The mapping is bound to the upstream instance that created it: a changed
        # base URL (or a legacy mapping without one) must not be sent to a
        # different provider. Reject before dispatching any remote request.
        if mapping.get('api_base_url') != _normalize_api_base_url(api_base_url):
            raise RuntimeError('Upstream target changed; reconcile before deletion')
        url = f"{api_base_url}/datasets/{dataset_id}/documents/{mapping['upstream_id']}"
        headers = {
            "Authorization": f"Bearer {api_key}",
        }

        async def remove():
            async with self.http_client() as client:
                response = await client.delete(url, headers=headers, timeout=30.0)
                if response.status_code != 204:
                    # Some Dify versions may return 200 instead of 204.
                    response.raise_for_status()
                return response.status_code

        try:
            status_code = await self._state.dispatched(
                self.plugin, kb_id, remove, 'Dify delete outcome unknown')
            await self._save_document(kb_id, mapping['host_document_id'], {**mapping, 'status': 'deleted'})
            logger.info(
                f"[DifyDatasetsConnector] Document deleted: {document_id} "
                f"from dataset {dataset_id} (status={status_code})"
            )
            return True
        except httpx.HTTPStatusError as e:
            # The provider answered, so the delete was rejected deterministically.
            logger.error(
                f"[DifyDatasetsConnector] Failed to delete document {document_id}: {e}"
            )
            return False
        except Exception as e:
            logger.error(
                f"[DifyDatasetsConnector] Failed to delete document {document_id}: {e}"
            )
            return False

