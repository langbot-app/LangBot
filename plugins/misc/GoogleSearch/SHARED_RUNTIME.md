# Shared runtime source candidate (SDK >=0.7.4)

This source declares `shared-runtime-v1` and `stateless-v1`. It is not certified
and makes no claim of live vendor acceptance. Certification additionally requires
independent review, signer approval, and two-Workspace invocation acceptance.

- `initialize()` is process-scoped and touches no configuration.
- The SERP API key is read from the **current invocation** with
  `self.get_plugin_config()` (the task-local installation snapshot). It is never
  copied into an instance field or module global.
- An `httpx.AsyncClient` is created per invocation and the request is awaited, so
  the component never runs blocking socket IO on the shared event loop.
- No binding-keyed caches, stateful client objects, or detached tasks exist, so
  `on_installation_revoked()` has nothing to release.

## Limits

- One outbound request per call, 5 s timeout, no retries. Redirects are not
  followed (unchanged from the previous synchronous implementation).
- The plugin stores no tenant state anywhere; a revocation-safe cache is
  therefore unnecessary rather than omitted.
- Tests use the installed SDK types with a stubbed HTTP transport; they are not
  paid/live SERP API tests.
