# StickerHub Tool - store a sticker image
from __future__ import annotations

import json
import logging
from typing import Any

from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.provider.session import Session

logger = logging.getLogger(__name__)


class AddSticker(Tool):
    """Tool that stores a sticker image for later retrieval by name."""

    async def call(
        self, params: dict[str, Any], session: Session, query_id: int
    ) -> str:
        payload = params or {}
        name = str(payload.get("name") or "").strip()
        if not name:
            return json.dumps({"ok": False, "error": "name is required"})
        url = str(payload.get("url") or "").strip()
        data_url = str(payload.get("data_url") or "").strip()
        if not url and not data_url:
            return json.dumps(
                {"ok": False, "error": "url or data_url is required"}
            )
        try:
            if url:
                sticker = await self.plugin.add_sticker_from_url(
                    name, url, source="ai"
                )
            else:
                sticker = await self.plugin.add_sticker_from_base64(
                    name, data_url, source="ai"
                )
        except ValueError as exc:
            return json.dumps({"ok": False, "error": str(exc)})
        return json.dumps({"ok": True, "sticker": sticker})
