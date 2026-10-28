from __future__ import annotations

from langbot_plugin.api.definition.components.page import Page, PageRequest, PageResponse


class DashboardPage(Page):
    """FAQ Dashboard — read-only stats overview."""

    async def handle_api(self, request: PageRequest) -> PageResponse:
        plugin = self.plugin

        if request.endpoint == '/stats':
            entries = await plugin.get_entries()
            total = len(entries)
            avg_len = 0
            if total > 0:
                avg_len = sum(len(e['answer']) for e in entries) // total
            return PageResponse.ok({
                'total_entries': total,
                'avg_answer_length': avg_len,
            })

        return PageResponse.fail(f'Unknown endpoint: {request.method} {request.endpoint}')
