"""Query rewriting strategies for retrieval augmentation.

Provides HyDE, Multi-Query, and Step-Back rewriting to improve recall quality.
Each strategy rewrites/expands the user query before embedding and searching.
"""

import logging

from langbot_plugin.api.entities.builtin.provider.message import Message
from components.observability.telemetry import add_stage_duration, hash_text, telemetry

logger = logging.getLogger(__name__)

MULTI_QUERY_COUNT = 3

HYDE_PROMPT = """Please write a short passage that would answer the following question.
Write as if you are writing a paragraph from a reference document.
Do not say "I don't know" — just write a plausible answer.

Question: {query}

Passage:"""

MULTI_QUERY_PROMPT = """Given the following user question, generate {n} different search queries
that could help find relevant information. Each query should approach the question from a
different angle or use different terminology.

User question: {query}

Output exactly {n} queries, one per line (no numbering, no bullets):"""

STEP_BACK_PROMPT = """Given the following specific question, generate a more general/abstract
question that would help retrieve broader background context.

Specific question: {query}

General question:"""


def _extract_text(msg: Message) -> str:
    """Extract plain text from an LLM response Message."""
    if isinstance(msg.content, str):
        return msg.content.strip()
    if isinstance(msg.content, list):
        return "".join(e.text for e in msg.content if e.type == "text").strip()
    return ""


def _vector_result_sort_key(result: dict) -> tuple[int, float]:
    """Prefer lower distance; fall back to legacy score-as-distance."""
    distance = result.get("distance")
    if isinstance(distance, (int, float)):
        return (0, float(distance))

    score = result.get("score")
    if isinstance(score, (int, float)):
        return (1, float(score))

    return (2, float("inf"))


def _uses_vector(search_type) -> bool:
    """Return whether this search mode needs an embedding vector."""
    return getattr(search_type, "value", search_type) != "full_text"


def _text_log_ref(text: str | None) -> str:
    """Return a privacy-preserving text reference for logs."""
    return f"hash={hash_text(text)}, length={len(text or '')}"


async def _timed_call(stage_durations: dict[str, float] | None, stage: str, call):
    started_at = telemetry.start_timer()
    try:
        return await call()
    finally:
        if stage_durations is not None:
            add_stage_duration(stage_durations, stage, telemetry.elapsed_ms(started_at))


async def retrieve_with_rewrite(
    plugin,
    query: str,
    query_rewrite: str,
    rewrite_llm: str,
    collection_id: str,
    embedding_model_uuid: str,
    fetch_k: int,
    filters,
    search_type,
    vector_weight=None,
    stage_durations: dict[str, float] | None = None,
) -> list[dict]:
    """Route to the appropriate rewrite strategy and return raw search results."""
    if query_rewrite == "hyde":
        return await _retrieve_hyde(
            plugin,
            query,
            rewrite_llm,
            collection_id,
            embedding_model_uuid,
            fetch_k,
            filters,
            search_type,
            vector_weight,
            stage_durations,
        )
    elif query_rewrite == "multi_query":
        return await _retrieve_multi_query(
            plugin,
            query,
            rewrite_llm,
            collection_id,
            embedding_model_uuid,
            fetch_k,
            filters,
            search_type,
            vector_weight,
            stage_durations,
        )
    elif query_rewrite == "step_back":
        return await _retrieve_step_back(
            plugin,
            query,
            rewrite_llm,
            collection_id,
            embedding_model_uuid,
            fetch_k,
            filters,
            search_type,
            vector_weight,
            stage_durations,
        )
    else:
        logger.warning(
            f"Unknown query_rewrite strategy: {query_rewrite}, falling back to direct search"
        )
        query_vector: list[float] = []
        if _uses_vector(search_type):
            query_vectors = await _timed_call(
                stage_durations,
                "rewrite_embedding",
                lambda: plugin.invoke_embedding(embedding_model_uuid, [query]),
            )
            query_vector = query_vectors[0]
        return await _timed_call(
            stage_durations,
            "rewrite_vector_search",
            lambda: plugin.vector_search(
                collection_id=collection_id,
                query_vector=query_vector,
                top_k=fetch_k,
                filters=filters,
                search_type=search_type,
                query_text=query,
                vector_weight=vector_weight,
            ),
        )


async def _retrieve_hyde(
    plugin,
    query,
    rewrite_llm,
    collection_id,
    embedding_model_uuid,
    fetch_k,
    filters,
    search_type,
    vector_weight=None,
    stage_durations: dict[str, float] | None = None,
) -> list[dict]:
    """HyDE: generate a hypothetical document, embed it, and search with that vector."""
    logger.info(
        f"[HyDE] Generating hypothetical document "
        f"for query_ref=({_text_log_ref(query)})"
    )
    prompt = HYDE_PROMPT.format(query=query)
    resp = await _timed_call(
        stage_durations,
        "rewrite_llm",
        lambda: plugin.invoke_llm(rewrite_llm, [Message(role="user", content=prompt)]),
    )
    hypothetical_doc = _extract_text(resp) or query
    logger.info(f"[HyDE] Hypothetical document ref: {_text_log_ref(hypothetical_doc)}")

    query_vector: list[float] = []
    if _uses_vector(search_type):
        logger.info("[HyDE] Embedding hypothetical document and searching...")
        hyde_vectors = await _timed_call(
            stage_durations,
            "rewrite_embedding",
            lambda: plugin.invoke_embedding(embedding_model_uuid, [hypothetical_doc]),
        )
        query_vector = hyde_vectors[0]
    else:
        logger.info("[HyDE] Searching with hypothetical document text...")
    results = await _timed_call(
        stage_durations,
        "rewrite_vector_search",
        lambda: plugin.vector_search(
            collection_id=collection_id,
            query_vector=query_vector,
            top_k=fetch_k,
            filters=filters,
            search_type=search_type,
            query_text=hypothetical_doc,
            vector_weight=vector_weight,
        ),
    )
    logger.info(f"[HyDE] Search returned {len(results)} results")
    return results


async def _retrieve_multi_query(
    plugin,
    query,
    rewrite_llm,
    collection_id,
    embedding_model_uuid,
    fetch_k,
    filters,
    search_type,
    vector_weight=None,
    stage_durations: dict[str, float] | None = None,
) -> list[dict]:
    """Multi-Query: generate N query variants, search with each, merge and deduplicate."""
    logger.info(
        f"[Multi-Query] Generating {MULTI_QUERY_COUNT} sub-queries "
        f"for query_ref=({_text_log_ref(query)})"
    )
    prompt = MULTI_QUERY_PROMPT.format(query=query, n=MULTI_QUERY_COUNT)
    resp = await _timed_call(
        stage_durations,
        "rewrite_llm",
        lambda: plugin.invoke_llm(rewrite_llm, [Message(role="user", content=prompt)]),
    )
    raw_text = _extract_text(resp)
    sub_queries = [line.strip() for line in raw_text.splitlines() if line.strip()]
    sub_queries = sub_queries[:MULTI_QUERY_COUNT]
    logger.info(
        "[Multi-Query] Generated sub-query refs: "
        + ", ".join(_text_log_ref(sq) for sq in sub_queries)
    )

    # Search original query + sub-queries
    all_queries = [query] + sub_queries
    logger.info(
        f"[Multi-Query] Searching {len(all_queries)} queries "
        f"(1 original + {len(sub_queries)} generated)"
    )
    if _uses_vector(search_type):
        all_vectors = await _timed_call(
            stage_durations,
            "rewrite_embedding",
            lambda: plugin.invoke_embedding(embedding_model_uuid, all_queries),
        )
    else:
        all_vectors = [[] for _ in all_queries]

    # Search with each vector and merge results
    seen_ids: set[str] = set()
    merged: list[dict] = []
    for i, (search_query, vec) in enumerate(zip(all_queries, all_vectors)):
        results = await _timed_call(
            stage_durations,
            "rewrite_vector_search",
            lambda search_query=search_query, vec=vec: plugin.vector_search(
                collection_id=collection_id,
                query_vector=vec,
                top_k=fetch_k,
                filters=filters,
                search_type=search_type,
                query_text=search_query,
                vector_weight=vector_weight,
            ),
        )
        new_count = sum(1 for r in results if r["id"] not in seen_ids)
        logger.info(
            f"[Multi-Query] Query [{i}] returned {len(results)} results ({new_count} new)"
        )
        for r in results:
            rid = r["id"]
            if rid not in seen_ids:
                seen_ids.add(rid)
                merged.append(r)

    # Prefer lower distance. Older hosts incorrectly exposed distance in score,
    # so score is only used as a compatibility fallback here.
    merged.sort(key=_vector_result_sort_key)
    merged = merged[:fetch_k]
    logger.info(
        f"[Multi-Query] Merged: {len(seen_ids)} unique results, returning {len(merged)}"
    )
    return merged


async def _retrieve_step_back(
    plugin,
    query,
    rewrite_llm,
    collection_id,
    embedding_model_uuid,
    fetch_k,
    filters,
    search_type,
    vector_weight=None,
    stage_durations: dict[str, float] | None = None,
) -> list[dict]:
    """Step-Back: generate a broader question, search with both original and abstract queries."""
    logger.info(
        f"[Step-Back] Generating abstract question "
        f"for query_ref=({_text_log_ref(query)})"
    )
    prompt = STEP_BACK_PROMPT.format(query=query)
    resp = await _timed_call(
        stage_durations,
        "rewrite_llm",
        lambda: plugin.invoke_llm(rewrite_llm, [Message(role="user", content=prompt)]),
    )
    abstract_query = _extract_text(resp) or query
    logger.info(f"[Step-Back] Abstract query ref: {_text_log_ref(abstract_query)}")

    # Search with both original and abstract queries
    both_queries = [query, abstract_query]
    logger.info("[Step-Back] Searching original + abstract queries...")
    if _uses_vector(search_type):
        both_vectors = await _timed_call(
            stage_durations,
            "rewrite_embedding",
            lambda: plugin.invoke_embedding(
                embedding_model_uuid,
                both_queries,
            ),
        )
    else:
        both_vectors = [[] for _ in both_queries]

    # Search with both vectors and merge
    seen_ids: set[str] = set()
    merged: list[dict] = []
    for i, (search_query, vec) in enumerate(zip(both_queries, both_vectors)):
        label = "original" if i == 0 else "abstract"
        results = await _timed_call(
            stage_durations,
            "rewrite_vector_search",
            lambda search_query=search_query, vec=vec: plugin.vector_search(
                collection_id=collection_id,
                query_vector=vec,
                top_k=fetch_k,
                filters=filters,
                search_type=search_type,
                query_text=search_query,
                vector_weight=vector_weight,
            ),
        )
        new_count = sum(1 for r in results if r["id"] not in seen_ids)
        logger.info(
            f"[Step-Back] {label} query returned {len(results)} results ({new_count} new)"
        )
        for r in results:
            rid = r["id"]
            if rid not in seen_ids:
                seen_ids.add(rid)
                merged.append(r)

    merged.sort(key=_vector_result_sort_key)
    merged = merged[:fetch_k]
    logger.info(
        f"[Step-Back] Merged: {len(seen_ids)} unique results, returning {len(merged)}"
    )
    return merged
