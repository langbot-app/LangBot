# LangRAG Offline Benchmarks

This directory contains a reproducible retrieval benchmark harness for LangRAG.
It does not start LangBot and does not require external model services.

## Purpose

These benchmarks are intended to help iterate LangRAG with controlled,
repeatable comparisons. Use them to check whether a code or configuration
change improves retrieval behavior under the same dataset and runtime
conditions.

They are especially useful for:

- catching retrieval regressions before release
- comparing chunking, parent-child, QA index, rewrite, rerank, and hybrid settings
- comparing LangRAG's fallback parser with the external GeneralParsers plugin
- exposing multi-hop failures where one relevant document is retrieved but not
  all required evidence is found
- tracking cost and performance signals such as chunk count, vector count,
  embedding calls, LLM calls, and latency

They are not intended to produce an absolute production quality score. Real
deployment quality still depends on the actual embedding model, vector store,
parser configuration, document corpus, and user query distribution. For
production decisions, run the same benchmark shape with representative data and
the real provider stack.

## Run

```bash
python3 -m benchmarks.run
```

The default run uses:

- dataset: `benchmarks/datasets/mini_zh.json`
- config: `benchmarks/configs/local_retrieval.json`
- output: `benchmarks/runs/<run_id>/results.json`

You can pin a run ID for exact comparisons:

```bash
python3 -m benchmarks.run --run-id local-dev
```

To compare LangRAG's fallback parser with the external GeneralParsers plugin:

```bash
python3 -m benchmarks.run \
  --dataset benchmarks/datasets/parser_compare_zh.json \
  --config benchmarks/configs/parser_compare.json \
  --run-id parser-compare-local
```

The parser directory defaults to `misc/GeneralParsers` in this repository. Override it with
`--parser-repo /path/to/GeneralParsers` or the `LANGBOT_PARSER_REPO`
environment variable.

The bundled parser comparison dataset uses raw HTML so it can run in a minimal
Python environment. PDF, DOCX, Markdown, and vision/OCR parser benchmarks can be
added as separate datasets once those parser dependencies and representative
files are available.

To run the harder multi-hop / distractor retrieval set:

```bash
python3 -m benchmarks.run \
  --dataset benchmarks/datasets/hard_multihop_zh.json \
  --config benchmarks/configs/hard_retrieval.json \
  --run-id hard-local
```

## What It Measures

The runner evaluates document-level retrieval quality:

- `hit@k`: whether any relevant document appears in the top `k`
- `all_relevant@k`: whether all relevant documents appear in the top `k`
- `precision@k`: relevant retrieved documents divided by `k`
- `recall@k`: relevant retrieved documents divided by all relevant documents
- `mrr@k`: reciprocal rank of the first relevant document
- `ndcg@k`: binary relevance ranking quality

Parser comparison datasets can also include `relevant_headings`, which enables
`heading_hit@k` to measure whether retrieved chunks carry the expected
section heading metadata.

It also records operational counters:

- chunks created
- vectors stored
- vectors with `heading_path`
- parsed section count
- embedding calls
- LLM calls
- parser time
- ingestion and retrieval wall-clock seconds

## Reproducibility

The local runtime in `benchmarks/local_runtime.py` provides deterministic
substitutes for Host capabilities:

- hashing-vector embeddings
- in-memory vector/full-text/hybrid search
- simple deterministic LLM responses for QA, query rewriting, and reranking

Every `results.json` includes:

- dataset path and SHA-256
- config path and SHA-256
- git commit and dirty flag
- Python and platform information
- per-query retrieved document order and metrics

This makes runs comparable without depending on LangBot, a vector database, or
remote LLM/provider state.

## Realism

The harness executes LangRAG's real ingestion and retrieval code, including the
selected chunk/index/rewrite/rerank paths. The Host side is intentionally
simulated with deterministic local adapters, so these results are best treated
as regression and relative-comparison signals. They are not a replacement for
production evaluation with the actual embedding model, vector database, parser
configuration, and representative user queries.

## Hard Dataset Design

`benchmarks/datasets/hard_multihop_zh.json` follows common retrieval benchmark
patterns used by multi-hop and heterogeneous IR datasets such as HotpotQA,
BEIR, and MIRACL: questions may require two supporting documents, include
comparison/constraint wording, and sit among near-duplicate distractors. For
these cases `all_relevant@k` is more informative than `hit@k`, because
retrieving only one of two gold documents is insufficient for the downstream
answer.
