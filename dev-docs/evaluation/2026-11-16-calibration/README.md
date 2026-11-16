# Real Pipeline calibration on 2026-11-16

This run exercises public LoCoMo questions through installed LangBot plugins,
LocalAgent and the normal Pipeline scheduler on Linux101. Its eight questions
come from one conversation. The run establishes reproducible execution and
identifies implementation and measurement defects. System ranking requires
the broader evaluation described below.

## Source and configuration

The source is LoCoMo by Snap Research, revision
`3eb6f2c585f5e1699204e3c3bdf7adc5c28cb376`. Dataset SHA-256 is
`79fa87e90f04081343b8c8debecb80a9a6842b76a7aa537dc9fdf651ea698ff4`.
The question plan selects two questions per category from conv-26 with seed 42.
Its question-set hash is
`4c40d67265a0144fe3545cc7bca976ded8c1d7c3eb269aa67609d3a9f5fc35ba`.
Embedded dataset excerpts retain the source's CC BY-NC 4.0 license. Questions,
reference answers and dialogue excerpts are reproduced for research evaluation.
The execution traces and judge annotations are generated evaluation artifacts.
[LoCoMo source and license](https://github.com/snap-research/locomo/tree/3eb6f2c585f5e1699204e3c3bdf7adc5c28cb376)

`profile.json` records the shared protocol and source identities.
`pipelines.json` records the four Pipeline configurations. All arms use local
all-MiniLM-L6-v2 384d embeddings, DeepSeek Flash, temperature zero, a 256-token
answer limit, source-only instructions and a 12,000-byte input budget. The byte
budget includes the complete compact-serialized UTF-8 model `messages` list.
Tools, MCP, skills, Box and capture of test questions are disabled.

Core was updated to `b05872e8e1a248b9773503ad56daef27ee5550a3` and overlaid
with the memory integration fix in `476b78a23`. The recorded local patch hash
identifies the running source overlay. Core uses the in-tree SDK 0.7.25.
Installed plugin archive versions and SHA-256 values are retained in the profile.
The original LangRAG arm uses installed 0.2.2. The current source tree contains
subsequent plugin changes, so rebuilding it produces a separate candidate.

The four arms are baseline, LangRAG, LangRAG + LongTermMemory and PowerContext.
The primary comparison is the combined arm against PowerContext. Baseline and
LangRAG provide ablations. Each question receives a fresh Pipeline session.

LangRAG ingested 19 timestamped session files with chunk size 512, overlap 50
and top-k 10. LongTermMemory imported 419 original turns and recalls top-k 3.
PowerContext ingested the same 19 sessions as individual Sources, using the
conversation extraction profile and a flush after each session. It produced
173 active memories, uses search limit 30 and a 9,000-byte plugin context cap.
Both source-only ingestion audits matched original dialogue exactly.

LongTermMemory's raw-episode import exercises its recall/read behavior.
Automatic extraction, candidate review and updates remain a separate write-path
experiment. The source representations and ingestion costs are recorded product
policies. A complete end-to-end memory comparison also needs that write path.

## Observed calibration results

All 32 Pipeline calls completed successfully. Exact real-provider request and
response traces are present for all 32 answers. Each trace satisfies the shared
model, generation settings and input budget. Both memory context and document
RAG context reach the combined arm's actual model input.

| Arm | Strict judge correct | Maximum input bytes | Core LLM input tokens | Core LLM output tokens | Judge input tokens | Judge output tokens |
| --- | --- | --- | --- | --- | --- | --- |
| Baseline | 0/8 | 1,880 | 4,117 | 11 | 989 | 248 |
| LangRAG | 4/8 | 6,780 | 14,274 | 231 | 1,210 | 283 |
| LangRAG + LongTermMemory | 4/8 | 8,654 | 18,346 | 249 | 1,228 | 294 |
| PowerContext | 5/8 | 6,654 | 13,604 | 176 | 1,154 | 263 |

Core usage aggregates the message's Core-side LLM calls. Each question in this
configuration made one answer call. Rewrite, rerank or additional agent calls
would also contribute to that Core total when enabled. Judge usage comes from
the separate judge responses. PowerContext ingestion additionally used 19
generation calls with 154,864 input and 134,157 output tokens. Sequential flush
duration totaled 697.45 seconds. Local embedding usage accounting is incomplete.
Earlier diagnostic calls and failed setup attempts are outside this calibration
cost table. These figures describe measured stages and their coverage.

The combined/PowerContext pairs contain three jointly correct answers, one
combined-only answer, two PowerContext-only answers and two jointly wrong
answers. The conversation-cluster confidence interval is unavailable with one
conversation. `paired-report.json` retains the original judge labels.

Ordered retrieval candidate traces are unavailable for this run. The artifacts
record that absence explicitly. Model-delivery traces establish actual input
delivery. Evidence Hit@k, Recall@k and MRR require original ranked retrieval IDs
and post-budget evidence mappings.

## Measurement defect exposed by q6

`conv-26/q6` asks when Melanie ran a charity race. Gold says
"The sunday before 25 May 2023". Source turn D2:1, dated 25 May, says
"last Saturday". The calendar date is 20 May 2023, a Saturday.

LangRAG and the combined arm answer 20 May and explicitly mention Saturday.
The judge marks both wrong for disagreeing with Sunday. PowerContext answers
"20 May 2023." and receives a true label, with a reason incorrectly calling
that date Sunday. The original labels and all answers remain in the artifacts.
`review-findings.json` records the source/gold conflict and judge inconsistency.
Blinded manual adjudication and a second judge policy are required before
interpreting score differences from this calibration.

## Implementation changes verified

- Core now delivers transient system messages added by PromptPreProcessing
  plugins to LocalAgent through GET_PROMPT. Cached conversation prompts are
  copied before per-turn additions to prevent cross-turn accumulation.
- LongTermMemory performs its authorized recall before suppressing automatic
  retrieval of its memory KB. Frozen explicit retrieval authorization remains
  intact. LocalAgent's automatic document retrieval uses the projected KB list,
  which avoids a second naive memory-KB retrieval.
- LangRAG's fallback text decoder now handles Unicode BOMs and valid UTF-8
  before legacy detection. The original KB contained six encoding-damaged
  chunks out of 185. Public-source replay reproduced all six defects with
  chardet 5.2.0 and preserved all six source texts after the fix. GeneralParsers
  preserved all six in the same replay. The frozen original KB is retained.

`langrag-encoding-audit.json` and `langrag-decoder-replay.json` contain the
source hashes and assertions. Parser re-ingestion uses a separate KB and run
directory, preserving this calibration unchanged.

The re-ingestion environment resolved chardet 7.7.0. Under that version, both
old and fixed decoders preserve all 19 source sessions. Fixed-version replay
with chardet 5.2.0 establishes the parser patch's effect. Re-ingestion verifies
the new index's text integrity. Its QA score also reflects the dependency and
index rebuild, so causal attribution requires the fixed-dependency replay.

The separate re-ingestion run completed eight additional real Pipeline calls.
Its 185 chunks have zero encoding defects and complete source coverage. Their
text multiset matches the original 185 chunks after correcting the six
encoding defects and trimming leading/trailing whitespace. The raw text
multisets differ in 19 chunks, including trailing newlines. Strict QA changed
from 4/8 to 3/8. Question q72 changed from
a correct book title to Unknown, with nine of ten delivered chunks shared by
both runs. Both actual model inputs still contain the book title and the later
reading passage. The observed answer change requires further reader/context
analysis. This follow-up observed improved text integrity and a lower QA score.

The isolated test archive retains version 0.2.2 and has SHA-256
`453a6f60095fc58e9300cd05e390660ca27801eed6d59af2bca15c328ff114c6`.
Its only archive-member change is `parser.py`. The recreated plugin environment
also changed soupsieve 4.1 to 4.1.1. Both test environments resolved chardet
7.7.0 during the follow-up. These identities, ranked delivered-text overlaps,
complete model traces and unchanged judge configuration are retained under
`parser-reingestion/`. All 40 calls across the two runs have verified delivery
traces. Original results and original KBs are retained.

## Linux verification

Run from the repository root on the development host with Core's in-tree SDK.

```sh
.venv/bin/python -m pytest \
  tests/unit_tests/test_preproc.py \
  tests/unit_tests/pipeline/test_prompt_system_context.py \
  tests/unit_tests/plugin/test_handler_actions.py \
  tests/unit_tests/agent/test_automatic_knowledge_selection.py \
  tests/unit_tests/agent/test_orchestrator_integration.py -q -rs

.venv/bin/python -m pytest tests/integration/plugin \
  --required-suite sdk_core -q -rs

python3 -m unittest discover -s tools/tests -p 'test_public*.py' -v

PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m unittest \
  discover -s tools/tests -p 'test_*.py' -q
```

The focused Core run passed 186 tests. The required SDK/Core suite passed all
40 selected tests, with 13 unrelated tests deselected by its suite mechanism.
LangRAG's isolated suite passed 23 tests, including four new decoder regressions.
LocalAgent's 12 affected consumer tests passed against released SDK 0.7.23 and
in-tree SDK 0.7.25. LongTermMemory's eight injection tests passed.
The public evaluation suite passed 50 tests. The complete tools suite passed
251 tests with Core's virtualenv on PATH for subprocesses. Ruff 0.14.14 passed
the full Core/tests/tools lint check and the 826-file source/tools format check. The
plugin catalog check validated all 44 plugins.

## Reproduce artifact analysis

These commands use the committed observations and perform no provider calls.
The acquisition and live-execution commands are in the evaluator README.

```sh
python3 -m tools.evaluation.compare \
  --left dev-docs/evaluation/2026-11-16-calibration/combined-judged.json \
  --right dev-docs/evaluation/2026-11-16-calibration/powercontext-judged.json \
  --output /tmp/calibration-paired.json --seed 42 --bootstrap-samples 2000
```

`artifact-manifest.json` records UTF-8/LF-normalized file hashes and code
identities. The judged files retain complete
model requests, responses, answers and judge decisions. Authentication headers
are absent. The publication review found zero Core API-key and DeepSeek
credential matches.

## Expand the evaluation

1. Freeze a new calibration selection covering all ten LoCoMo conversations.
   Reserve the final question selection before tuning. Record answer policy,
   complete model inputs, failures and separate stage costs for every arm.
2. Add native write-path ingestion for LongTermMemory and measure extraction,
   temporal updates, contradictions and per-user isolation. Continue using the
   combined Pipeline as the primary official-plugin arm.
3. Add ranked retrieval adapters with original source IDs and delivered evidence.
   Run supplied-gold-evidence controls to diagnose retrieval and reader errors.
4. Apply both frozen judge policies and blind-review disagreements. Retain gold
   conflicts in a versioned review file and report original and adjudicated
   metrics with denominators and review coverage.
5. Run the predeclared larger selection, then compare targeted changes such as
   parent-child expansion, hybrid retrieval or reranking on held-out questions.
6. Extend the shared result contract to pinned document QA and Parser datasets.
   HotpotQA or MuSiQue can cover document retrieval. Original OmniDocBench
   documents and official annotations can cover OCR, tables and reading order,
   followed by downstream QA using the same LangRAG pipeline.

The PDF/OCR dataset experiment and the larger multi-conversation integration
run remain pending. The separate PowerContext 90.78% claim still requires its
exact run configuration and artifacts for reproduction. Its LoCoMo Plus
embedding declaration belongs to that dataset profile. The embedding used for
the 90.78% claim remains unverified.
