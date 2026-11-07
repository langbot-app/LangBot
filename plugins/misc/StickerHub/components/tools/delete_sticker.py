# StickerHub Tool - delete a stored sticker
from __future__ import annotations

import json
import logging
from typing import Any

from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.provider.session import Session

logger = logging.getLogger(__name__)


class DeleteSticker(Tool):
    """Delete a stored sticker by name."""

    async def call(
        self, params: dict[str, Any], session: Session, query_id: int
    ) -> str:
        payload = params or {}
        name = str(payload.get("name") or "").strip()
        if not name:
            return json.dumps({"ok": False, "error": "name is required"})
        deleted = await self.plugin.delete_sticker(name)
        return json.dumps({"ok": bool(deleted), "name": name})
