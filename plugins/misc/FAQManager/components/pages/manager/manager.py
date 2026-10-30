from __future__ import annotations

from langbot_plugin.api.definition.components.page import Page, PageRequest, PageResponse


class ManagerPage(Page):
    """FAQ Manager page — handles CRUD and search API calls."""

    async def handle_api(self, request: PageRequest) -> PageResponse:
        plugin = self.plugin

        if request.endpoint == '/entries' and request.method == 'GET':
            return PageResponse.ok({'entries': await plugin.get_entries()})

        if request.endpoint == '/entries' and request.method == 'POST':
            question = (request.body or {}).get('question', '').strip()
            answer = (request.body or {}).get('answer', '').strip()
            if not question or not answer:
                return PageResponse.fail('question and answer are required')
            entry = await plugin.add_entry(question, answer)
            await plugin.persist()
            return PageResponse.ok({'entry': entry})

        if request.endpoint == '/entries' and request.method == 'PUT':
            entry_id = (request.body or {}).get('id', '')
            entry = await plugin.update_entry(
                entry_id,
                (request.body or {}).get('question'),
                (request.body or {}).get('answer'),
            )
            if entry is None:
                return PageResponse.fail('entry not found')
            await plugin.persist()
            return PageResponse.ok({'entry': entry})

        if request.endpoint == '/entries' and request.method == 'DELETE':
            entry_id = (request.body or {}).get('id', '')
            if await plugin.delete_entry(entry_id):
                await plugin.persist()
                return PageResponse.ok({'deleted': entry_id})
            return PageResponse.fail('entry not found')

        if request.endpoint == '/search' and request.method == 'POST':
            query = (request.body or {}).get('query', '')
            return PageResponse.ok({'results': await plugin.search(query)})

        return PageResponse.fail(f'Unknown endpoint: {request.method} {request.endpoint}')
