# StickerHub Tool - list stored stickers
from __future__ import annotations

import json
import logging
from typing import Any

from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.provider.session import Session

logger = logging.getLogger(__name__)


class ListStickers(Tool):
    """Return a short page of stored stickers with their stable URLs."""

    async def call(
        self, params: dict[str, Any], session: Session, query_id: int
    ) -> str:
        payload = params or {}
        try:
            limit = int(payload.get("limit", 20))
        except (TypeError, ValueError):
            limit = 20
        page = await self.plugin.list_stickers(limit=limit)
        return json.dumps(
            {
                "ok": True,
                "total": page.get("total", 0),
                "items": [
                    {
                        "name": item.get("slug", ""),
                        "uri": item.get("url", ""),
                        "mime": item.get("mime", ""),
                        "size": item.get("size", 0),
                    }
                    for item in page.get("items", [])
                ],
            }
        )
