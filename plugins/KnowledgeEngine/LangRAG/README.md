# LangRAG

RAG (Retrieval-Augmented Generation) Engine plugin for LangBot.

Source: [KnowledgeEngine/LangRAG](https://github.com/langbot-app/LangBot/tree/master/plugins/KnowledgeEngine/LangRAG). Run the commands below from this plugin directory.

This plugin demonstrates how to build a Knowledge Engine that handles document ingestion and vector retrieval using LangBot Host's built-in infrastructure (Embedding models and Vector Database).

## Features

- **External Parser Integration** - Prefers pre-parsed content from a Parser plugin such as GeneralParsers, including structured sections and document metadata
- **Fallback Internal Parsing** - Includes a built-in parser as a fallback when no external parser is configured
- **Multiple Index Strategies** - Flat chunking, parent-child chunking, LLM-generated Q&A pairs
- **Flexible Retrieval** - Vector, full-text, or hybrid search
- **Query Rewriting** - HyDE, Multi-Query, Step-Back strategies for improved recall
- **Configurable Chunking** - Recursive character splitting with custom chunk size and overlap
- **Section-aware Chunking** - When structured sections are available, chunking preserves headings, page information, and table boundaries
- **Context Expansion** - Optionally appends adjacent chunks around each hit for richer retrieval context
- **Document Management** - Delete indexed vectors by document

## Architecture

```
┌─────────────────────────────────┐
│         LangBot Core            │
│  (Embedding / VDB / Storage)    │
└──────────┬──────────────────────┘
           │ RPC (IPC)
┌──────────▼──────────────────────┐
│          LangRAG                │
│  ┌───────────────────────────┐  │
│  │    Knowledge Engine       │  │
│  │  Parse → Chunk → Embed   │  │
│  │      → Store / Search    │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

## Ingestion Flow

LangRAG now prefers parser output provided by LangBot Host:

1. LangBot reads the uploaded file
2. A Parser plugin such as GeneralParsers extracts `text`, `sections`, and `metadata`
3. LangRAG ingests that structured result directly
4. If no parser output is available, LangRAG falls back to its internal parser
5. The selected index strategy builds chunks / Q&A pairs
6. LangBot Host generates embeddings and stores vectors

This means LangRAG works best when paired with an external parser plugin.

Parsed-input admission is capped at **4 MiB of UTF-8 bytes**, inclusive: both
flat text and the aggregate content of all sections must independently fit this
budget. These alternative representations are not added together. The check runs
after parsing, before any strategy chunking/offload, LLM, embedding, or vector
work, for `chunk`, `parent_child`, and `qa`. Over-budget ingestion returns a failed
result without processing partial sections. This is an input-content limit, not
a bound on generated Q&A, metadata, or total runtime memory.

## Document Deletion

Deletion confirms success only after Host `vector_delete` returns a nonnegative
integer count. Zero is a successful no-op: a document may have no chunks, or its
vectors may already have been deleted before a failed Host file-record commit.
Errors, missing acknowledgements, and malformed counts are not proof of absence;
they propagate and fence further mutations until reconciliation. This does not
make vector deletion and Host file-record deletion one atomic transaction.

## Configuration

### Knowledge Base Creation

| Parameter | Description | Default |
|-----------|-------------|---------|
| `embedding_model_uuid` | Embedding model | Required |
| `index_type` | Index strategy: `chunk`, `parent_child`, or `qa` | `chunk` |
| `chunk_size` | Characters per chunk | 512 |
| `overlap` | Overlap between chunks | 50 |
| `parent_chunk_size` | Parent chunk size (parent_child only) | 2048 |
| `child_chunk_size` | Child chunk size (parent_child only) | 256 |
| `qa_llm_model_uuid` | LLM for Q&A generation (qa only) | - |
| `questions_per_chunk` | Questions to generate per chunk (qa only) | 1 |

### Retrieval

| Parameter | Description | Default |
|-----------|-------------|---------|
| `top_k` | Number of results to return | 5 |
| `search_type` | Search mode: `vector`, `full_text`, or `hybrid` | `vector` |
| `query_rewrite` | Rewrite strategy: `off`, `hyde`, `multi_query`, or `step_back` | `off` |
| `rewrite_llm_model_uuid` | LLM for query rewriting (when rewrite is enabled) | - |
| `rerank` | Reranking strategy: `off`, `rerank_model`, or `llm` | `off` |
| `rerank_model_uuid` | LangBot rerank model for candidate reranking | - |
| `rerank_llm_model_uuid` | LLM for reranking (legacy LLM mode) | - |
| `context_window` | Number of adjacent chunks to append around each hit | 0 |

## Index Strategies

- **chunk** - Default flat chunking. Splits documents into fixed-size chunks and embeds each directly. When parser sections are available, chunks are created section-by-section instead of flattening the whole document.
- **parent_child** - Two-level chunking. Splits into large parent chunks, then smaller child chunks. Embeds child chunks but returns parent text for richer context. When parser sections are available, sections are used as natural parent boundaries.
- **qa** - LLM-generated Q&A pairs. Chunks text, uses an LLM to generate question-answer pairs per chunk, and embeds the questions. When parser sections are available, Q&A generation also becomes section-aware.

## Query Rewriting

- **hyde** - Hypothetical Document Embedding. Generates a hypothetical answer to the query, then embeds that answer for retrieval.
- **multi_query** - Generates 3 query variants, searches with each, and merges results by score.
- **step_back** - Generates a more abstract question and searches with both the original and abstract queries.

## Pairing With GeneralParsers

GeneralParsers is currently the recommended parser for LangRAG because it can provide:

- cleaner PDF extraction
- structured sections
- table-preserving text
- document-level metadata
- optional OCR and image descriptions via a vision model

LangRAG consumes those parser outputs directly during ingestion, which generally produces better chunks and better retrieval quality than the fallback parser.

## Observability Page

LangRAG includes a WebUI Page named **Observability**. It shows recent ingest,
retrieval, delete, and embedding events, plus production-oriented diagnostics:

- 1m / 5m / 1h operation windows, rates, error rates, and zero-result rates
- latency averages plus p50 / p95 / p99 / max values
- ingest and retrieval stage timings, including parser, chunking, embedding,
  vector search, rerank, context expansion, and vector upsert stages
- retrieval quality signals such as zero-result rate, Top-K fill rate, reference
  coverage, rerank usage, and filtered-query rate
- active alerts for high error rate, retrieval zero results, high p95 latency,
  and persistence problems
- privacy-conscious event data: query text is not stored; query, document, and
  collection identifiers are represented with hashes where possible

Recent diagnostics are stored through the SDK's installation-scoped plugin
storage and survive plugin restarts. The retained history is bounded to 100
events and 192 KiB; it is diagnostic history, not an accounting ledger.
This version does not load the old local JSONL history or honor
`LANGRAG_OBSERVABILITY_DIR`. Knowledge documents and vectors are unaffected.

The Page backend also exposes `/snapshot`, `/export`, `/clear`, and `/metrics`
through the LangBot Page API. `/metrics` returns Prometheus text format so the
data can be bridged into an external monitoring stack.

## Development

```bash
pip install -r requirements.txt
cp .env.example .env
```

Configure `DEBUG_RUNTIME_WS_URL` and `PLUGIN_DEBUG_KEY` in `.env`, then launch with your IDE debugger.

### Testing

```bash
python3 -m unittest discover -s tests
```

### Offline Benchmarks

```bash
python3 -m benchmarks.run
```

Benchmark datasets, experiment configs, deterministic local adapters, and metric
code are stored in `benchmarks/`. Runs write traceable `results.json` files under
`benchmarks/runs/`.

Parser integration can be benchmarked against `misc/GeneralParsers` in this repository:

```bash
python3 -m benchmarks.run \
  --dataset benchmarks/datasets/parser_compare_zh.json \
  --config benchmarks/configs/parser_compare.json
```

Harder multi-hop retrieval cases are also available:

```bash
python3 -m benchmarks.run \
  --dataset benchmarks/datasets/hard_multihop_zh.json \
  --config benchmarks/configs/hard_retrieval.json
```

## Links

- [LangBot Documentation](https://langbot.app/docs/)

## Contributing

We welcome contributions! Feel free to:

- Submit issues for bugs or feature requests
- Fork the repo and submit pull requests
- Improve documentation or add examples
- Share your ideas and feedback

Star the repo if you find it useful!

## Runtime placement

This version remains dedicated. SDK 0.7.4 shared singleton placement requires a
signed `stateless-v1` component model, not just `shared-runtime-v1`.
The existing per-installation mutation state and cancellation model have
not passed that contract. See [the audit](../SHARED_RUNTIME.md).
