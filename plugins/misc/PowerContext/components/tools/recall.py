from __future__ import annotations

import json
from typing import Any

from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.provider import session as provider_session

from powercontext_client import PowerContextError


class Recall(Tool):
    async def call(
        self,
        params: dict[str, Any],
        session: provider_session.Session,
        query_id: int,
    ) -> str:
        query = params.get("query", "")
        if not isinstance(query, str) or not query.strip():
            return "Error: query is required."
        limit = params.get("limit", self.plugin.settings().search_limit)
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 50
        ):
            return "Error: limit must be an integer between 1 and 50."
        mode = params.get("mode", "auto")
        if mode not in {"auto", "fts", "vector", "hybrid"}:
            return "Error: mode must be auto, fts, vector, or hybrid."

        try:
            settings = self.plugin.settings()
            resolved = await self.plugin.resolve_query(
                session=session, query_id=query_id
            )
            response = await settings.new_client().search_memory(
                scope_id=resolved.scope_id,
                query=query.strip()[:8192],
                limit=limit,
                mode=mode,
            )
        except PowerContextError as exc:
            return f"Error: {exc.safe_summary()}"
        except Exception as exc:
            return f"Error: {str(exc)[:300]}"

        hits = response.data.get("hits", [])
        if not hits:
            return "No relevant PowerContext memories found."
        return json.dumps(
            {
                "scope_id": resolved.scope_id,
                "mode": response.data.get("mode"),
                "hits": hits,
            },
            ensure_ascii=False,
        )
