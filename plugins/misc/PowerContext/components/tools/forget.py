from __future__ import annotations

from typing import Any

from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.provider import session as provider_session

from powercontext_client import PowerContextError


class Forget(Tool):
    async def call(
        self,
        params: dict[str, Any],
        session: provider_session.Session,
        query_id: int,
    ) -> str:
        artifact_id = params.get("memory_artifact_id", "")
        entry_id = params.get("entry_id", "")
        entry_version_id = params.get("entry_version_id", "")
        revision = params.get("memory_revision")
        reason = params.get("reason")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (artifact_id, entry_id, entry_version_id)
        ):
            return "Error: memory_artifact_id, entry_id, and entry_version_id are required."
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            return "Error: memory_revision must be a positive integer."
        if reason is not None and (not isinstance(reason, str) or len(reason) > 512):
            return "Error: reason must be a string of at most 512 characters."

        citation = {
            "memory_ref": {
                "family": "memory",
                "artifact_id": artifact_id.strip(),
                "revision": revision,
            },
            "entry_id": entry_id.strip(),
            "entry_version_id": entry_version_id.strip(),
        }
        try:
            settings = self.plugin.settings()
            resolved = await self.plugin.resolve_query(
                session=session, query_id=query_id
            )
            await settings.new_client().retire_memory(
                scope_id=resolved.scope_id,
                citation=citation,
                reason=reason.strip()
                if isinstance(reason, str) and reason.strip()
                else None,
            )
        except PowerContextError as exc:
            return f"Error: {exc.safe_summary()}"
        except Exception as exc:
            return f"Error: {str(exc)[:300]}"
        return f"Retired PowerContext memory entry {entry_id.strip()}."
