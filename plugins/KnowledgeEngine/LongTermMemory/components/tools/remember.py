from __future__ import annotations

import logging
from typing import Any

from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.provider import session as provider_session
from langbot_plugin.api.proxies.query_based_api import QueryBasedAPIProxy

logger = logging.getLogger(__name__)


class Remember(Tool):
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
            "[LongTermMemory] remember called: query_id=%s params_keys=%s",
            query_id,
            sorted(params.keys()),
        )
        bot_uuid = await api.get_bot_uuid()
        query_vars = await api.get_query_vars()
        session_key, user_key, kb_id, _, config = await store.resolve_user_context(
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

        content = params.get("content", "")
        if not content:
            return "Error: content is required."

        tags = params.get("tags", [])
        importance = params.get("importance", 2)
        sender_id = str(query_vars.get("sender_id", "") or "")
        sender_name = str(query_vars.get("sender_name", "") or "")
        logger.info(
            "[LongTermMemory] remember storing episode: query_id=%s kb_id=%s user_key=%s sender_id=%s importance=%s tags=%s content_len=%s",
            query_id,
            kb_id,
            user_key,
            sender_id,
            importance,
            tags,
            len(str(content)),
        )

        episode = await store.add_episode(
            collection_id=kb_id,
            embedding_model_uuid=embedding_model_uuid,
            user_key=user_key,
            content=content,
            tags=tags,
            importance=importance,
            sender_id=sender_id,
            sender_name=sender_name,
            bot_uuid=bot_uuid,
        )

        logger.info(
            "[LongTermMemory] remember stored: query_id=%s episode_id=%s user_key=%s content_len=%s",
            query_id,
            episode["id"],
            user_key,
            len(str(content)),
        )
        await store.append_audit_entry(
            scope_key=session_key,
            user_key=user_key,
            operation="remember",
            target_type="episode",
            target_id=episode["id"],
            summary=self._preview_text(str(content)),
            sender_id=sender_id,
            sender_name=sender_name,
            query_id=query_id,
            metadata={
                "kb_id": kb_id,
                "tags": tags,
                "importance": importance,
                "status": episode.get("status", "active"),
            },
        )

        return f"Remembered: {content}"
