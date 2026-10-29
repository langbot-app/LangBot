# Shared runtime source candidate (SDK >=0.7.4)

This source declares `shared-runtime-v1` and `stateless-v1`. It is not certified
and makes no claim of live vendor acceptance. Certification additionally requires
independent review, signer approval, and two-Workspace invocation acceptance.

- `initialize()` is process-scoped and touches no configuration.
- The Tavily API key is read from the **current invocation** with
  `self.get_plugin_config()` (the task-local installation snapshot). It is never
  copied into an instance field or module global.
- `TavilyClient` is built per invocation from that key.
- `TavilyClient.search` is synchronous; it is dispatched with
  `asyncio.to_thread(...)` so a slow vendor call cannot stall the shared event
  loop and every other tenant on the worker.
- No binding-keyed caches or detached tasks exist, so
  `on_installation_revoked()` has nothing to release.

## Limits

- Thread offload means a cancelled invocation does not guarantee rollback of an
  already-dispatched vendor search; the request completes in the worker thread.
- Concurrency is bounded by the default executor's thread pool.
- Tests replace `TavilyClient` with an in-process stub; they are not paid/live
  Tavily API tests.
