from __future__ import annotations

import json
import logging
from typing import Any

from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.provider import session as provider_session
from langbot_plugin.api.proxies.query_based_api import QueryBasedAPIProxy

logger = logging.getLogger(__name__)


class RecallMemory(Tool):
    @staticmethod
    def _preview_text(value: str, max_len: int = 120) -> str:
        text = value.strip().replace("\n", " ")
        if len(text) <= max_len:
            return text
        return f"{text[:max_len]}..."

    async def call(
        self,
        params: dict[str, Any],
        session: provider_session.Session,
        query_id: int,
    ) -> str:
        store = self.plugin.memory_store
        api = QueryBasedAPIProxy(
            query_id=query_id,
            plugin_runtime_handler=self.plugin.plugin_runtime_handler,
        )
        logger.info(
            "[LongTermMemory] recall_memory called: query_id=%s params_keys=%s",
            query_id,
            sorted(params.keys()),
        )
        bot_uuid = await api.get_bot_uuid()
        _, user_key, kb_id, _isolation, config = await store.resolve_user_context(
            session, bot_uuid
        )

        if not kb_id:
            return "Error: no memory knowledge base configured. Create one first."

        pipeline_kbs = await api.list_pipeline_knowledge_bases()
        if not any(kb.get("uuid") == kb_id for kb in pipeline_kbs):
            return "Error: memory knowledge base is not configured for the current pipeline."

        embedding_model_uuid = config.get("embedding_model_uuid", "")
        if not embedding_model_uuid:
            return "Error: no embedding model configured in knowledge base."

        query = params.get("query", "")
        if not isinstance(query, str) or not query.strip():
            return "Error: query is required."

        top_k = params.get("top_k", 5)
        if not isinstance(top_k, int) or top_k <= 0:
            return "Error: top_k must be a positive integer."

        speaker_id = params.get("speaker_id", "")
        if speaker_id is None:
            speaker_id = ""
        if not isinstance(speaker_id, str):
            return "Error: speaker_id must be a string."

        speaker_name = params.get("speaker_name", "")
        if speaker_name is None:
            speaker_name = ""
        if not isinstance(speaker_name, str):
            return "Error: speaker_name must be a string."

        time_after = params.get("time_after", "")
        if time_after is None:
            time_after = ""
        if not isinstance(time_after, str):
            return "Error: time_after must be a string."

        time_before = params.get("time_before", "")
        if time_before is None:
            time_before = ""
        if not isinstance(time_before, str):
            return "Error: time_before must be a string."

        source = params.get("source", "")
        if source is None:
            source = ""
        if not isinstance(source, str):
            return "Error: source must be a string."

        status = params.get("status", "active")
        if status is None:
            status = "active"
        if not isinstance(status, str):
            return "Error: status must be a string."
        status = status.strip().lower() or "active"
        if status not in store.EPISODE_STATUSES:
            return "Error: status must be one of active, superseded, archived, or deleted."

        importance_min = params.get("importance_min")
        if importance_min is not None and (
            not isinstance(importance_min, int) or importance_min < 1 or importance_min > 5
        ):
            return "Error: importance_min must be an integer between 1 and 5."

        logger.info(
            "[LongTermMemory] recall_memory searching: query_id=%s kb_id=%s user_key=%s top_k=%s speaker_id=%s speaker_name=%s source=%s status=%s importance_min=%s time_after=%s time_before=%s query_len=%s",
            query_id,
            kb_id,
            user_key,
            top_k,
            speaker_id.strip(),
            speaker_name.strip(),
            source.strip(),
            status,
            importance_min,
            time_after.strip(),
            time_before.strip(),
            len(query),
        )
        try:
            episodes = await store.search_episodes(
                collection_id=kb_id,
                embedding_model_uuid=embedding_model_uuid,
                query=query.strip(),
                user_key=user_key,
                top_k=top_k,
                sender_id=speaker_id.strip(),
                sender_name=speaker_name.strip(),
                time_after=time_after.strip(),
                time_before=time_before.strip(),
                importance_min=importance_min,
                source=source.strip(),
                include_statuses=[status],
                retrieval_strategy=config.get("retrieval_strategy", "auto"),
                vector_weight=config.get("vector_weight", 0.7),
                exact_match_boost=bool(config.get("exact_match_boost", True)),
            )
        except ValueError as exc:
            return f"Error: {exc}"

        if not episodes:
            logger.info(
                "[LongTermMemory] recall_memory no results: query_id=%s kb_id=%s",
                query_id,
                kb_id,
            )
            return "No relevant memories found."

        logger.info(
            "[LongTermMemory] recall_memory completed: query_id=%s kb_id=%s result_count=%s",
            query_id,
            kb_id,
            len(episodes),
        )
        return json.dumps(episodes, ensure_ascii=False)
