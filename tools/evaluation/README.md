# Public evaluation

Run public questions through installed LangBot plugins and the normal Pipeline
scheduler. Retain exact model inputs, answers, usage, judge labels, configuration
and the question plan so reported results can be reproduced and inspected.

The first real Pipeline calibration includes raw observations, source audits
and a separate parser re-ingestion experiment.
[Calibration artifacts](../../dev-docs/evaluation/2026-11-16-calibration/README.md)

## Evaluation arms

The primary integration comparison uses LangRAG + LongTermMemory in one Pipeline
and the PowerContext EventListener in another. Both use LocalAgent and the same
answer model. Add a context-free baseline and individual-plugin ablations to
diagnose contributions. Explicit extension allowlists scope each arm to its
intended plugins. PowerContext is an EventListener. LocalAgent is the Runner.

Use dedicated test resources. Ingest public history before asking questions and
disable capture/extraction of evaluation questions and answers. `pipeline.run`
creates a fresh session per question. LongTermMemory's imported `user_key` must
match the test bot identity and isolation configuration. PowerContext scopes
must resolve to the matching conversation. Distinct session names alone do not
isolate a bot-scoped store.

## Prepare the public question plan

Download `data/locomo10.json` from the source commit in
[the manifest](datasets/locomo10.manifest.json). Preparation verifies SHA-256.
This input profile uses text-only dialogue, Source dates and turn IDs. Images
and dataset summaries are outside the profile.

LoCoMo data is supplied under CC BY-NC 4.0. Retain its attribution and license
when sharing dataset excerpts or model inputs containing those excerpts.

```sh
python3 -m tools.evaluation.locomo \
  --dataset /path/locomo10.json --output /path/calibration-plan \
  --conversation-limit 1 --per-category 2 --seed 42
```

This selects two questions per available category from the first conversation.
Remove both selection arguments for all 1,540 category 1–4 questions. Select
before inspecting outputs. Category 1 is multi-hop, 2 temporal, 3 open-domain
and 4 single-hop.

`sources.jsonl` contains only history. Keep `plan.json`, which includes QA gold,
outside ingestion. Use a separate calibration selection when tuning and a
predeclared final selection for reporting quality. Disclose any reuse of observed
answers for tuning.

## Provision and freeze the experiment

Use `lbctl` or Application Operations for Providers, models, KBs, permissions and
Pipelines. Inspect installed operation schemas first. See
[the operations skill](../../skills/skills/langbot-mcp-ops/SKILL.md).
The runner executes existing configured Pipelines.

Copy [the profile example](profiles/pipeline.example.json). Record running Core
SHA and local patch, SDK source/version, plugin archive hashes, model version,
embedding dimension, vector backend, parser, chunking, extraction, retrieval,
prompts and source-ingestion policy. Arm-specific details belong in each arm.
Importing raw episodes evaluates recall/read behavior. Automatic extraction and
review from live dialogue requires a separate write-path experiment.

The reference configuration uses local MiniLM-L6-v2 384d and DeepSeek Flash for
answering and judging, with temperature zero. A common budget is an upper bound.
Record each system's candidate count and actual delivered input, since a chunk,
extracted fact and whole session carry different amounts of information.

The integration budget measures the complete JSON `messages` list in UTF-8,
serialized with `ensure_ascii=False` and compact separators. It includes static
instructions and event metadata. Configure retrieval to fit this bound and verify
it at the model boundary. The runner records declared configuration. The trace
step checks observed model names and bytes. A budget violation invalidates the
protocol comparison and requires a new declared configuration.

## Record real model delivery

Point a dedicated test Provider at `http://127.0.0.1:8770/v1`. Supply the real
upstream key through the proxy process environment.

```sh
python3 -m tools.evaluation.recording_proxy \
  --port 8770 --upstream https://api.deepseek.com/v1 \
  --key-env DEEPSEEK_API_KEY --record /path/model-requests.jsonl

python3 -m tools.evaluation.pipeline \
  --plan /path/calibration-plan/plan.json --profile /path/profile.json \
  --output /path/run --api-key-env LANGBOT_API_KEY
```

The loopback proxy preserves real streaming and records requests, response
content, completion status and provider usage without retrying. Authentication
headers are omitted and its upstream key is redacted. Use public test data and
review private-by-default artifacts before publication.

Each Pipeline submission is checkpointed before execution. A timeout or unknown
execution is retained and stops the runner. Reconcile its query and submission
time against monitoring before resuming. Inspect the process before removing a
stale lock. Completed rows resume without resubmission. The manifest rejects
Pipeline/configuration and question-plan changes.

```sh
python3 -m tools.evaluation.traces \
  --input /path/run/langrag_memory.json --record /path/model-requests.jsonl \
  --output /path/langrag-memory-traced.json
```

Repeat per arm. Correlation uses the exact current input and execution time
window, including LocalAgent's multipart event envelope. Inspect that expected
RAG and memory blocks occur in actual requests, with no other question's history.
Delivery correlation alone cannot establish evidence recall. Retrieval adapters
must retain original candidate IDs and post-budget delivered evidence separately.
Unavailable retrieval traces are counted explicitly.

## Judge and compare

The judge sees the question, reference and generated answer after generation.
Its instruction, endpoint, model and decoding settings are frozen on resume.
`strict-v1` requires the requested facts and rejects answer-changing additions.
`topical-v1` permits broader topical equivalence. Report them separately.

```sh
python3 -m tools.evaluation.judge \
  --input /path/langrag-memory-traced.json --output /path/langrag-memory-judged.json \
  --base-url https://api.deepseek.com/v1 --api-key-env DEEPSEEK_API_KEY

python3 -m tools.evaluation.compare \
  --left /path/langrag-memory-judged.json --right /path/powercontext-judged.json \
  --output /path/paired-report.json --seed 42 --bootstrap-samples 2000
```

Comparison requires the same complete question plan, references, protocol,
models, judge, input budget and execution layer. Pipeline successes require
verified model traces. Explicit failures remain zero-scored. Unknown executions
require reconciliation. Reports include paired wins/losses and a seeded
conversation-cluster bootstrap interval. LoCoMo's ten conversations limit interval
precision and generalization. A small calibration score cannot establish ranking.

The comparator recomputes validation from raw request/response records, question
plan contents and the judge source hash. Both arms must carry the same frozen
judge identity. The canonical plan fields are `id`, `sample_id`, `question`,
`category`, `category_name`, `reference_answer` and `gold_evidence`. Dataset
adapters populate those fields before hashing. A one-conversation run reports
an unavailable confidence interval.

Blindly human-review sampled disagreements and judge decisions. Report latency,
errors and delivered bytes alongside accuracy. Account for ingestion, extraction,
rewrite, rerank, answer, judge and failed attempts separately. Missing usage stays
unknown. Publish reviewed raw outputs, configs, source manifests and code identity
with each result.

## Scorer v2 and legacy results

```sh
python3 -m tools.evaluation.public_memory_metrics \
  --input /path/adapter-results.json --output /path/metrics.json \
  --k 1 3 5 10 20 --granularity session
```

Rows contain stable `id`, `sample_id`, `reference_answer`, `answer`, `judge`,
`gold_evidence_ids` and ordered `retrieved_hits`. Each hit supplies `source_id`
or `source_ids`. A multi-source hit stays at one rank. Preserve duplicate and
unmapped items before cutoff. LoCoMo compound annotations and the `D:11:26` typo
are normalized. Missing gold and the unresolvable standalone `D` have an explicit
unscorable evidence count. All reference-bearing questions remain in answer
metric denominators.

v2 fixes multiset Token F1, missing-answer handling and source-rank cutoffs.
Retain v1 aggregates and regenerate v2 from original ranked rows. Previously
deduplicated exports cannot reconstruct original ranks. Legacy independent-system
results retain diagnostic value. Their absent shared manifests and model-delivery
traces leave integration comparability unverified.

## Extend coverage and improve implementations

For document RAG, add a pinned HotpotQA or MuSiQue selection with declared corpus
scope and the same result contract. Run retrieved-context and supplied-gold-evidence
controls to distinguish retrieval and reader failures. LoCoMo open-domain questions
need an explicit source-only or general-knowledge answer policy.

For Parser comparisons, pin original files and public structure/OCR ground truth,
such as a declared OmniDocBench split. Retain page/block IDs, reading order,
tables, OCR and parser cost. Feed each parser output into identical LangRAG
retrieval and downstream QA. Report official parser metrics and downstream QA
separately. PDF/OCR quality requires original documents and their annotations.

Use failures to select one implementation change at a time. Compare LangRAG
chunking, hybrid retrieval, parent-child expansion and reranking. Check memory
extraction completeness, dates, conflicts, updates and isolation. Preserve
citations so memories can be traced to original facts.

Published vendor accuracy belongs to its recorded model, judge and answer policy.
Reproducing a vendor score requires that exact run configuration and artifacts.
PowerContext declares `qwen3.7-text-embedding` in its LoCoMo Plus section.
The embedding used for its separate 90.78% LoCoMo claim remains unverified.

## Linux checks

```sh
python3 -m unittest discover -s tools/tests -p 'test_public*.py' -v
```
