# StickerHub Tool - stable interface for the stable sticker URL
from __future__ import annotations

import logging
from typing import Any

from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.provider.session import Session

logger = logging.getLogger(__name__)


class GetStickerUrl(Tool):
    """Return the stable URL for a stored sticker.

    This is the stable integration contract for other plugins (notably
    HumanTakeover): call ``stickerhub_get_sticker_url`` and use the returned
    string as the image URL. The string is ``None`` when ``public_base_url`` is
    empty, which yields a relative ``/api/v1/plugins/...`` path.
    """

    async def call(
        self, params: dict[str, Any], session: Session, query_id: int
    ) -> str:
        payload = params or {}
        name = str(payload.get("name") or "").strip()
        if not name:
            return "error: name is required"
        url = await self.plugin.media_url(name)
        if not url:
            return f"error: sticker {name!r} not found"
        return url
