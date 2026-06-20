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

## Local-Agent RAG Check

After retrieval passes:

1. Open the target pipeline.
2. In `Configuration > AI`, add the knowledge base to `Knowledge Bases`.
3. Save.
4. Open `Debug Chat`.
5. Ask for the sentinel.
6. Confirm the bot response contains the exact sentinel.
