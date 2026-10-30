import logging
from collections.abc import Awaitable, Iterable
from components.shared_state import SerialState, serialized

from langbot_plugin.api.definition.components.knowledge_engine import (
    KnowledgeEngine,
    KnowledgeEngineCapability,
)
from langbot_plugin.api.entities.builtin.rag import (
    IngestionContext,
    IngestionResult,
    RetrievalContext,
    RetrievalResponse,
    RetrievalResultEntry,
    DocumentStatus,
    SearchType,
)

from .parser import FileParser
from .query_rewrite import retrieve_with_rewrite
from .rerank import llm_rerank, model_rerank
from .strategies import get_strategy
from components.observability.telemetry import add_stage_duration, hash_text, telemetry

logger = logging.getLogger(__name__)

# Batch size for embedding API calls.
# Larger batches = fewer round-trips.  Keep under ~64 to avoid IPC response
# timeouts.
EMBEDDING_BATCH_SIZE = 32
PARSED_TEXT_LIMIT_BYTES = 4 * 1024 * 1024


def _validate_parsed_text_budget(parts: Iterable[str]) -> None:
    """Bound aggregate UTF-8 content before strategy work, without joining it."""
    total_bytes = 0
    for text in parts:
        # Encode bounded slices so even a rejected input cannot require a
        # second, arbitrarily large allocation just to measure its byte size.
        for offset in range(0, len(text), 64 * 1024):
            total_bytes += len(text[offset:offset + 64 * 1024].encode("utf-8"))
            if total_bytes > PARSED_TEXT_LIMIT_BYTES:
                raise ValueError("Parsed text exceeds the 4 MiB UTF-8 byte limit")


def _query_log_ref(query: str | None) -> str:
    """Return a privacy-preserving query reference for logs."""
    return f"hash={hash_text(query)}, length={len(query or '')}"


def _trace_spans(trace_id: str, stage_durations: dict[str, float]) -> list[dict]:
    """Build LangRAG-local spans from recorded stage timings."""
    return [
        {
            "trace_id": trace_id,
            "span_id": f"{trace_id}:{stage}",
            "name": stage,
            "kind": "langrag.stage",
            "status": "completed",
            "duration_ms": duration,
        }
        for stage, duration in stage_durations.items()
    ]


class LangRAG(KnowledgeEngine):
    """Simple Knowledge Engine implementation using Plugin IPC.

    Provides:
    - Document ingestion with parsing, chunking, embedding, and vector storage
    - Vector-based retrieval
    - Full integration with Host's embedding models and vector database
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._state = SerialState()

    async def initialize(self) -> None:
        await super().initialize()
        # The runtime dispatches installation revocation to the plugin instance,
        # which holds no back-reference to its components; hand it this
        # component's state so the revocation hook can drop per-binding locks and
        # fences. Without the hook (langbot-plugin 0.7.4) this attribute is simply
        # never read.
        plugin = getattr(self, 'plugin', None)
        if plugin is not None:
            plugin.knowledge_engine_serial_state = self._state

    @classmethod
    def get_capabilities(cls) -> list[str]:
        """Declare supported capabilities."""
        return [
            KnowledgeEngineCapability.DOC_INGESTION,
            KnowledgeEngineCapability.DOC_PARSING,
        ]

    # ========== Lifecycle Hooks ==========

    async def on_knowledge_base_create(self, kb_id: str, config: dict) -> None:
        logger.info(f"Knowledge base created: {kb_id}")

    async def on_knowledge_base_delete(self, kb_id: str) -> None:
        logger.info(f"Knowledge base deleted: {kb_id}")
        # Deleting a knowledge base resolves its pending ambiguity, so this is the
        # operator path out of a fence; a fresh knowledge base starts unfenced.
        await self._state.clear_fence(self.plugin, kb_id)

    # ========== Helpers ==========

    async def _embed_and_upsert(
        self,
        collection_id: str,
        embedding_model_uuid: str,
        texts: list[str],
        ids: list[str],
        metas: list[dict],
        trace_id: str | None = None,
        parent_stage_durations: dict[str, float] | None = None,
    ) -> int:
        """Embed a batch of texts and upsert into the vector store.

        Returns the number of vectors stored.
        """
        telemetry = self.plugin.telemetry
        started_at = telemetry.start_timer()
        status = "failed"
        error = None
        vectors_stored = 0
        stage_durations: dict[str, float] = {}
        try:
            stage_started = telemetry.start_timer()
            vectors = await self.plugin.invoke_embedding(embedding_model_uuid, texts)
            add_stage_duration(
                stage_durations,
                "embedding",
                telemetry.elapsed_ms(stage_started),
            )
            if parent_stage_durations is not None:
                add_stage_duration(
                    parent_stage_durations,
                    "embedding",
                    stage_durations["embedding"],
                )
            stage_started = telemetry.start_timer()
            await self._state.mutate(
                self.plugin,
                collection_id,
                lambda: self.plugin.vector_upsert(
                    collection_id=collection_id,
                    vectors=vectors,
                    ids=ids,
                    metadata=metas,
                    documents=texts,
                ),
                'Host vector_upsert outcome unknown',
            )
            add_stage_duration(
                stage_durations,
                "vector_upsert",
                telemetry.elapsed_ms(stage_started),
            )
            if parent_stage_durations is not None:
                add_stage_duration(
                    parent_stage_durations,
                    "vector_upsert",
                    stage_durations["vector_upsert"],
                )
            vectors_stored = len(texts)
            status = "completed"
            return vectors_stored
        except Exception as e:
            error = e
            raise
        finally:
            await self._record_diagnostic(
                "record_embedding_batch",
                telemetry.record_embedding_batch(
                    collection_id=collection_id,
                    ids=ids,
                    metas=metas,
                    texts=texts,
                    status=status,
                    duration_ms=telemetry.elapsed_ms(started_at),
                    vectors_stored=vectors_stored,
                    stage_durations_ms=stage_durations,
                    trace_id=trace_id,
                    error=error,
                ),
            )

    @staticmethod
    async def _record_diagnostic(label: str, awaitable: Awaitable[None]) -> None:
        """Record one diagnostic best effort.

        Telemetry is observability, never a precondition: a fenced or unreachable
        telemetry state must not fail the operation it describes, and it must not
        replace the error the caller is about to see.
        """
        try:
            await awaitable
        except Exception:
            logger.warning("LangRAG telemetry %s failed", label, exc_info=True)

    @staticmethod
    def _metadata_int(value) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    @staticmethod
    def _neighbor_id(meta: dict, offset: int) -> str | None:
        """Build the vector ID for an adjacent retrieval unit.

        The three index strategies use different vector ID schemes.  Context
        expansion only needs one representative vector per adjacent unit
        because the stored metadata ``text`` field carries the display context.
        """
        doc_id = meta.get("document_id", "")
        index_type = meta.get("index_type", "chunk")

        if index_type == "parent_child":
            parent_idx = LangRAG._metadata_int(meta.get("parent_index"))
            if doc_id and parent_idx is not None and parent_idx + offset >= 0:
                return f"{doc_id}_p{parent_idx + offset}_c0"
            return None

        if index_type == "qa":
            chunk_idx = LangRAG._metadata_int(meta.get("chunk_index"))
            if doc_id and chunk_idx is not None and chunk_idx + offset >= 0:
                return f"{doc_id}_{chunk_idx + offset}_qa0"
            return None

        chunk_idx = LangRAG._metadata_int(meta.get("chunk_index"))
        if doc_id and chunk_idx is not None and chunk_idx + offset >= 0:
            return f"{doc_id}_{chunk_idx + offset}"
        return None

    async def _expand_context(
        self,
        results: list[dict],
        collection_id: str,
        window: int,
    ) -> None:
        """Expand each result with adjacent chunks from the same document.

        For each hit, looks up adjacent retrieval units from the same document
        and appends their text to the result's metadata as
        ``context_before`` and ``context_after``.

        Requires the vector store to support ``vector_get_by_ids``.  If the
        method is unavailable or fails, this is a no-op.
        """
        get_by_ids = getattr(self.plugin, "vector_get_by_ids", None)
        if not callable(get_by_ids):
            return

        ids_to_fetch: set[str] = set()
        # Map result → adjacent IDs needed
        for res in results:
            meta = res.get("metadata", {})
            for offset in range(1, window + 1):
                before_id = self._neighbor_id(meta, -offset)
                after_id = self._neighbor_id(meta, offset)
                if before_id:
                    ids_to_fetch.add(before_id)
                if after_id:
                    ids_to_fetch.add(after_id)

        if not ids_to_fetch:
            return

        adjacent = await get_by_ids(
            collection_id=collection_id, ids=list(ids_to_fetch)
        )
        # Build lookup: id → text
        adj_map: dict[str, str] = {}
        for item in adjacent:
            item_id = item.get("id", "")
            item_text = item.get("metadata", {}).get("text", "")
            if item_id and item_text:
                adj_map[item_id] = item_text

        # Attach context to results
        for res in results:
            meta = res.get("metadata", {})
            before_parts = []
            after_parts = []
            for offset in range(1, window + 1):
                before_id = self._neighbor_id(meta, -offset)
                after_id = self._neighbor_id(meta, offset)
                if before_id in adj_map:
                    before_parts.insert(0, adj_map[before_id])
                if after_id in adj_map:
                    after_parts.append(adj_map[after_id])
            if before_parts:
                meta["context_before"] = "\n".join(before_parts)
            if after_parts:
                meta["context_after"] = "\n".join(after_parts)

    @staticmethod
    async def _timed_batches(generator, stage_durations: dict[str, float]):
        """Yield strategy batches while accumulating generator runtime."""
        iterator = generator.__aiter__()
        while True:
            stage_started = telemetry.start_timer()
            try:
                batch = await iterator.__anext__()
            except StopAsyncIteration:
                break
            else:
                add_stage_duration(
                    stage_durations,
                    "chunking",
                    telemetry.elapsed_ms(stage_started),
                )
                yield batch

    # ========== Core Methods ==========

    @serialized
    async def ingest(self, context: IngestionContext) -> IngestionResult:
        """Handle document ingestion: Read -> Parse -> Chunk -> Embed -> Store.

        Uses an async generator pipeline: the strategy yields batches
        incrementally, and each batch is embedded and upserted as soon as it
        is ready.  This ensures partial results are persisted early.
        """
        telemetry = self.plugin.telemetry
        started_at = telemetry.start_timer()
        trace_id = telemetry.new_trace_id("ingest")
        stage_durations: dict[str, float] = {}
        doc_id = context.file_object.metadata.document_id
        filename = context.file_object.metadata.filename
        file_size = getattr(context.file_object.metadata, "file_size", None)
        metadata_extra = getattr(context.file_object.metadata, "extra", {}) or {}
        collection_id = context.get_collection_id()
        index_type = context.creation_settings.get("index_type") or "chunk"
        telemetry_status = DocumentStatus.FAILED
        telemetry_error = None
        telemetry_chunks_created = 0
        telemetry_text_length = None
        telemetry_content_hash = None
        telemetry_sections_count = None
        parser_source = None
        correlation = telemetry.correlation_summary(
            context.creation_settings,
            metadata_extra,
            trace_id=trace_id,
        )

        logger.info(
            f"Ingesting file: {filename} (doc={doc_id}) into collection: {collection_id}"
        )

        try:
            # 1. Parse file content (prefer pre-parsed content from external Parser plugin)
            sections = None
            doc_metadata = None
            if context.parsed_content and context.parsed_content.text:
                stage_started = telemetry.start_timer()
                text_content = context.parsed_content.text
                parser_source = "external"
                logger.info(
                    f"Using pre-parsed content from external parser for {filename}"
                )
                # Extract structured sections and metadata if available
                if context.parsed_content.sections:
                    sections = context.parsed_content.sections
                    telemetry_sections_count = len(sections)
                    logger.info(
                        f"Found {len(sections)} structured sections from parser"
                    )
                if context.parsed_content.metadata:
                    doc_metadata = context.parsed_content.metadata
                    correlation.update(
                        telemetry.correlation_summary(doc_metadata, trace_id=trace_id)
                    )
                    logger.info(
                        f"Found document metadata from parser: "
                        f"{[k for k in doc_metadata if k != 'images']}"
                    )
                add_stage_duration(
                    stage_durations,
                    "parser_external",
                    telemetry.elapsed_ms(stage_started),
                )
            else:
                parser_source = "internal"
                logger.warning(
                    f"No external parser content for {filename}; "
                    "falling back to internal FileParser. Consider configuring an "
                    "external parser (e.g. GeneralParsers) for better results."
                )
                try:
                    stage_started = telemetry.start_timer()
                    content_bytes = await self.plugin.get_knowledge_file_stream(
                        context.file_object.storage_path
                    )
                    add_stage_duration(
                        stage_durations,
                        "file_read",
                        telemetry.elapsed_ms(stage_started),
                    )
                except Exception as e:
                    telemetry_error = e
                    telemetry_status = DocumentStatus.FAILED
                    logger.error(f"Failed to get file content: {e}")
                    return IngestionResult(
                        document_id=doc_id,
                        status=DocumentStatus.FAILED,
                        error_message=f"Could not read file: {e}",
                    )
                parser = FileParser(self.plugin.offload)
                stage_started = telemetry.start_timer()
                text_content = await parser.parse(content_bytes, filename)
                add_stage_duration(
                    stage_durations,
                    "parser_internal",
                    telemetry.elapsed_ms(stage_started),
                )

            # Bound both representations independently: strategies consume the
            # sections when present, not necessarily the parser's flat text.
            _validate_parsed_text_budget((text_content or "",))
            if sections:
                _validate_parsed_text_budget(section.content for section in sections)
            telemetry_text_length = len(text_content) if text_content else 0
            telemetry_content_hash = hash_text(text_content)

            if not text_content:
                telemetry_status = DocumentStatus.COMPLETED
                logger.warning(f"No text content extracted from file: {filename}")
                return IngestionResult(
                    document_id=doc_id,
                    status=DocumentStatus.COMPLETED,
                    chunks_created=0,
                )

            # 3. Build chunks via strategy (async generator)
            strategy = get_strategy(index_type)
            embedding_model_uuid = context.creation_settings.get(
                "embedding_model_uuid", ""
            )
            logger.info(f"Strategy: {index_type} ({strategy.__class__.__name__})")

            # 4. Progressive ingest: consume generator → accumulate → embed+upsert
            #    when a full batch is ready.  Embedding happens between generator
            #    yields (sequential, not concurrent) to avoid IPC timeout issues.
            pending_texts: list[str] = []
            pending_ids: list[str] = []
            pending_metas: list[dict] = []
            total_stored = 0

            async for (
                batch_texts,
                batch_ids,
                batch_metas,
            ) in self._timed_batches(
                strategy.build_chunks_and_metadata(
                    text_content,
                    doc_id,
                    filename,
                    context.creation_settings,
                    plugin=self.plugin,
                    sections=sections,
                    doc_metadata=doc_metadata,
                ),
                stage_durations,
            ):
                pending_texts.extend(batch_texts)
                pending_ids.extend(batch_ids)
                pending_metas.extend(batch_metas)

                # Flush full batches immediately
                while len(pending_texts) >= EMBEDDING_BATCH_SIZE:
                    t = pending_texts[:EMBEDDING_BATCH_SIZE]
                    i = pending_ids[:EMBEDDING_BATCH_SIZE]
                    m = pending_metas[:EMBEDDING_BATCH_SIZE]
                    pending_texts = pending_texts[EMBEDDING_BATCH_SIZE:]
                    pending_ids = pending_ids[EMBEDDING_BATCH_SIZE:]
                    pending_metas = pending_metas[EMBEDDING_BATCH_SIZE:]
                    total_stored += await self._embed_and_upsert(
                        collection_id,
                        embedding_model_uuid,
                        t,
                        i,
                        m,
                        trace_id=trace_id,
                        parent_stage_durations=stage_durations,
                    )
                    telemetry_chunks_created = total_stored

            # Flush remaining
            if pending_texts:
                total_stored += await self._embed_and_upsert(
                    collection_id,
                    embedding_model_uuid,
                    pending_texts,
                    pending_ids,
                    pending_metas,
                    trace_id=trace_id,
                    parent_stage_durations=stage_durations,
                )
                telemetry_chunks_created = total_stored

            if total_stored:
                unit = "Q&A pairs" if index_type == "qa" else "chunks"
                logger.info(f"Ingestion complete: {total_stored} {unit} stored")

            telemetry_status = DocumentStatus.COMPLETED
            telemetry_chunks_created = total_stored
            return IngestionResult(
                document_id=doc_id,
                status=DocumentStatus.COMPLETED,
                chunks_created=total_stored,
            )

        except Exception as e:
            telemetry_error = e
            telemetry_status = DocumentStatus.FAILED
            logger.error(f"Ingestion failed for {filename}: {e}")
            return IngestionResult(
                document_id=doc_id,
                status=DocumentStatus.FAILED,
                error_message=str(e),
            )
        finally:
            await self._record_diagnostic(
                "record_ingest",
                telemetry.record_ingest(
                    document_id=doc_id,
                    filename=filename,
                    collection_id=collection_id,
                    status=telemetry_status,
                    duration_ms=telemetry.elapsed_ms(started_at),
                    index_type=index_type,
                    chunks_created=telemetry_chunks_created,
                    file_size=file_size,
                    text_length=telemetry_text_length,
                    content_hash=telemetry_content_hash,
                    sections_count=telemetry_sections_count,
                    settings=context.creation_settings,
                    stage_durations_ms=stage_durations,
                    parser_source=parser_source,
                    knowledge_base_id=context.knowledge_base_id,
                    trace_id=trace_id,
                    correlation=correlation,
                    error=telemetry_error,
                ),
            )

    async def retrieve(self, context: RetrievalContext) -> RetrievalResponse:
        """Retrieve relevant content with support for vector, full-text, and hybrid search."""
        telemetry = self.plugin.telemetry
        started_at = telemetry.start_timer()
        trace_id = telemetry.new_trace_id("retrieval")
        stage_durations: dict[str, float] = {}
        query = context.query
        top_k = context.retrieval_settings.get("top_k", 5)
        collection_id = context.get_collection_id()
        search_type = context.retrieval_settings.get("search_type", SearchType.VECTOR)
        raw_count = None
        result_count = None
        fetch_k = None
        reranked = False
        telemetry_status = "failed"
        telemetry_error = None
        reference_count = None
        heading_count = None
        context_expanded_count = None
        distance_min = None
        distance_avg = None
        distance_max = None
        correlation = telemetry.correlation_summary(
            context.filters,
            context.creation_settings,
            context.retrieval_settings,
            trace_id=trace_id,
        )

        try:
            # Read hybrid fusion weight (YAML default 0.7; vdb fallback handles None)
            vector_weight = float(context.retrieval_settings.get("vector_weight", 0.7))

            # Determine strategy for post-processing
            index_type = context.creation_settings.get("index_type") or "chunk"
            strategy = get_strategy(index_type)
            logger.info(
                f"Retrieve: strategy={index_type}, top_k={top_k}, "
                f"query_rewrite={context.retrieval_settings.get('query_rewrite', 'off')}, "
                f"query_ref=({_query_log_ref(query)})"
            )
            logger.info(
                f"Retrieve search config: search_type={search_type}, "
                f"vector_weight={vector_weight}"
            )

            rerank_mode = context.retrieval_settings.get("rerank", "off")
            rerank_llm = context.retrieval_settings.get("rerank_llm_model_uuid", "")
            rerank_model = context.retrieval_settings.get("rerank_model_uuid", "")
            rerank_enabled = (
                rerank_mode == "llm"
                and bool(rerank_llm)
            ) or (
                rerank_mode in ("rerank_model", "model")
                and bool(rerank_model)
            )

            # For parent_child/qa, over-fetch to allow dedup to still yield top_k.
            # When reranking is enabled, keep a larger candidate pool for rerankers.
            if index_type in ("parent_child", "qa") or rerank_enabled:
                fetch_k = top_k * 3
            else:
                fetch_k = top_k

            # Check query rewrite settings
            query_rewrite = context.retrieval_settings.get("query_rewrite", "off")
            rewrite_llm = context.retrieval_settings.get("rewrite_llm_model_uuid", "")

            if query_rewrite != "off" and rewrite_llm:
                logger.info(f"Query rewrite enabled: strategy={query_rewrite}")
                stage_started = telemetry.start_timer()
                results = await retrieve_with_rewrite(
                    plugin=self.plugin,
                    query=query,
                    query_rewrite=query_rewrite,
                    rewrite_llm=rewrite_llm,
                    collection_id=collection_id,
                    embedding_model_uuid=context.creation_settings.get(
                        "embedding_model_uuid", ""
                    ),
                    fetch_k=fetch_k,
                    filters=context.filters or None,
                    search_type=search_type,
                    vector_weight=vector_weight,
                    stage_durations=stage_durations,
                )
                add_stage_duration(
                    stage_durations,
                    f"rewrite_{query_rewrite}",
                    telemetry.elapsed_ms(stage_started),
                )
            else:
                # Original logic: embed query → vector_search
                query_vector: list[float] = []
                if search_type != SearchType.FULL_TEXT:
                    embedding_model_uuid = context.creation_settings.get(
                        "embedding_model_uuid", ""
                    )
                    stage_started = telemetry.start_timer()
                    query_vectors = await self.plugin.invoke_embedding(
                        embedding_model_uuid, [query]
                    )
                    query_vector = query_vectors[0]
                    add_stage_duration(
                        stage_durations,
                        "query_embedding",
                        telemetry.elapsed_ms(stage_started),
                    )

                stage_started = telemetry.start_timer()
                results = await self.plugin.vector_search(
                    collection_id=collection_id,
                    query_vector=query_vector,
                    top_k=fetch_k,
                    filters=context.filters or None,
                    search_type=search_type,
                    query_text=query,
                    vector_weight=vector_weight,
                )
                add_stage_duration(
                    stage_durations,
                    "vector_search",
                    telemetry.elapsed_ms(stage_started),
                )

            # Post-process (strategy may deduplicate). If reranking is enabled,
            # preserve the over-fetched pool and let the reranker apply top_k.
            raw_count = len(results)
            postprocess_k = fetch_k if rerank_enabled else top_k
            stage_started = telemetry.start_timer()
            results = strategy.postprocess_results(results, postprocess_k)
            add_stage_duration(
                stage_durations,
                "postprocess",
                telemetry.elapsed_ms(stage_started),
            )
            logger.info(
                f"Retrieve post-process: {raw_count} raw → {len(results)} after dedup "
                f"(fetch_k={fetch_k}, postprocess_k={postprocess_k})"
            )

            if rerank_mode in ("rerank_model", "model") and rerank_model:
                logger.info("[Rerank] Host rerank model enabled")
                stage_started = telemetry.start_timer()
                results = await model_rerank(
                    plugin=self.plugin,
                    rerank_model_uuid=rerank_model,
                    query=query,
                    results=results,
                    top_k=top_k,
                )
                add_stage_duration(
                    stage_durations,
                    "rerank_model",
                    telemetry.elapsed_ms(stage_started),
                )
                reranked = True
            elif rerank_mode == "llm" and rerank_llm:
                logger.info("[Rerank] LLM reranking enabled")
                stage_started = telemetry.start_timer()
                results = await llm_rerank(
                    plugin=self.plugin,
                    llm_uuid=rerank_llm,
                    query=query,
                    results=results,
                    top_k=top_k,
                )
                add_stage_duration(
                    stage_durations,
                    "rerank_llm",
                    telemetry.elapsed_ms(stage_started),
                )
                reranked = True

            # C1: Heading hit weighting — boost results whose heading_path
            # contains query keywords.  Skipped when LLM reranking is active
            # because the LLM already understands heading relevance.
            if not reranked:
                stage_started = telemetry.start_timer()
                query_keywords = [w for w in query.lower().split() if len(w) >= 2]
                if query_keywords:
                    for res in results:
                        heading_path = (
                            res.get("metadata", {}).get("heading_path", "") or ""
                        ).lower()
                        if not heading_path:
                            continue
                        distance = res.get("distance")
                        if distance is not None and isinstance(distance, (int, float)):
                            for kw in query_keywords:
                                if kw in heading_path:
                                    distance *= 0.9
                            res["distance"] = distance
                    # Re-sort by distance (lower is better) after weighting
                    results.sort(
                        key=lambda r: (
                            r.get("distance")
                            if isinstance(r.get("distance"), (int, float))
                            else float("inf")
                        )
                    )
                add_stage_duration(
                    stage_durations,
                    "heading_weight",
                    telemetry.elapsed_ms(stage_started),
                )

            # C2: Context window — attempt to fetch adjacent chunks from the same
            # document to provide surrounding context.  Only works when the vector
            # store supports ``vector_get_by_ids`` (gracefully skipped otherwise).
            context_window = context.retrieval_settings.get("context_window", 0)
            if context_window and context_window > 0:
                try:
                    stage_started = telemetry.start_timer()
                    await self._expand_context(results, collection_id, context_window)
                    add_stage_duration(
                        stage_durations,
                        "context_expansion",
                        telemetry.elapsed_ms(stage_started),
                    )
                except Exception as e:
                    logger.debug(
                        f"Context window expansion skipped (vector_get_by_ids "
                        f"not supported or failed): {e}"
                    )

            # Format results
            stage_started = telemetry.start_timer()
            distances = [
                float(res["distance"])
                for res in results
                if isinstance(res.get("distance"), (int, float))
            ]
            if distances:
                distance_min = round(min(distances), 6)
                distance_avg = round(sum(distances) / len(distances), 6)
                distance_max = round(max(distances), 6)
            entries: list[RetrievalResultEntry] = []
            for res in results:
                meta = res.get("metadata", {})
                content_text = meta.get("text", "")
                raw_score = res.get("score")
                distance = res.get("distance")
                if distance is None and raw_score is not None:
                    # Compatibility with older hosts that incorrectly returned
                    # distance under the score field.
                    distance = raw_score

                doc_name = meta.get("document_name", "")
                page = meta.get("page")
                heading_path = meta.get("heading_path", "")

                # Build structured reference string
                ref_parts = [doc_name]
                if page is not None:
                    ref_parts.append(f"p.{page}")
                if heading_path:
                    ref_parts.append(f'"{heading_path}"')
                reference = "[" + ", ".join(ref_parts) + "]" if ref_parts else ""

                content_entry: dict = {
                    "type": "text",
                    "text": content_text,
                    "file_name": doc_name,
                }
                if page is not None:
                    content_entry["page"] = page
                if heading_path:
                    content_entry["heading_path"] = heading_path
                if reference:
                    content_entry["reference"] = reference

                entries.append(
                    RetrievalResultEntry(
                        id=res["id"],
                        content=[content_entry],
                        metadata=meta,
                        score=raw_score,
                        distance=distance,
                    )
                )

            result_count = len(entries)
            reference_count = sum(
                1
                for entry in entries
                for item in entry.content
                if isinstance(item, dict) and item.get("reference")
            )
            heading_count = sum(
                1
                for entry in entries
                for item in entry.content
                if isinstance(item, dict) and item.get("heading_path")
            )
            context_expanded_count = sum(
                1
                for entry in entries
                if entry.metadata.get("context_before")
                or entry.metadata.get("context_after")
            )
            add_stage_duration(
                stage_durations,
                "format_response",
                telemetry.elapsed_ms(stage_started),
            )
            telemetry_status = "completed"
            trace_spans = _trace_spans(trace_id, stage_durations)
            return RetrievalResponse(
                results=entries,
                total_found=len(entries),
                metadata={
                    "trace_id": trace_id,
                    "raw_count": raw_count,
                    "stage_durations_ms": stage_durations,
                    "trace_spans": trace_spans,
                },
            )
        except Exception as e:
            telemetry_error = e
            telemetry_status = "failed"
            raise
        finally:
            await self._record_diagnostic(
                "record_retrieval",
                telemetry.record_retrieval(
                    query=query,
                    collection_id=collection_id,
                    status=telemetry_status,
                    duration_ms=telemetry.elapsed_ms(started_at),
                    index_type=context.creation_settings.get("index_type") or "chunk",
                    search_type=search_type,
                    top_k=top_k,
                    fetch_k=fetch_k,
                    raw_count=raw_count,
                    result_count=result_count,
                    reference_count=reference_count,
                    heading_count=heading_count,
                    context_expanded_count=context_expanded_count,
                    distance_min=distance_min,
                    distance_avg=distance_avg,
                    distance_max=distance_max,
                    filters=context.filters,
                    creation_settings=context.creation_settings,
                    retrieval_settings=context.retrieval_settings,
                    stage_durations_ms=stage_durations,
                    trace_spans=_trace_spans(trace_id, stage_durations),
                    reranked=reranked,
                    knowledge_base_id=context.knowledge_base_id,
                    trace_id=trace_id,
                    correlation=correlation,
                    error=telemetry_error,
                ),
            )

    @serialized
    async def delete_document(self, kb_id: str, document_id: str) -> bool:
        """Delete a document's vectors by file_id."""
        telemetry = self.plugin.telemetry
        started_at = telemetry.start_timer()
        trace_id = telemetry.new_trace_id("delete")
        status = "failed"
        error = None
        deleted = None
        count = None
        try:
            result_count = await self._state.mutate(
                self.plugin,
                kb_id,
                lambda: self.plugin.vector_delete(
                    collection_id=kb_id,
                    file_ids=[document_id],
                ),
                'Host vector_delete outcome unknown',
            )
            # The Host answered, but a malformed count does not say what happened
            # to the rows: the vector store's state is unknown, so this knowledge
            # base has to be reconciled before it accepts another mutation.
            if type(result_count) is not int or result_count < 0:
                await self._state.fence(
                    self.plugin,
                    kb_id,
                    'Host vector_delete returned a malformed count',
                )
                raise ValueError("Host vector_delete must return a nonnegative integer count")
            count = result_count
            # An authoritative no-op also confirms absence (empty ingest or retry).
            deleted = True
            status = "completed"
            return deleted
        except Exception as e:
            error = e
            raise
        finally:
            await self._record_diagnostic(
                "record_delete",
                telemetry.record_delete(
                    collection_id=kb_id,
                    document_id=document_id,
                    status=status,
                    duration_ms=telemetry.elapsed_ms(started_at),
                    deleted=deleted,
                    vectors_deleted=count,
                    knowledge_base_id=kb_id,
                    trace_id=trace_id,
                    error=error,
                ),
            )
