from __future__ import annotations

from typing import Any

from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.provider import session as provider_session

from powercontext_client import PowerContextError


class Remember(Tool):
    async def call(
        self,
        params: dict[str, Any],
        session: provider_session.Session,
        query_id: int,
    ) -> str:
        text = params.get("text", "")
        kind = params.get("kind", "fact")
        reason = params.get("reason")
        if not isinstance(text, str) or not text.strip():
            return "Error: text is required."
        if len(text.strip().encode("utf-8")) > 8192:
            return "Error: text must not exceed 8192 UTF-8 bytes."
        if not isinstance(kind, str) or not kind.strip() or len(kind.strip()) > 128:
            return "Error: kind must be a non-empty string of at most 128 characters."
        if reason is not None and (not isinstance(reason, str) or len(reason) > 512):
            return "Error: reason must be a string of at most 512 characters."

        try:
            settings = self.plugin.settings()
            resolved = await self.plugin.resolve_query(
                session=session,
                query_id=query_id,
            )
            response = await settings.new_client().remember(
                scope_id=resolved.scope_id,
                kind=kind.strip(),
                text=text.strip(),
                reason=reason.strip()
                if isinstance(reason, str) and reason.strip()
                else None,
            )
        except PowerContextError as exc:
            return f"Error: {exc.safe_summary()}"
        except Exception as exc:
            return f"Error: {str(exc)[:300]}"

        entry = response.data.get("entry") or {}
        citation = entry.get("citation") if isinstance(entry, dict) else None
        return f"Remembered in PowerContext scope {resolved.scope_id}. Citation: {citation}"
