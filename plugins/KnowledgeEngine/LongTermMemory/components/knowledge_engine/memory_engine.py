from __future__ import annotations

import json
import logging
import math
import time
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any

from langbot_plugin.api.definition.components.knowledge_engine.engine import (
    KnowledgeEngine,
    KnowledgeEngineCapability,
)
from langbot_plugin.api.entities.builtin.rag.context import (
    RetrievalContext,
    RetrievalResponse,
    RetrievalResultEntry,
)
from langbot_plugin.api.entities.builtin.rag.models import (
    IngestionContext,
    IngestionResult,
)
from langbot_plugin.api.entities.builtin.rag.enums import DocumentStatus
from store.serialization import serialized_write

logger = logging.getLogger(__name__)

EMBEDDING_BATCH_SIZE = 32


class LongTermMemoryEngine(KnowledgeEngine):
    """Long-term memory KnowledgeEngine.

    Serves as the configuration entry point for the memory plugin
    (embedding model, isolation mode) and handles L2 episodic memory
    retrieval and import.
    """

    @property
    def _writes(self):
        return self.plugin.memory_store._writes

    @classmethod
    def get_capabilities(cls) -> list[str]:
        return [KnowledgeEngineCapability.DOC_INGESTION]

    async def on_knowledge_base_create(self, kb_id: str, config: dict) -> None:
        existing = await self.plugin.memory_store.get_kb_configs()
        if existing:
            raise ValueError(
                "Only one memory knowledge base is supported per plugin instance. "
                "Please delete the existing one before creating a new one."
            )
        logger.info("Memory KB created: %s, config: %s", kb_id, config)
        await self.plugin.memory_store.save_kb_config(kb_id, config)

    async def on_knowledge_base_delete(self, kb_id: str) -> None:
        logger.info("Memory KB deleted: %s", kb_id)
        await self.plugin.memory_store.remove_kb_config(kb_id)

    # ================================================================
    # time-decay scoring
    # ================================================================

    @staticmethod
    def _time_decay_score(
        similarity: float, timestamp_str: str, half_life_days: float = 30.0,
    ) -> float:
        """Blend similarity with exponential time decay.

        final_score = similarity * exp(-ln2 * age_days / half_life_days)

        A memory exactly ``half_life_days`` old retains 50 % of its
        similarity weight; very recent memories are nearly unaffected.
        """
        if not timestamp_str:
            return similarity * 0.5
        try:
            ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age_days = max(0.0, (now - ts).total_seconds() / 86400.0)
            decay = math.exp(-math.log(2) * age_days / half_life_days)
            return similarity * decay
        except (ValueError, TypeError):
            return similarity * 0.5

    @staticmethod
    def _parse_importance(metadata: dict[str, Any]) -> int:
        raw = metadata.get("importance", "2")
        try:
            return max(1, min(5, int(raw)))
        except (TypeError, ValueError):
            return 2

    @staticmethod
    def _importance_weight(importance: int) -> float:
        # Importance should influence ranking, but not overpower semantic match.
        # The weights keep importance as a secondary signal.
        return {
            1: 0.9,
            2: 1.0,
            3: 1.08,
            4: 1.16,
            5: 1.24,
        }.get(importance, 1.0)

    @staticmethod
    def _speaker_match_weight(
        metadata: dict[str, Any],
        current_sender_id: str,
    ) -> float:
        if not current_sender_id:
            return 1.0
        if str(metadata.get("sender_id", "") or "") == current_sender_id:
            return 1.12
        return 1.0

    @staticmethod
    def _has_update_signal(metadata: dict[str, Any]) -> bool:
        raw_tags = str(metadata.get("tags", "") or "")
        tags = {
            item.strip().lower()
            for item in raw_tags.split(",")
            if item.strip()
        }
        return bool(tags & {
            "correction",
            "clarification",
            "profile-update",
            "preference-change",
            "fact-update",
            "更正",
            "修正",
            "纠正",
            "偏好变化",
        })

    @staticmethod
    def _recency_hint(timestamp_str: str) -> str:
        if not timestamp_str:
            return "unknown"
        try:
            ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age_days = max(0.0, (now - ts).total_seconds() / 86400.0)
        except (ValueError, TypeError):
            return "unknown"

        if age_days < 1:
            return "fresh"
        if age_days < 7:
            return "recent"
        if age_days < 30:
            return "still-relevant"
        if age_days < 90:
            return "older"
        return "old"

    # ================================================================
    # retrieve - called by LocalAgentRunner before LLM invocation
    # ================================================================

    async def retrieve(self, context: RetrievalContext) -> RetrievalResponse:
        query = context.query
        collection_id = context.get_collection_id()
        settings = context.creation_settings
        retrieval_settings = context.retrieval_settings
        store = self.plugin.memory_store

        embedding_model_uuid = settings.get("embedding_model_uuid", "")
        top_k = retrieval_settings.get("top_k", 5)
        logger.info(
            "[LongTermMemory] engine retrieve called: collection_id=%s top_k=%s session_name=%s sender_id=%s bot_uuid=%s query_len=%s",
            collection_id,
            top_k,
            retrieval_settings.get("session_name"),
            retrieval_settings.get("sender_id", ""),
            retrieval_settings.get("bot_uuid", ""),
            len(query),
        )

        if not query.strip() or not embedding_model_uuid:
            logger.info(
                "[LongTermMemory] engine retrieve skipped: collection_id=%s reason=%s",
                collection_id,
                "missing_query" if not query.strip() else "missing_embedding_model_uuid",
            )
            return RetrievalResponse(results=[], total_found=0)

        # embed the query
        query_vectors = await self.plugin.invoke_embedding(
            embedding_model_uuid, [query]
        )
        query_vector = query_vectors[0]

        session_name = retrieval_settings.get("session_name")
        sender_id = str(retrieval_settings.get("sender_id", "") or "")
        bot_uuid = str(retrieval_settings.get("bot_uuid", "") or "")
        isolation = settings.get("isolation", "session")
        # Over-fetch to allow time-decay re-ranking to surface recent
        # memories that would otherwise be pushed out by pure similarity.
        fetch_k = top_k * 3
        retrieval_strategy = store.normalize_retrieval_strategy(
            settings.get("retrieval_strategy", "auto")
        )
        vector_weight = store.normalize_vector_weight(settings.get("vector_weight", 0.7))
        exact_match_boost = bool(settings.get("exact_match_boost", True))
        results: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        async def extend_results(filters: dict[str, Any] | None) -> None:
            nonlocal results
            logger.info(
                "[LongTermMemory] engine vector search: collection_id=%s fetch_k=%s strategy=%s filters=%s",
                collection_id,
                fetch_k,
                retrieval_strategy,
                filters,
            )
            search_kwargs = {
                "collection_id": collection_id,
                "query_vector": query_vector,
                "top_k": fetch_k,
                "filters": filters,
            }
            if retrieval_strategy in {"auto", "hybrid"}:
                try:
                    batch = await self.plugin.vector_search(
                        **search_kwargs,
                        search_type="hybrid",
                        query_text=query,
                        vector_weight=vector_weight,
                    )
                except Exception:
                    if retrieval_strategy == "hybrid":
                        logger.warning(
                            "[LongTermMemory] engine hybrid search failed; falling back to vector search",
                            exc_info=True,
                        )
                    else:
                        logger.info(
                            "[LongTermMemory] engine auto hybrid search unavailable; falling back to vector search",
                            exc_info=True,
                        )
                    batch = await self.plugin.vector_search(**search_kwargs)
            else:
                batch = await self.plugin.vector_search(**search_kwargs)
            for item in batch:
                item_id = item.get("id", "")
                if item_id and item_id in seen_ids:
                    continue
                if not store.episode_status_included(item.get("metadata", {})):
                    continue
                if item_id:
                    seen_ids.add(item_id)
                results.append(item)
                if len(results) >= fetch_k:
                    return

        if session_name:
            scope_key = store.get_scope_key_from_session_name(
                bot_uuid, session_name, isolation
            )

            if sender_id:
                await extend_results({"$and": [{"user_key": scope_key}, {"sender_id": sender_id}]})

            if len(results) < fetch_k:
                await extend_results({"user_key": scope_key})
        else:
            # Refuse to search without scope — returning unfiltered results
            # would leak memories across sessions / users.
            logger.warning(
                "[LongTermMemory] engine retrieve refused: collection_id=%s reason=missing_session_name",
                collection_id,
            )
            return RetrievalResponse(results=[], total_found=0)

        # Time-decay re-ranking: blend similarity with recency so that
        # recent memories can outrank older ones with marginally higher
        # vector similarity.
        half_life = float(settings.get("recency_half_life_days", 30))
        for r in results:
            sim = r.get("score") or (1.0 - r.get("distance", 1.0))
            metadata = r.get("metadata", {})
            ts = metadata.get("timestamp", "")
            importance = self._parse_importance(metadata)
            time_score = self._time_decay_score(float(sim), ts, half_life)
            importance_weight = self._importance_weight(importance)
            speaker_weight = self._speaker_match_weight(metadata, sender_id)
            update_weight = 1.08 if self._has_update_signal(metadata) else 1.0
            exact_boost = 1.0
            if exact_match_boost:
                exact_score = store._metadata_exact_match_score(
                    query,
                    r.get("id", ""),
                    metadata,
                )
                exact_boost += min(exact_score, 2.0) * 0.25
            final_score = (
                time_score
                * importance_weight
                * speaker_weight
                * update_weight
                * exact_boost
            )
            r["_final_score"] = max(0.0, min(1.0, final_score))
            r["_recency_hint"] = self._recency_hint(ts)
            r["_importance"] = importance
            r["_speaker_match"] = speaker_weight > 1.0
            r["_has_update_signal"] = update_weight > 1.0
            r["_exact_match"] = exact_boost > 1.0

        results.sort(key=lambda r: r["_final_score"], reverse=True)
        results = results[:top_k]
        logger.info(
            "[LongTermMemory] engine retrieve completed: collection_id=%s result_count=%s half_life_days=%s",
            collection_id,
            len(results),
            half_life,
        )

        entries: list[RetrievalResultEntry] = []
        for r in results:
            meta = r.get("metadata", {})
            content = meta.get("content", "")
            timestamp = meta.get("timestamp", "")
            importance = str(r.get("_importance", self._parse_importance(meta)))
            tags = meta.get("tags", "")
            hints = [f"importance:{importance}"]
            recency_hint = r.get("_recency_hint", "unknown")
            if recency_hint != "unknown":
                hints.append(f"recency:{recency_hint}")
            if r.get("_speaker_match"):
                hints.append("speaker:current")
            if r.get("_has_update_signal"):
                hints.append("signal:update")
            if r.get("_exact_match"):
                hints.append("match:exact")

            display = f"[{timestamp}] ({', '.join(hints)})"
            if tags:
                display += f" [{tags}]"
            # Wrap content in data markers to reduce prompt-injection risk.
            display += f" <mem>{content}</mem>"

            entries.append(
                RetrievalResultEntry(
                    id=r.get("id", ""),
                    content=[{"type": "text", "text": display}],
                    metadata=meta,
                    score=r.get("_final_score", r.get("score")),
                    distance=1.0 - r.get("_final_score", r.get("score", 0.0)),
                )
            )

        return RetrievalResponse(results=entries, total_found=len(entries))

    # ================================================================
    # ingest - import memories from JSON file
    # ================================================================

    async def ingest(self, context: IngestionContext) -> IngestionResult:
        audit_entries: list[dict[str, Any]] = []
        result = await self._ingest(context.get_collection_id(), context, audit_entries)
        # User-scope audit writes run after releasing the collection lock.
        for entry in audit_entries:
            await self.plugin.memory_store.append_audit_entry(**entry)
        return result

    @serialized_write
    async def _ingest(
        self,
        collection_id: str,
        context: IngestionContext,
        audit_entries: list[dict[str, Any]],
    ) -> IngestionResult:
        doc_id = context.file_object.metadata.document_id
        filename = context.file_object.metadata.filename
        settings = context.creation_settings
        embedding_model_uuid = settings.get("embedding_model_uuid", "")

        logger.info("Ingesting memory file: %s (doc=%s)", filename, doc_id)

        if not embedding_model_uuid:
            return IngestionResult(
                document_id=doc_id,
                status=DocumentStatus.FAILED,
                error_message="No embedding model configured.",
            )

        # read file content
        try:
            content_bytes = await self.plugin.get_knowledge_file_stream(
                context.file_object.storage_path
            )
        except Exception as e:
            logger.error("Failed to read file: %s", e)
            return IngestionResult(
                document_id=doc_id,
                status=DocumentStatus.FAILED,
                error_message=f"Could not read file: {e}",
            )

        # parse JSON array of memory entries
        try:
            text = content_bytes.decode("utf-8")

            # support pre-parsed content from a Parser plugin
            if context.parsed_content and context.parsed_content.text:
                text = context.parsed_content.text

            memories = json.loads(text)
            if not isinstance(memories, list):
                memories = [memories]
        except Exception as e:
            logger.error("Failed to parse memory file: %s", e)
            return IngestionResult(
                document_id=doc_id,
                status=DocumentStatus.FAILED,
                error_message=f"Invalid JSON format: {e}",
            )

        if not memories:
            return IngestionResult(
                document_id=doc_id,
                status=DocumentStatus.COMPLETED,
                chunks_created=0,
            )

        # batch embed and upsert
        total_stored = 0
        batch_texts: list[str] = []
        batch_ids: list[str] = []
        batch_metas: list[dict[str, Any]] = []
        imported_by_user: dict[str, int] = {}

        for mem in memories:
            content = mem.get("content", "")
            if not content:
                continue

            tags = mem.get("tags", [])
            importance = mem.get("importance", 2)
            try:
                raw_timestamp = mem.get("timestamp", "")
                if raw_timestamp:
                    timestamp = self.plugin.memory_store.normalize_timestamp(
                        str(raw_timestamp)
                    )
                else:
                    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            except ValueError as exc:
                return IngestionResult(
                    document_id=doc_id,
                    status=DocumentStatus.FAILED,
                    error_message=str(exc),
                )
            user_key = mem.get("user_key", "imported")
            status = self.plugin.memory_store.normalize_episode_status_value(
                mem.get("status", "active")
            )
            user_key_text = str(user_key or "imported")
            imported_by_user[user_key_text] = imported_by_user.get(user_key_text, 0) + 1

            mid = uuid_mod.uuid4().hex[:12]
            batch_texts.append(content)
            batch_ids.append(mid)
            batch_metas.append({
                "content": content,
                "tags": ",".join(tags) if isinstance(tags, list) else str(tags),
                "importance": str(importance),
                "timestamp": timestamp,
                "user_key": user_key,
                "source": "import",
                "document_id": doc_id,
                "status": status,
            })

            if len(batch_texts) >= EMBEDDING_BATCH_SIZE:
                total_stored += await self._embed_and_upsert(
                    collection_id, embedding_model_uuid,
                    batch_texts, batch_ids, batch_metas,
                )
                batch_texts, batch_ids, batch_metas = [], [], []

        # flush remaining
        if batch_texts:
            total_stored += await self._embed_and_upsert(
                collection_id, embedding_model_uuid,
                batch_texts, batch_ids, batch_metas,
            )

        logger.info("Ingestion complete: %d memories stored", total_stored)
        for user_key, count in imported_by_user.items():
            audit_entries.append(dict(
                scope_key=user_key,
                user_key=user_key,
                operation="import_l2",
                target_type="document",
                target_id=doc_id,
                summary=f"Imported {count} L2 episode(s) from {filename}",
                metadata={
                    "kb_id": collection_id,
                    "filename": filename,
                    "count": count,
                },
            ))
        return IngestionResult(
            document_id=doc_id,
            status=DocumentStatus.COMPLETED,
            chunks_created=total_stored,
        )

    @serialized_write
    async def _embed_and_upsert(
        self,
        collection_id: str,
        embedding_model_uuid: str,
        texts: list[str],
        ids: list[str],
        metas: list[dict[str, Any]],
    ) -> int:
        logger.info(
            "[LongTermMemory] engine embed_and_upsert: collection_id=%s batch_size=%s ids=%s",
            collection_id,
            len(texts),
            ids,
        )
        vectors = await self.plugin.invoke_embedding(embedding_model_uuid, texts)
        await self._writes.mutate(
            self.plugin,
            collection_id,
            lambda: self.plugin.vector_upsert(
                collection_id=collection_id,
                vectors=vectors,
                ids=ids,
                metadata=metas,
                documents=texts,
            ),
            "Host vector_upsert outcome unknown",
        )
        return len(texts)

    # ================================================================
    # delete_document - remove imported memories by document_id
    # ================================================================

    async def delete_document(self, kb_id: str, document_id: str) -> bool:
        logger.info(
            "[LongTermMemory] delete_document called: kb_id=%s document_id=%s",
            kb_id,
            document_id,
        )
        count = await self._delete_document_vectors(kb_id, document_id)
        logger.info(
            "[LongTermMemory] delete_document completed: kb_id=%s document_id=%s deleted_count=%s",
            kb_id,
            document_id,
            count,
        )
        await self.plugin.memory_store.append_audit_entry(
            scope_key=f"document:{document_id}",
            operation="delete_document",
            target_type="document",
            target_id=document_id,
            summary=f"Deleted imported memory document {document_id}",
            metadata={"kb_id": kb_id, "deleted": count},
        )
        return count > 0

    @serialized_write
    async def _delete_document_vectors(self, kb_id: str, document_id: str) -> int:
        return await self._writes.mutate(
            self.plugin,
            kb_id,
            lambda: self.plugin.vector_delete(
                collection_id=kb_id,
                filters={"document_id": document_id},
            ),
            "Host vector_delete outcome unknown",
        )
