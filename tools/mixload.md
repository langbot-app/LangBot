# Configurable LangBot mixload (QA only)

This optional mode uses the existing Endurance driver but does not modify
the stock Daily workflow or the fixed Docker acceptance checks. It creates and
cleans a disposable deployment. Do not target a shared or production workspace.
The workload is protocol-level, using real Core, Plugin Runtime, LocalAgent,
SQLite ledger, HTTP Bot, and deterministic local model/embedding interfaces.

## Run

Install the checked-out development dependencies and supply an existing
`lbctl` executable, matching the repository's regression CI guidance. Validate
the effective schedule first (this does not start any services):

```bash
uv run --no-sync python -m tools.regression.profiled_mixload \
  --profile tools/profiles/mixload-smoke.json
uv run --no-sync python -m tools.entrypoints.regression_ci --suite endurance \
  --mixload-profile tools/profiles/mixload-smoke.json --plugins plugins \
  --lbctl /path/to/lbctl --output .qa/mixload-smoke-001
```

For the same runner with real **Host Box** on a disposable Linux executor with
no Docker, use `--box-backend host --plugin-wheelhouse /path/to/wheels` with
`--plugins plugins`. The wheelhouse has to be pre-fetched from the pinned
plugin dependency requirements. Host Box is only for trusted local fixtures;
it is not a sandbox, Docker coverage, or a security boundary. There are no live
model/platform credentials, external endpoints, or shell commands in a mixload
configuration. Use a fresh output directory per run.

| Profile | Planned active load | Purpose |
|---|---:|---|
| `profiles/mixload-smoke.json` | 44 s mixed + 36 s Chat-only | Prove all scenario receipts; prove disabled scenarios do not run in the second phase |
| `profiles/mixload-pressure.json` | 120 s at 1.5 RPS + 240 s at 3 RPS | Compare normal and heavier demand, with an independent cooldown after each phase |
| `profiles/mixload-soak-4h.json` | 14,400 s at 1.5 RPS | Continuous mixed load; this is **not** the Artifact accelerated-TTL/GC workflow |

Customization is configuration-only for known scenarios: use `include` and
`exclude` to select families, global integer `weights`, and optional per-phase
`weights` (zero disables a family in that phase). Configure `duration_seconds`,
`rps`, `workers`, `groups`, `members_per_group`, and `cooldown_seconds`.
`max_requests` limits *offered slots*, not completed requests and not retries.
`min_delivery_ratio` can make missed admissions fail a phase; omit it when
measuring loss under deliberate saturation. `seed` reproducibly orders weighted
families per phase, not deployment IDs or runtime timing. Group count must be a
multiple of the active weight sum, with enough scheduled slots for at least two
turns per group. Each group remains pinned to one scenario; groups are fresh at
phase boundaries, durable throughout a single phase, and do not silently reuse
a different scenario's history after reweighting.

## Business receipts

- `chat`: signed HTTP Bot → LocalAgent → its model stream; each group rotates
  speaking members and verifies consecutive turns, prior group history, final
  reply tokens and exactly one matching terminal RunLedger record.
- `rag_chat`: same external turn pipeline through LangRAG, a pre-indexed
  fixture parsed by GeneralParsers and deterministic embedding; the current
  provider input must contain the retrieved golden document text, not an echo
  of a token from the question or conversation history.
- `box`: two real tool calls write/read a fixture in the actual selected Box
  backend; each group has a distinct, reusable Box identity (Docker hostname
  or Host runtime session ID). Host does not provide Docker container evidence.
- `media_chat`: signed PNG through the group interface and a real native input
  attachment tool read; the model receiver checks the original image bytes.
  This is image input, not outgoing file delivery or external SSE.

Optional **finite companions**, not part of the measured sustained transaction
mix: use the same controller with `--suite state` for RAG replacement/deletion
and monitoring read-back across real Runtime/Core restarts; use `--suite api
--api-seed N` for representative configuration/management chains; use
`--suite smoke` for the stock HTTP/callback/file/Box checks the setup supports.
Coming from a finite companion never qualifies as covered under sustained load.
An independent Plugin Runtime/Box Runtime, local provider stubs and actual
ledger checks are still not live IM vendor delivery, inference quality, or a
production capacity benchmark.

## Interpreting results

At monotonic absolute slots, the schedule offers work to the next group's
assigned scenario. Bounded workers and serialized sessions can cause late or
busy slots to be **not admitted**, never replayed or silently counted as
successful. A lost response that may have been processed is **unknown**, not
retried. Inspect `gate/suite/<phase>/summary.json` for offered/admitted/missed
counts, status, P50/P95/P99, queue tail, per-case counters, successful HTTP
concurrency, and terminal ledger closeout; `gate/mixed.json` is the additional
wire-and-ledger verdict. `gate/suite/workload.json` records the applied
geometry and checkout-local oracle digests. The configured delivery floor is
separate from application correctness. Local rate numbers reflect fixture and
machine conditions; compare only identical backends and workloads.

New repeating transactions belong in the repository-backed catalog, with
an external stimulus and independent provider/ledger/side-effect oracle. JSON
can choose and tune them, but cannot add arbitrary URLs, model payloads, shell
commands or credentials. Restart/cleanup and configuration mutations should
stay in separate finite contracts until made replay-safe and isolated.

### Optional plugin mix with persistent session memory

`tools/profiles/mixload-plugins-smoke.json` opts into the additional
`memory_chat` family. The old four-family profiles do not change. Use a
disposable Chroma-backed test instance and explicitly install the bundled
LongTermMemory fixture in this lane:

```sh
.venv/bin/python -m tools.entrypoints.regression_ci \
  --suite endurance --mixload-profile tools/profiles/mixload-plugins-smoke.json \
  --box-backend host --plugin-wheelhouse /path/to/offline-wheels \
  --plugins plugins --extra-plugins KnowledgeEngine/LongTermMemory \
  --lbctl /path/to/lbctl --output /path/to/new-test-output
```

LocalAgent drives all five families. LangRAG answers via a document that
GeneralParsers parsed during setup; this is a retrieval workload, not
concurrent parser performance. The memory pipeline binds its own
LongTermMemory knowledge base and explicitly scopes discovery to LocalAgent
and LongTermMemory. Turn one writes and recalls a synthetic group-specific
episode; subsequent turns recall the original episode without rewriting it.
The mock validates the current turn's actual tool result, the independent
verifier rechecks wire stages and the Core RunLedger, and each group may
return only its own receipt. Do not infer true model quality, memory
consolidation quality, or parser throughput from this preset.

Specialized checks stay separate: memory correction/expiry/deletion and
runtime reload, GeneralParsers format and degradation cases, AgenticRAG tool
retrieval, and other stateful plugins such as EssentialCommands,
GroupChatSummary, or external PowerContext. Adding a plugin to the install
manifest is not business evidence.
