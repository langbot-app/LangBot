from __future__ import annotations

import asyncio
from typing import Any

from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.provider import session as provider_session


class QAPluginSleepTool(Tool):
    async def call(
        self,
        params: dict[str, Any],
        session: provider_session.Session,
        query_id: int,
    ) -> str:
        raw_seconds = params.get("seconds", 0)
        try:
            seconds = float(raw_seconds)
        except (TypeError, ValueError):
            seconds = 0.0
        seconds = max(0.0, min(seconds, 15.0))
        text = str(params.get("text", ""))
        await asyncio.sleep(seconds)
        seconds_label = str(int(seconds)) if seconds.is_integer() else str(seconds)
        return f"qa-plugin-smoke:sleep:{seconds_label}:{text}"
