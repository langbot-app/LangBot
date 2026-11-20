# LangBot retrieval benchmark with public BEIR SciFact

This suite uploads published scientific abstracts via Core's Artifact API and
indexes them through GeneralParsers and LangRAG. Test claims go through Core's
real knowledge retrieval API and persistent local Chroma. Real local CPU
embeddings use all-MiniLM-L6-v2 ONNX (384 dimensions, input cap of 256 word
pieces, attention-mask mean pooling and L2 normalization). The embedding
endpoint is loopback OpenAI-compatible HTTP. No external inference or mock
embedding vectors are used. The benchmark makes no claim about generated
answers, reranking, or hybrid search.

## Sources and reproducible inputs

- [BEIR SciFact dataset card](https://huggingface.co/datasets/BeIR/scifact)
  (CC BY-SA 4.0); original [SciFact project by AI2](https://github.com/allenai/scifact).
  Download the [official BEIR archive](https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip).
  Its MD5 equals `5f7d1de60b170fc8027bb7898e2efca1` as published by BEIR.
- [Sentence Transformers all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/1110a243fdf4706b3f48f1d95db1a4f5529b4d41)
  (Apache 2.0), pinned to revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.
  The upstream Git LFS OID also confirms the ONNX SHA-256.

## Setup and run

Run from the repository root in a disposable Linux checkout with a matching
plugin wheelhouse. Keep downloads, model weights, collected traces and timing
outside the checkout. The launcher rejects cache and output paths under the
checkout. Bootstrap once:

```bash
uv sync --locked --dev
uv pip install 'onnxruntime==1.23.2' 'pyarrow==19.0.1'
QA_ROOT=$(mktemp -d)
mkdir -p "$QA_ROOT/wheels"
grep -h -v '^langbot-plugin[<>=~!]' \
  plugins/Runner/LocalAgent/requirements.txt \
  plugins/KnowledgeEngine/LangRAG/requirements.txt \
  plugins/misc/GeneralParsers/requirements.txt > "$QA_ROOT/wheel-inputs.txt"
python -m pip download --only-binary=:all: \
  -r "$QA_ROOT/wheel-inputs.txt" -d "$QA_ROOT/wheels"
```

Use a system Python with pip whose platform and minor Python version match
the project virtual environment for wheel downloads. The launcher records
wheelhouse and plugin archive hashes and the installed dependency versions.
Use the same wheelhouse across repeated trials. `pyarrow` is only needed for
the WikiText RSS suite; `onnxruntime` is only needed for SciFact.

```bash
uv run --no-sync python -m tools.entrypoints.vdb_benchmark_local --suite scifact \
  --profile tools/profiles/vdb-public-scifact-smoke.json \
  --plugin-wheelhouse "$QA_ROOT/wheels" --output "$QA_ROOT/scifact-smoke"
```

The launcher downloads the pinned source archive, model and tokenizer on
first use into `~/.cache/langbot/public-rag` (override with `--asset-cache`).
Subsequent runs reuse only verified cache files and can run without network
after the wheelhouse is prepared. Invalid existing cache files are rejected,
not overwritten; remove the rejected file before retrying. Data/MiniLM
downloads occur before the transient Core and Runtime start. Those workers
use local resources only.

The three assets must match the pinned SHA-256 hashes embedded in the launcher before benchmarking. The output source manifest records those hashes and URLs. Do not run another resource-heavy job
on the host during timing. Change the output directory per trial; a profile
deterministically reconstructs the same workload and writes incremental
ingestion and query receipts. Interrupted results are retained but must not
be compared to complete runs; reruns start from a fresh knowledge base rather
than combining data across independent processes.

## Profiles and methods

| Profile | Corpus | Official test queries used | Status |
|---|---:|---:|---|
| smoke | 48 | 20 | Debugging integration |
| moderate | 120 | 60 | Repeatable subset baseline |
| canonical | **5,183** | **300** | Full corpus/test-query profile |

The corpus contains the original title and abstract from each selected
document, with only a blank separator inserted. Subset profiles choose test
queries by fixed seed, require all their relevant documents, then fill the
remaining corpus slots with seeded random distractors. That conditions the
corpus on the chosen qrels; these numbers must **not** be compared to
published full-corpus BEIR scores. The full profile can need a much larger
`--trial-timeout` (e.g. 3600 seconds) due to real upload/index/cleanup. No
retrieval quality is emitted if ingestion cannot be confirmed for the entire
planned corpus, or if any test query fails.

The API returns up to 10 chunks per query. The scorer maps each chunk's engine
file ID to the confirmed original SciFact document ID, then deduplicates in
rank order without fetching extra chunks. Macro document Recall@10 and
nDCG@10 therefore measure document coverage of the **actual API top-10
chunks**, not a backend-native search over 10 unique documents. The confirmed
ingestion manifests and independently counted committed Chroma vectors are
kept together; record counts are not HNSW graph node counts. Warmup claims use
only non-test IDs and never enter scoring or latency summaries.

`summary.json` gives HTTP p50/p95/p99/max and measured throughput; this
includes Core, the plugin runtime, the Chroma backend, and local CPU
embedding. Indexing latency includes observing terminal async tasks. The
test-request sample count is recorded explicitly; short-run p99 is not a
production SLO. Per-document/time and ranked document IDs are recorded in
`ingest.jsonl` and `queries.jsonl`; configuration, source URLs, hashes, seed,
selected IDs, and selected qrels are in `manifest.json`. This suite does not
bundle the corpus or publish source texts. To investigate Core RSS size of
large, representative files use the separate
[upload/RAG memory suite](vdb-benchmark-memory.md); short SciFact abstracts
are not a large-upload capacity claim.
