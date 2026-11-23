from __future__ import annotations

from langbot_plugin.api.definition.components.page import Page, PageRequest, PageResponse


class SmokePage(Page):
    async def handle_api(self, request: PageRequest) -> PageResponse:
        return PageResponse.ok(
            {
                "sentinel": "qa-plugin-smoke-page",
                "endpoint": request.endpoint,
                "method": request.method,
                "body": request.body,
            }
        )
