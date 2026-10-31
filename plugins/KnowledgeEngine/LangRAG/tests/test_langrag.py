import asyncio
import unittest

from benchmarks.sdk_stubs import install_stubs

install_stubs()

from components.knowledge_engine.langrag import LangRAG, PARSED_TEXT_LIMIT_BYTES
from components.observability.installation import InstallationTelemetry
from components.offload import BoundedOffload
from components.shared_state import FENCE_KEY_PREFIX, FenceStateUnavailableError
from benchmarks.state_fixture import attach_installation_state
from langbot_plugin.api.entities.builtin.rag import (
    DocumentStatus,
    FileMetadata,
    FileObject,
    IngestionContext,
    ParseResult,
    RetrievalContext,
)


class ControllableStoragePlugin:
    """Host storage that can be taken offline, with observable remote calls."""

    def __init__(self):
        self.data = {}
        self.reads_offline = False
        self.embeddings = 0
        self.upserts = []
        self.deletes = []
        self.delete_entered = asyncio.Event()
        self.delete_release = asyncio.Event()
        self.delete_release.set()
        self.offload = BoundedOffload()
        self.telemetry = InstallationTelemetry(self)

    async def get_plugin_storage_keys(self):
        if self.reads_offline:
            raise RuntimeError("fixture fence store offline")
        return list(self.data)

    async def get_plugin_storage(self, key):
        if self.reads_offline:
            raise RuntimeError("fixture fence store offline")
        return self.data[key]

    async def set_plugin_storage(self, key, value):
        self.data[key] = value

    async def invoke_embedding(self, embedding_model_uuid, texts):
        self.embeddings += 1
        return [[float(i)] for i in range(len(texts))]

    async def vector_upsert(self, **kwargs):
        self.upserts.append(kwargs)

    async def vector_delete(self, **kwargs):
        self.deletes.append(kwargs)

        async def commit():
            # A detached Host commit outlives cancellation of the caller.
            self.delete_entered.set()
            await self.delete_release.wait()
            return 0

        return await asyncio.shield(asyncio.create_task(commit()))


def ingest_context(text="external parser text"):
    """One external-parser ingestion for knowledge base ``kb1``."""
    return IngestionContext(
        file_object=FileObject(
            metadata=FileMetadata(
                filename="sample.txt",
                file_size=len(text),
                mime_type="text/plain",
                document_id="doc1",
                knowledge_base_id="kb1",
            ),
            storage_path="/missing/sample.txt",
        ),
        knowledge_base_id="kb1",
        creation_settings={
            "embedding_model_uuid": "emb1",
            "chunk_size": 100,
            "overlap": 0,
        },
        parsed_content=ParseResult(text=text),
    )


async def bound_engine(plugin):
    engine = LangRAG()
    engine.plugin = plugin
    await plugin.telemetry.initialize()
    return engine


class RecordingIngestPlugin:
    def __init__(self):
        self.read_called = False
        self.upserts = []

    async def get_knowledge_file_stream(self, storage_path):
        self.read_called = True
        raise AssertionError("external parser content should skip file reads")

    async def invoke_embedding(self, embedding_model_uuid, texts):
        return [[float(i)] for i, _ in enumerate(texts)]

    async def vector_upsert(self, **kwargs):
        self.upserts.append(kwargs)


class RecordingVectorPlugin:
    def __init__(self, items):
        self.items = items
        self.requested_ids = []

    async def vector_get_by_ids(self, collection_id, ids):
        self.requested_ids = ids
        return [self.items[item_id] for item_id in ids if item_id in self.items]


class RecordingRetrievePlugin:
    def __init__(self):
        self.search_top_k = None
        self.rerank_documents = []
        self.rerank_top_k = None

    async def invoke_embedding(self, embedding_model_uuid, texts):
        return [[0.0] for _ in texts]

    async def vector_search(self, **kwargs):
        self.search_top_k = kwargs["top_k"]
        return [
            {
                "id": f"chunk-{i}",
                "distance": float(i),
                "metadata": {
                    "text": f"candidate {i}",
                    "document_name": "doc.txt",
                    "chunk_index": i,
                    "index_type": "chunk",
                },
            }
            for i in range(kwargs["top_k"])
        ]

    async def invoke_rerank(self, rerank_model_uuid, query, documents, top_k=None):
        self.rerank_documents = list(documents)
        self.rerank_top_k = top_k
        return [
            {"index": 2, "relevance_score": 0.95},
            {"index": 0, "relevance_score": 0.5},
        ]


class LangRAGTests(unittest.IsolatedAsyncioTestCase):
    async def test_ingest_uses_external_parse_result_without_reading_file(self):
        engine = LangRAG()
        plugin = RecordingIngestPlugin()
        await attach_installation_state(plugin)
        engine.plugin = plugin

        context = IngestionContext(
            file_object=FileObject(
                metadata=FileMetadata(
                    filename="sample.txt",
                    file_size=12,
                    mime_type="text/plain",
                    document_id="doc1",
                    knowledge_base_id="kb1",
                ),
                storage_path="/missing/sample.txt",
            ),
            knowledge_base_id="kb1",
            creation_settings={
                "embedding_model_uuid": "emb1",
                "chunk_size": 100,
                "overlap": 0,
            },
            parsed_content=ParseResult(text="external parser text"),
        )

        result = await engine.ingest(context)

        self.assertEqual(result.status, DocumentStatus.COMPLETED)
        self.assertFalse(plugin.read_called)
        self.assertEqual(result.chunks_created, 1)
        self.assertEqual(plugin.upserts[0]["documents"], ["external parser text"])

    async def test_context_window_uses_parent_child_id_scheme(self):
        engine = LangRAG()
        engine.plugin = RecordingVectorPlugin(
            {
                "doc1_p1_c0": {
                    "id": "doc1_p1_c0",
                    "metadata": {"text": "previous parent"},
                },
                "doc1_p3_c0": {
                    "id": "doc1_p3_c0",
                    "metadata": {"text": "next parent"},
                },
            }
        )
        results = [
            {
                "metadata": {
                    "document_id": "doc1",
                    "index_type": "parent_child",
                    "parent_index": 2,
                }
            }
        ]

        await engine._expand_context(results, "kb1", 1)

        self.assertEqual(set(engine.plugin.requested_ids), {"doc1_p1_c0", "doc1_p3_c0"})
        self.assertEqual(results[0]["metadata"]["context_before"], "previous parent")
        self.assertEqual(results[0]["metadata"]["context_after"], "next parent")

    def test_neighbor_id_supports_all_index_types(self):
        self.assertEqual(
            LangRAG._neighbor_id(
                {"document_id": "doc1", "index_type": "chunk", "chunk_index": 2},
                -1,
            ),
            "doc1_1",
        )
        self.assertEqual(
            LangRAG._neighbor_id(
                {"document_id": "doc1", "index_type": "qa", "chunk_index": "2"},
                1,
            ),
            "doc1_3_qa0",
        )
        self.assertEqual(
            LangRAG._neighbor_id(
                {
                    "document_id": "doc1",
                    "index_type": "parent_child",
                    "parent_index": 2,
                },
                1,
            ),
            "doc1_p3_c0",
        )

    async def test_retrieve_uses_host_rerank_model_with_overfetched_candidates(self):
        engine = LangRAG()
        plugin = RecordingRetrievePlugin()
        await attach_installation_state(plugin)
        engine.plugin = plugin

        response = await engine.retrieve(
            RetrievalContext(
                query="candidate",
                knowledge_base_id="kb1",
                creation_settings={
                    "embedding_model_uuid": "emb1",
                    "index_type": "chunk",
                },
                retrieval_settings={
                    "top_k": 2,
                    "rerank": "rerank_model",
                    "rerank_model_uuid": "rerank1",
                },
            )
        )

        self.assertEqual(plugin.search_top_k, 6)
        self.assertEqual(len(plugin.rerank_documents), 6)
        self.assertEqual(plugin.rerank_top_k, 2)
        self.assertEqual([entry.id for entry in response.results], ["chunk-2", "chunk-0"])
        self.assertEqual(response.results[0].score, 0.95)
        self.assertTrue(response.metadata["trace_id"].startswith("retrieval-"))
        self.assertTrue(response.metadata["trace_spans"])
        self.assertTrue(
            all(span["trace_id"] == response.metadata["trace_id"] for span in response.metadata["trace_spans"])
        )
        self.assertIn("vector_search", {span["name"] for span in response.metadata["trace_spans"]})

        recent = (await plugin.telemetry.snapshot())["recent"]["retrieval"][0]
        self.assertEqual(recent["trace_id"], response.metadata["trace_id"])
        self.assertEqual(recent["trace_spans"], response.metadata["trace_spans"])


class LangRAGFenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_unreadable_fence_store_refuses_mutations_and_recovers(self):
        plugin = ControllableStoragePlugin()
        engine = await bound_engine(plugin)

        plugin.reads_offline = True
        # An unreadable fence store is not "no fence": nothing may be dispatched,
        # and the failure reports the underlying storage error for diagnosis.
        with self.assertRaisesRegex(FenceStateUnavailableError, "fence store offline"):
            await engine.ingest(ingest_context())
        with self.assertRaisesRegex(FenceStateUnavailableError, "fence store offline"):
            await engine.delete_document("kb1", "doc1")
        self.assertEqual(plugin.embeddings, 0)
        self.assertEqual(plugin.upserts, [])
        self.assertEqual(plugin.deletes, [])

        # The failed read was not cached, so the retry proceeds normally.
        plugin.reads_offline = False
        result = await engine.ingest(ingest_context())
        self.assertEqual(result.status, DocumentStatus.COMPLETED)
        self.assertEqual(len(plugin.upserts), 1)
        self.assertTrue(await engine.delete_document("kb1", "doc1"))
        self.assertEqual(len(plugin.deletes), 1)

    async def test_cancelled_delete_fences_the_knowledge_base(self):
        plugin = ControllableStoragePlugin()
        engine = await bound_engine(plugin)

        task = asyncio.create_task(engine.delete_document("kb1", "doc1"))
        await plugin.delete_entered.wait()
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        try:
            # The dispatched delete's outcome is unknown, so no retry may claim
            # deletion while it is still in flight.
            with self.assertRaisesRegex(RuntimeError, "fenced"):
                await engine.delete_document("kb1", "doc1")
        finally:
            plugin.delete_release.set()
            await asyncio.gather(task, return_exceptions=True)

        # The dispatched delete ran exactly once, and the fence is durable: a
        # restarted worker refuses the same knowledge base.
        self.assertEqual(len(plugin.deletes), 1)
        self.assertTrue(any(key.startswith(FENCE_KEY_PREFIX) for key in plugin.data))
        restarted = LangRAG()
        restarted.plugin = plugin
        with self.assertRaisesRegex(RuntimeError, "fenced"):
            await restarted.delete_document("kb1", "doc1")
        self.assertEqual(len(plugin.deletes), 1)

        # The caller never observed a confirmed removal, so no delete record
        # claims one; LangRAG holds no document mapping to mark deleted because
        # the Host vector store is the record of what exists.
        recent = (await plugin.telemetry.snapshot())["recent"]["delete"]
        self.assertNotIn(True, [event.get("deleted") for event in recent])

    async def test_deterministic_validation_error_does_not_fence(self):
        plugin = ControllableStoragePlugin()
        engine = await bound_engine(plugin)

        oversized = await engine.ingest(
            ingest_context(text="x" * (PARSED_TEXT_LIMIT_BYTES + 1))
        )
        self.assertEqual(oversized.status, DocumentStatus.FAILED)
        self.assertEqual(plugin.upserts, [])

        # Rejected before any dispatch: the knowledge base stays usable.
        result = await engine.ingest(ingest_context())
        self.assertEqual(result.status, DocumentStatus.COMPLETED)
        self.assertEqual(len(plugin.upserts), 1)
        self.assertFalse(engine._state.is_fenced(engine._state.binding(plugin), "kb1"))
        self.assertFalse(any(key.startswith(FENCE_KEY_PREFIX) for key in plugin.data))


if __name__ == "__main__":
    unittest.main()
