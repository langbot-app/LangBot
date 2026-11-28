# StickerHub Hub Page - backend API handler
from __future__ import annotations

import logging
from typing import Any

from langbot_plugin.api.definition.components.page import Page, PageRequest, PageResponse

logger = logging.getLogger(__name__)


class HubPage(Page):
    """StickerHub management page.

    Serves upload, gallery, preview and administration. The human reply flow and
    the AI tool flow share the same ``StickerHub`` plugin object, so every
    mutation here is visible to tools and vice versa.
    """

    async def handle_api(self, request: PageRequest) -> PageResponse:
        plugin = self.plugin
        endpoint = request.endpoint
        method = request.method
        body = request.body if isinstance(request.body, dict) else {}

        try:
            if endpoint == "/stats" and method == "GET":
                return PageResponse.ok(await plugin.stats())

            if endpoint == "/list" and method == "GET":
                try:
                    limit = int(body.get("limit", 100))
                except (TypeError, ValueError):
                    limit = 100
                try:
                    offset = max(0, int(body.get("offset", 0)))
                except (TypeError, ValueError):
                    offset = 0
                return PageResponse.ok(
                    await plugin.list_stickers(limit=limit, offset=offset)
                )

            if endpoint == "/item" and method == "GET":
                name = str(body.get("name") or "").strip()
                if not name:
                    return PageResponse.fail("name is required")
                item = await plugin.get_sticker(name)
                if item is None:
                    return PageResponse.fail("sticker not found")
                return PageResponse.ok(item)

            if endpoint == "/image" and method == "GET":
                # Fallback only: the page renders ``item.url`` first and asks
                # for these bytes when the asset route fails.
                name = str(body.get("name") or "").strip()
                if not name:
                    return PageResponse.fail("name is required")
                image = await plugin.sticker_image(name)
                if image is None:
                    return PageResponse.fail("sticker not found")
                if body.get("with_data"):
                    return PageResponse.ok(image)
                image.pop("base64", None)
                return PageResponse.ok(image)

            if endpoint == "/upload/begin" and method == "POST":
                return PageResponse.ok(await plugin.begin_upload())

            if endpoint == "/upload/chunk" and method == "POST":
                session = str(body.get("session") or "").strip()
                if not session:
                    return PageResponse.fail("session is required")
                try:
                    index = int(body.get("index"))
                except (TypeError, ValueError):
                    return PageResponse.fail("index is required")
                try:
                    return PageResponse.ok(
                        await plugin.put_upload_chunk(
                            session, index, str(body.get("data") or "")
                        )
                    )
                except ValueError as exc:
                    return PageResponse.fail(str(exc))

            if endpoint == "/upload/finish" and method == "POST":
                name = str(body.get("name") or "").strip()
                session = str(body.get("session") or "").strip()
                if not name:
                    return PageResponse.fail("name is required")
                if not session:
                    return PageResponse.fail("session is required")
                try:
                    item = await plugin.finish_upload(
                        name, session, str(body.get("mime") or "") or None
                    )
                except ValueError as exc:
                    return PageResponse.fail(str(exc))
                return PageResponse.ok(item)

            if endpoint == "/upload/abort" and method == "POST":
                await plugin.abort_upload(str(body.get("session") or "").strip())
                return PageResponse.ok({"aborted": True})

            if endpoint == "/add" and method == "POST":
                name = str(body.get("name") or body.get("slug") or "").strip()
                if not name:
                    return PageResponse.fail("name is required")
                url = str(body.get("url") or "").strip()
                data_url = str(body.get("data_url") or "").strip()
                try:
                    if url:
                        item = await plugin.add_sticker_from_url(
                            name, url, source="human"
                        )
                    elif data_url:
                        item = await plugin.add_sticker_from_base64(
                            name, data_url, source="human"
                        )
                    else:
                        return PageResponse.fail("url or data_url is required")
                except ValueError as exc:
                    return PageResponse.fail(str(exc))
                return PageResponse.ok(item)

            if endpoint == "/delete" and method == "POST":
                name = str(body.get("name") or "").strip()
                if not name:
                    return PageResponse.fail("name is required")
                deleted = await plugin.delete_sticker(name)
                if not deleted:
                    return PageResponse.fail("sticker not found")
                return PageResponse.ok({"deleted": True, "name": name})

            if endpoint == "/clear" and method == "DELETE":
                removed = await plugin.clear_stickers()
                return PageResponse.ok({"cleared": removed})

            return PageResponse.fail(f"Unknown: {method} {endpoint}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("StickerHub HubPage error on %s %s", method, endpoint)
            return PageResponse.fail(str(exc))

    @staticmethod
    def _param(request: PageRequest, key: str) -> str:
        body = request.body
        if isinstance(body, dict) and body.get(key):
            return str(body[key])
        return ""

    def _data(self, value: Any) -> Any:
        return value
