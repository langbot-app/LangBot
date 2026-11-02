from __future__ import annotations

import logging
from typing import Any

from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.provider import session as provider_session

logger = logging.getLogger(__name__)


class Forget(Tool):
    async def call(
        self,
        params: dict[str, Any],
        session: provider_session.Session,
        query_id: int,
    ) -> str:
        store = self.plugin.memory_store
        bot_uuid = session.bot_uuid or ""
        session_key, user_key, kb_id, _, config = await store.resolve_user_context(
            session, bot_uuid
        )

        if not kb_id:
            return "Error: no memory knowledge base configured."

        episode_id = params.get("episode_id", "")
        if not episode_id:
            return "Error: episode_id is required."

        logger.info(
            "[LongTermMemory] forget called: query_id=%s kb_id=%s user_key=%s episode_id=%s",
            query_id,
            kb_id,
            user_key,
            episode_id,
        )

        deleted = await store.delete_episode_by_id(
            collection_id=kb_id,
            episode_id=episode_id,
            user_key=user_key,
        )
        if not deleted:
            return "No matching memory found in the current scope."
        await store.append_audit_entry(
            scope_key=session_key,
            user_key=user_key,
            operation="forget",
            target_type="episode",
            target_id=str(episode_id),
            summary=f"Deleted episode {episode_id}",
            sender_id=str(session.sender_id or ""),
            query_id=query_id,
            metadata={"kb_id": kb_id, "deleted": deleted},
        )

        return f"Deleted episode {episode_id}."
