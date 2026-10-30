from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.provider import session as provider_session
from langbot_plugin.api.proxies.query_based_api import QueryBasedAPIProxy

logger = logging.getLogger(__name__)


class QueryKnowledge(Tool):
    @staticmethod
    def _preview_text(value: str, max_len: int = 120) -> str:
        text = value.strip().replace("\n", " ")
        if len(text) <= max_len:
            return text
        return f"{text[:max_len]}..."

    @staticmethod
    def _normalize_kb_ids(params: dict[str, Any]) -> tuple[list[str] | None, str | None]:
        kb_id = params.get("kb_id")
        kb_ids = params.get("kb_ids")

        normalized_ids: list[str] = []

        if kb_id is not None:
            if not isinstance(kb_id, str):
                return None, "kb_id must be a string."
            if not kb_id.strip():
                return None, "kb_id must be a non-empty string."
            normalized_ids.append(kb_id.strip())

        if kb_ids is not None:
            if not isinstance(kb_ids, list):
                return None, "kb_ids must be an array of strings."
            if not kb_ids:
                if normalized_ids:
                    kb_ids = None
                else:
                    return None, "kb_ids must be a non-empty array of strings. For a single knowledge base, use kb_id instead."

            if kb_ids is not None:
                for item in kb_ids:
                    if not isinstance(item, str) or not item.strip():
                        return None, "kb_ids must contain only non-empty strings."
                    normalized_ids.append(item.strip())

        if not normalized_ids:
            return None, "Either kb_id or kb_ids is required for action 'query'."

        deduped_ids: list[str] = []
        seen_ids: set[str] = set()
        for item in normalized_ids:
            if item not in seen_ids:
                seen_ids.add(item)
                deduped_ids.append(item)

        return deduped_ids, None

    @staticmethod
    def _sort_key(result: dict[str, Any]) -> tuple[int, float]:
        distance = result.get("distance")
        if isinstance(distance, (int, float)):
            return (0, float(distance))

        score = result.get("score")
        if isinstance(score, (int, float)):
            return (1, -float(score))

        return (2, 0.0)

    @staticmethod
    def _attach_kb_metadata(result: dict[str, Any], kb_id: str) -> dict[str, Any]:
        enriched = dict(result)
        metadata = enriched.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        else:
            metadata = dict(metadata)

        metadata.setdefault("knowledge_base_id", kb_id)
        enriched["metadata"] = metadata
        return enriched

    async def call(self, params: dict[str, Any], session: provider_session.Session, query_id: int) -> str:
        api = QueryBasedAPIProxy(
            query_id=query_id,
            plugin_runtime_handler=self.plugin.plugin_runtime_handler,
        )

        action = params.get("action", "list")
        logger.info(
            "[AgenticRAG] tool call started: query_id=%s action=%s params_keys=%s",
            query_id,
            action,
            sorted(params.keys()),
        )

        if action == "list":
            logger.info("[AgenticRAG] listing knowledge bases: query_id=%s", query_id)
            knowledge_bases = await api.list_pipeline_knowledge_bases()
            logger.info(
                "[AgenticRAG] knowledge base list loaded: query_id=%s kb_count=%s",
                query_id,
                len(knowledge_bases),
            )
            if not knowledge_bases:
                return "No knowledge bases are configured for the current pipeline."
            return json.dumps(knowledge_bases, ensure_ascii=False)

        elif action == "query":
            query_text = params.get("query_text")
            if not isinstance(query_text, str) or not query_text.strip():
                logger.warning(
                    "[AgenticRAG] invalid query_text: query_id=%s query_text=%r",
                    query_id,
                    query_text,
                )
                return "query_text must be a non-empty string."

            top_k = params.get("top_k", 5)
            if not isinstance(top_k, int) or top_k <= 0:
                logger.warning(
                    "[AgenticRAG] invalid top_k: query_id=%s top_k=%r",
                    query_id,
                    top_k,
                )
                return "top_k must be a positive integer."

            kb_ids, kb_error = self._normalize_kb_ids(params)
            if kb_error:
                logger.warning(
                    "[AgenticRAG] invalid kb params: query_id=%s error=%s",
                    query_id,
                    kb_error,
                )
                return kb_error

            # Keep the agent-facing tool surface minimal here. Although the
            # underlying runtime supports metadata filters, different knowledge
            # engines do not expose a consistent, query-time filter schema to
            # the agent, so passing raw filters would be unreliable.
            query_text = query_text.strip()
            logger.info(
                "[AgenticRAG] retrieval requested: query_id=%s kb_ids=%s kb_count=%s top_k=%s query=%r",
                query_id,
                kb_ids,
                len(kb_ids),
                top_k,
                self._preview_text(query_text),
            )

            async def _query_single_kb(target_kb_id: str) -> dict[str, Any]:
                try:
                    logger.info(
                        "[AgenticRAG] querying knowledge base: query_id=%s kb_id=%s top_k=%s",
                        query_id,
                        target_kb_id,
                        top_k,
                    )
                    kb_results = await api.retrieve_knowledge(
                        kb_id=target_kb_id,
                        query_text=query_text,
                        top_k=top_k,
                    )
                    logger.info(
                        "[AgenticRAG] knowledge base query succeeded: query_id=%s kb_id=%s result_count=%s",
                        query_id,
                        target_kb_id,
                        len(kb_results),
                    )
                    return {
                        "kb_id": target_kb_id,
                        "results": [
                            self._attach_kb_metadata(result, target_kb_id)
                            for result in kb_results
                            if isinstance(result, dict)
                        ],
                        "error": None,
                    }
                except Exception as exc:
                    logger.exception(
                        "[AgenticRAG] knowledge base query failed: query_id=%s kb_id=%s error=%s",
                        query_id,
                        target_kb_id,
                        exc,
                    )
                    return {
                        "kb_id": target_kb_id,
                        "results": [],
                        "error": str(exc),
                    }

            retrieval_outcomes = await asyncio.gather(*[_query_single_kb(kb_id) for kb_id in kb_ids])
            merged_results = [
                result
                for outcome in retrieval_outcomes
                for result in outcome["results"]
            ]
            failed_kbs = [
                {"kb_id": outcome["kb_id"], "error": outcome["error"]}
                for outcome in retrieval_outcomes
                if outcome["error"] is not None
            ]
            logger.info(
                "[AgenticRAG] retrieval completed: query_id=%s merged_results=%s failed_kbs=%s",
                query_id,
                len(merged_results),
                len(failed_kbs),
            )

            if not merged_results:
                if failed_kbs:
                    logger.info(
                        "[AgenticRAG] returning failure summary: query_id=%s failed_kbs=%s",
                        query_id,
                        failed_kbs,
                    )
                    return json.dumps({"results": [], "failed_kbs": failed_kbs}, ensure_ascii=False)
                logger.info("[AgenticRAG] no relevant documents found: query_id=%s", query_id)
                return "No relevant documents found."

            merged_results.sort(key=self._sort_key)
            truncated_results = merged_results[:top_k]
            logger.info(
                "[AgenticRAG] returning retrieval response: query_id=%s returned_results=%s truncated=%s",
                query_id,
                len(truncated_results),
                len(merged_results) > len(truncated_results),
            )
            if failed_kbs:
                return json.dumps(
                    {"results": truncated_results, "failed_kbs": failed_kbs},
                    ensure_ascii=False,
                )
            return json.dumps(truncated_results, ensure_ascii=False)

        else:
            logger.warning(
                "[AgenticRAG] unknown action: query_id=%s action=%r",
                query_id,
                action,
            )
            return f"Unknown action: {action}. Use 'list' or 'query'."
