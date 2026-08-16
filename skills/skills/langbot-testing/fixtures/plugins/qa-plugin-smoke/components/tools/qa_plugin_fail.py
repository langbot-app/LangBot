from __future__ import annotations

from typing import Any

from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.provider import session as provider_session


class QAPluginFailTool(Tool):
    async def call(
        self,
        params: dict[str, Any],
        session: provider_session.Session,
        query_id: int,
    ) -> str:
        text = str(params.get("text", "qa-plugin-fail"))
        raise RuntimeError(f"qa-plugin-smoke forced failure: {text}")
