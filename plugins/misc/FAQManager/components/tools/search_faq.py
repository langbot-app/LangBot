from __future__ import annotations

from typing import Any

from langbot_plugin.api.definition.components.tool.tool import Tool


class SearchFAQ(Tool):
    """Search the FAQ knowledge base for matching entries."""

    async def call(self, params: dict[str, Any]) -> dict[str, Any]:
        query = params.get('query', '')
        results = await self.plugin.search(query)
        if not results:
            return {'message': 'No matching FAQ entries found.', 'results': []}
        return {
            'message': f'Found {len(results)} matching FAQ entries.',
            'results': [
                {'question': r['question'], 'answer': r['answer']}
                for r in results
            ],
        }
