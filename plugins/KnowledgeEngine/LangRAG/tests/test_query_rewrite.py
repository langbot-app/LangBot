import unittest

from benchmarks.sdk_stubs import install_stubs

install_stubs()

from components.knowledge_engine.query_rewrite import retrieve_with_rewrite


class LLMResponse:
    def __init__(self, content):
        self.content = content


class RewritePlugin:
    def __init__(self, llm_response):
        self.llm_response = llm_response
        self.embedding_calls = []
        self.search_query_texts = []

    async def invoke_llm(self, llm_uuid, messages):
        return LLMResponse(self.llm_response)

    async def invoke_embedding(self, embedding_model_uuid, texts):
        self.embedding_calls.append(list(texts))
        return [[float(i)] for i, _ in enumerate(texts)]

    async def vector_search(self, **kwargs):
        query_text = kwargs["query_text"]
        self.search_query_texts.append(query_text)
        return [
            {
                "id": query_text,
                "distance": float(len(self.search_query_texts)),
                "metadata": {"text": query_text},
            }
        ]


class QueryRewriteTests(unittest.IsolatedAsyncioTestCase):
    async def test_multi_query_full_text_uses_rewritten_query_text_without_embedding(self):
        plugin = RewritePlugin("variant one\nvariant two\nvariant three")

        await retrieve_with_rewrite(
            plugin=plugin,
            query="original",
            query_rewrite="multi_query",
            rewrite_llm="llm1",
            collection_id="kb1",
            embedding_model_uuid="emb1",
            fetch_k=5,
            filters=None,
            search_type="full_text",
        )

        self.assertEqual(plugin.embedding_calls, [])
        self.assertEqual(
            plugin.search_query_texts,
            ["original", "variant one", "variant two", "variant three"],
        )

    async def test_hyde_full_text_uses_hypothetical_document_without_embedding(self):
        plugin = RewritePlugin("hypothetical answer passage")

        await retrieve_with_rewrite(
            plugin=plugin,
            query="original",
            query_rewrite="hyde",
            rewrite_llm="llm1",
            collection_id="kb1",
            embedding_model_uuid="emb1",
            fetch_k=5,
            filters=None,
            search_type="full_text",
        )

        self.assertEqual(plugin.embedding_calls, [])
        self.assertEqual(plugin.search_query_texts, ["hypothetical answer passage"])


if __name__ == "__main__":
    unittest.main()
