# AgenticRAG

AgenticRAG exposes the knowledge bases configured for the current pipeline as an LLM Tool, so an agent can inspect available KBs and retrieve relevant chunks on demand.

## What It Does

- Provides a single tool, `query_knowledge`
- Supports two actions:
  - `list`: list knowledge bases available to the current pipeline
  - `query`: retrieve relevant documents from one or more selected knowledge bases
- Returns retrieval results as JSON so the agent can continue reasoning over them

## Overall Design

AgenticRAG is intentionally not a new RAG backend. It is a control-layer plugin that changes **who decides when retrieval should happen**.

Instead of the runner always injecting knowledge automatically before the model responds, AgenticRAG shifts retrieval into the agent loop:

- the model first decides whether retrieval is needed
- the model can inspect available knowledge bases
- the model can choose one KB or query several in parallel
- retrieval only happens when the model explicitly asks for it

This design exists to solve a specific problem: naive always-on retrieval is simple, but it also introduces noise, wasted context, and irrelevant chunks for many turns.

## Design

This plugin is intentionally thin. It does not implement a new RAG backend. Instead, it wraps LangBot's built-in query-scoped knowledge retrieval APIs:

- `list_pipeline_knowledge_bases()` for enumerating KBs visible to the current query
- `retrieve_knowledge()` for retrieving top-k entries from one or more selected KBs

The `query_id` is injected by the runtime when the tool is called, then stored inside `QueryBasedAPIProxy`. Because of that, the tool code only needs to pass business parameters such as `kb_id` or `kb_ids`, `query_text`, and `top_k`.

Although the underlying runtime can support metadata filters, this plugin does not expose raw filters to the agent in the current agentic tool flow. Different knowledge engines and vector backends may use different metadata fields, value formats, and filter semantics, and the agent currently has no reliable schema source for those fields.

Future versions may expose metadata filtering after the ecosystem has a more unified way to describe filterable fields and operators for each knowledge base.

## How It Works

An AgenticRAG request has four main stages:

### 1. Disable naive retrieval

During `PromptPreProcessing`, the plugin checks whether the active LLM supports tool calling.

- if tool calling is supported, it clears the runner's `_knowledge_base_uuids` so the normal naive pre-retrieval step is skipped
- if tool calling is not supported, it keeps naive RAG enabled as a fallback so KB retrieval does not disappear completely

### 2. Inject retrieval policy into the system prompt

At the same time, AgenticRAG injects an extra system prompt telling the model that:

- configured KBs are the primary source of truth for in-scope facts
- there is no automatic retrieval fallback
- for factual, policy, procedural, product, and domain-specific questions, it should prefer `query_knowledge`

This matters because tool descriptions alone are often not strong enough to reliably change model behavior.

### 3. Let the model inspect and query KBs

The agent can then use `query_knowledge` in two steps:

- `action="list"` to see which KBs are available
- `action="query"` to search one KB or several KBs in parallel

For single-KB retrieval, the preferred parameter is `kb_id`.
For multi-KB retrieval, use `kb_ids`.

### 4. Return retrieval results as structured JSON

The tool merges results, annotates them with `knowledge_base_id`, and returns JSON so the model can continue reasoning, tool use, or final answering.

## Retrieval Behavior

When AgenticRAG is enabled, it disables the runner's automatic naive RAG pre-processing for the current pipeline.

- Retrieval is no longer performed automatically before the model answers
- Whether to query a knowledge base is now a deliberate model decision through `query_knowledge`
- If the model does not call the tool, no KB content will be injected into context

There is one important exception:

- if the active LLM does not support tool calling, AgenticRAG keeps naive RAG enabled instead of disabling it

This reduces unconditional retrieval noise, but it also means prompting matters. The current implementation therefore uses **both**:

- a tool prompt on `query_knowledge`
- an injected system prompt during `PromptPreProcessing`

Together, they bias the model toward retrieval for factual, policy, procedural, product, and other domain-specific questions.

## Why It Is Designed This Way

This plugin is optimized for a specific tradeoff:

- keep LangBot's existing KB and retrieval infrastructure
- remove unnecessary always-on retrieval
- let the model make explicit retrieval decisions
- still keep retrieval behavior constrained to the current pipeline

Compared with naive RAG, this design gives you:

- less irrelevant context on turns that do not need KB access
- better control over which KB is queried
- room for iterative retrieval, re-querying, and multi-KB reasoning

The downside is also real: if the model never calls the tool, no KB content appears. That is why the plugin explicitly adds retrieval-oriented prompting, instead of assuming the model will naturally choose retrieval often enough.

This is also why the plugin now detects tool-call capability before disabling naive RAG. Without that guard, enabling AgenticRAG on a non-tool-capable model would accidentally break KB retrieval entirely.

## Security Boundary

This tool is scoped to the current pipeline.

- LangBot runtime also validates that the requested `kb_id` belongs to the current pipeline before executing retrieval

This means prompt injection alone should not allow the agent to query arbitrary KBs outside the pipeline configuration.

## How To Use

1. Install and enable the plugin.
2. Configure one or more knowledge bases in the current pipeline's local agent settings.
3. Let the agent call `query_knowledge`:
   - Start with `action="list"` to inspect available KBs
   - Then call `action="query"` with `kb_id` for one KB, or `kb_ids` for multiple KBs queried in parallel
   - Provide `query_text`, and optional `top_k` for the merged result count

## Parameters

For `action="query"`, the tool currently accepts:

- `kb_id`: target knowledge base UUID for single-KB retrieval; preferred when querying exactly one KB
- `kb_ids`: optional array of target knowledge base UUIDs for parallel multi-KB retrieval; use only when querying multiple KBs
- `query_text`: retrieval query text
- `top_k`: optional positive integer, default `5`, applied to the merged result set

If one KB query fails while others succeed, the tool returns a JSON object with `results` and `failed_kbs` so the agent can continue with partial results.

## Typical Flow

1. Agent lists available KBs.
2. Agent selects one KB or a small set of KBs based on name and description.
3. Agent submits a focused retrieval query.
4. Agent uses the returned chunks to answer or continue tool use.

## Prompting Intent

The prompting layer is designed to communicate two things to the model:

- these knowledge bases are the authoritative source for in-scope information
- no fallback automatic retrieval exists once AgenticRAG is enabled

Without that guidance, an LLM may over-trust its pretrained knowledge and under-use retrieval. The current implementation therefore reinforces the same policy at both the system-prompt layer and the tool-prompt layer.

## Logging

The plugin now emits logs during tool execution so you can observe how the LLM is using AgenticRAG in practice.

You will see logs for:

- tool call start, including `query_id`, `action`, and parameter keys
- KB listing start/end and how many KBs are visible
- retrieval start, including selected KBs, `top_k`, and a shortened `query_text` preview
- per-KB retrieval start/success/failure
- final retrieval summary, including merged result count, failed KB count, and returned result count

Typical log messages look like:

```text
[AgenticRAG] tool call started: query_id=123 action=query params_keys=['action', 'kb_id', 'query_text', 'top_k']
[AgenticRAG] retrieval requested: query_id=123 kb_ids=['kb-1'] kb_count=1 top_k=5 query='what is the refund policy'
[AgenticRAG] querying knowledge base: query_id=123 kb_id=kb-1 top_k=5
[AgenticRAG] knowledge base query succeeded: query_id=123 kb_id=kb-1 result_count=4
[AgenticRAG] retrieval completed: query_id=123 merged_results=4 failed_kbs=0
```
