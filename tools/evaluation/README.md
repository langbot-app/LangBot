# Public memory evaluation

This directory defines the shared scoring boundary for public retrieval and
memory comparisons. It does not change LangBot Core, a KnowledgeEngine, or a
plugin runtime. Each system-specific adapter produces one JSON row per public
question, then `public_memory_metrics` computes the same metrics for every arm.

## Dataset policy

Use a public dataset and record its source URL, revision or commit, SHA-256,
split, question count, and evidence granularity. Recommended first datasets
are LoCoMo for long-term conversation memory, HotpotQA or 2WikiMultihopQA for
multi-document retrieval, and MuSiQue for longer multi-hop chains. Do not copy
the dataset into this repository when its license or size does not allow that.
Keep a download manifest with the exact public URL and checksum.

LoCoMo evidence is commonly annotated at turn level such as `D1:3`. For a
memory comparison, report session-level and exact-turn results separately.
Session-level scoring normalizes `D1:3` to `D1`. It is less strict and matches
the PowerContext benchmark contract. Exact-turn scoring requires the adapter to
preserve turn or chunk IDs.

## Adapter result shape

An adapter should write an object containing a `results` or `queries` array.
Each row should include the question, gold evidence IDs, ranked retrieved IDs,
the generated answer, the reference answer, and complete model usage when an
LLM was called. A minimal row is:

```json
{
  "id": "q1",
  "question": "When did ...?",
  "reference_answer": "...",
  "gold_evidence_ids": ["D1"],
  "retrieved_ids": ["D3", "D1", "D2"],
  "answer": "...",
  "judge": {"correct": true},
  "answer_usage": {"total_tokens": 123}
}
```

`retrieved_hits` or `hits` may be used instead of `retrieved_ids` when each
hit contains `source_id`, `document_id`, `file_id`, or `id`. The scorer keeps
the original ranked order and removes duplicate IDs before calculating metrics.

## Metrics

For each cutoff `k`, the scorer reports hit rate, precision, recall, MRR, and
binary nDCG. When a row contains a generated answer and one or more reference
answers, it also reports answer exact match and token F1. A boolean or
`CORRECT`/`WRONG` judge label is preserved as `judge_correct`. Means are
calculated over every question for retrieval and every answer-bearing row for
answer metrics. Zero-result and failed retrieval rows stay in the retrieval
denominator.

```bash
python -m tools.evaluation.public_memory_metrics \
  --input /path/to/adapter-results.json \
  --output /path/to/retrieval-summary.json \
  --k 1 3 5 10 \
  --granularity session
```

Retrieval scores do not require an external LLM. Answer EM/F1 or an LLM judge
is a separate adapter output and must record the model name, judge policy,
temperature, and token usage. Do not compare judge scores produced by different
policies without labeling the policy.

## Comparison requirements

For a three-arm report, freeze the dataset revision, evidence granularity,
embedding model and dimension, retrieval cutoffs, context byte budget, answer
model, judge policy, and timeout policy. Record each arm's ingestion boundary
because session-level Sources, text chunks, and episodic memories are different
representations. Publish the raw per-question rows alongside the aggregate
summary so a missed evidence item can be audited.

