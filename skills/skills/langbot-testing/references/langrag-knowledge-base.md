# LangRAG Knowledge Base

Use this reference when validating LangRAG creation, document ingestion, retrieval, and local-agent RAG behavior.

## Setup

1. Install `langbot-team/LangRAG` from Marketplace if `/api/v1/knowledge/engines` has no LangRAG engine.
2. Confirm `LANGBOT_BACKEND_URL/api/v1/knowledge/engines` contains plugin id `langbot-team/LangRAG`.
3. Prefer local Chroma embedding for offline/free tests:
   - Provider requester: `chroma-embedding`
   - Embedding model name: `chroma-all-MiniLM-L6-v2`

Important: a Chroma embedding entry must exist under `embedding_models`. A model accidentally created as an LLM model will appear in the wrong model selector and will not satisfy LangRAG's embedding-model field.

## Parser Golden Case

Use `cases/langrag-parser-golden-e2e.yaml` when validating the LangRAG + GeneralParsers integration on the current master worktree.

Fixture:

```text
fixtures/rag/parser-golden.html
```

Golden intent:

- Start LangBot from `LANGBOT_REPO`, which should point at the master worktree for this run.
- Build and install/update local `LANGBOT_RAG_PLUGIN_REPO` and `LANGBOT_PARSER_PLUGIN_REPO`.
- Upload the HTML fixture and select GeneralParsers when the parser chooser is shown.
- Confirm retrieval returns `aurora-parser-rag-9137`, `GeneralParsers`, `LangRAG`, and the Markdown table header `| Parser field | Golden value |`.
- Confirm logs show LangRAG used external pre-parsed content instead of the internal fallback parser.

Local install pitfall:

- If GeneralParsers fails while installing `PyMuPDF>=1.24.0`, read `troubleshooting/plugin-dependency-install-offline.yaml`.
- The golden case can continue after the active LangBot master venv can `import fitz` and `python -m pip install --dry-run 'PyMuPDF>=1.24.0'` reports the requirement is satisfied.

## Browser Flow

1. Open `LANGBOT_FRONTEND_URL`.
2. Navigate to `Knowledge`.
3. Create a knowledge base.
4. Select engine `LangRAG`.
5. Select embedding model `chroma-all-MiniLM-L6-v2` or another known working embedding model.
6. Keep the index type as `Chunk` for smoke/regression tests.
7. Upload a small sentinel document.
8. Wait until the document row status is `Completed`.
9. Open `Retrieve Test` and query for the sentinel.

Recommended fixture:

```text
fixtures/rag/sentinel-doc.txt
```

## Pass Criteria

- The created knowledge base appears in the sidebar.
- The uploaded document reaches `Completed`.
- Retrieve Test returns the uploaded document with the sentinel text.
- Browser console has no unexpected errors.

## Document Lifecycle Acceptance

- Keep the public Host file UUID from upload/listing when calling file deletion. Core stores the engine-returned `document_id` separately in the server-owned `engine_document_id` column and sends it to the engine; do not overwrite the Host UUID or put this mapping in creation settings.
- Wait for the ingestion task to finish before deletion. Pending/processing files reject deletion to avoid losing the tracking row while an upstream document is still being created.
- Verify both the Host file-list readback and absence of the sentinel upstream. Core only removes its row after an explicit engine `True`; `False`, missing configuration, runtime errors, and unconfirmed absence remain failures with the row retained. A connector's `False` is not proof that the upstream document is absent.
- Failed ingestion with an acknowledged engine ID retains it for cleanup. Historical failed files with no mapping still use the Host UUID fallback, subject to confirmed deletion. New unacknowledged/malformed responses are `interrupted`, not confirmed failures.
- `interrupted` means Core cannot establish the remote ingestion outcome (cancellation, disconnect, timeout, lost acknowledgement, or abandoned pending/processing work). It is not proof of failure, successful ingestion, or remote quiescence. Core preserves the tracking row, any known engine ID, and its source upload; retention cleanup also protects pending/processing/interrupted uploads.
- Runtime loading and normal file listing recover abandoned rows to `interrupted`. Reloading a KB object must preserve genuinely live tasks. Delayed old tasks cannot replay interrupted rows or overwrite them with completion; an observed late engine ID is still retained.
- File deletion and whole-KB deletion reject interrupted work with operator guidance. Do not bypass this guard merely because the task list is empty or the Host restarted: the old SDK/plugin action may still write. There is deliberately no automatic retry, force-delete, or claim of a remote cancellation fence.
- Recovery procedure: preserve a DB/storage backup; identify the exact Workspace, KB, Host file UUID, engine ID (if known), and installation; inspect that plugin/upstream operation; establish that the old operation has stopped or settled; then have an operator reconcile the confirmed upstream outcome and exact mapping before cleanup or re-upload. Never invent an opaque upstream ID or blindly set `failed` to unlock deletion. Lost historical uploads/IDs cannot be reconstructed by this change. Automatic cleanup of arbitrary connector orphans is outside this recovery contract.
- SDK ingest/delete action signatures and envelopes are unchanged; old SDKs use the same conservative interrupted fallback. Existing acknowledged asynchronous-engine responses retain the legacy Host completion semantics (Host ingestion acknowledgement, not a guarantee that the upstream index is ready).
- Migration `0025_rag_document_identity` leaves historical mappings null: it cannot reconstruct IDs previously discarded, nor restore already-deleted Host rows. Those require separately authorized investigation/recovery. Downgrading removes the mapping column and loses these identities; back up before rollback.

## Local-Agent RAG Check

After retrieval passes:

1. Open the target pipeline.
2. In `Configuration > AI`, add the knowledge base to `Knowledge Bases`.
3. Save.
4. Open `Debug Chat`.
5. Ask for the sentinel.
6. Confirm the bot response contains the exact sentinel.
