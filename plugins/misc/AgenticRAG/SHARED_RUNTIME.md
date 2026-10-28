# Shared runtime source candidate (SDK >=0.7.4)

This source declares `sharedRuntime: shared-runtime-v1` and `componentModel: stateless-v1`.
It is source-reviewed for the multi-tenant contract; it is **not certified** and makes no
claim of live tenant acceptance.

- Configuration is read per invocation with `self.get_config()`. AgenticRAG declares no
  config items (`spec.config: []`); nothing from an installation is copied onto the
  plugin, the components or module globals.
- `initialize()` is empty, so a shared worker is never initialized with another
  installation's settings. No SDK process-global settings are modified.

## Per invocation

- `QueryKnowledge.call` builds a new `QueryBasedAPIProxy(query_id=<call argument>,
  plugin_runtime_handler=self.plugin.plugin_runtime_handler)` for every tool call
  (`components/tools/query_knowledge.py`); nothing is cached on the shared tool object, so
  concurrent invocations cannot observe each other's query id.
- `DisableNaiveRAG` reads the per-event query vars and resolves the active LLM's
  tool-call capability from `self.plugin.get_llm_models()` for every event, then mutates
  only the received `EventContext` (`set_query_var`, `event.default_prompt`). It retains
  no tenant state.
- Retrieval authority comes from the task-local SDK invocation; the tool passes the
  runtime handler through to the proxy rather than holding an API client.

## Identity

No upstream/tenant identity is derived: knowledge-base access is scoped by the Host's
query-based API, not by a plugin-computed identity.

## Tests

`tests/test_shared_runtime.py` drives one plugin/component object graph across two
distinct `InstallationBinding` values with the real SDK `bind_invocation(...)` and
`InstallationBinding`, and asserts (a) each call constructs a fresh proxy carrying that
call's query id and the shared runtime handler, and (b) the listener's naive-RAG decision
follows the invocation's model capability and only touches the per-event context.
Knowledge-base and model replies are simulated; no live network or vendor account is used.

## Known limits

- `spec.config` is empty: the plugin exposes no installation settings.
- Knowledge-base retrieval and model metadata depend on Host APIs; their cross-worker
  aggregation semantics are the Host's, not this plugin's.
- No claim of certification; independent review and two-Workspace invocation acceptance
  are still required.
