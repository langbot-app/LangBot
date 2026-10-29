# Shared runtime source candidate (SDK >=0.7.4)

This source declares `sharedRuntime: shared-runtime-v1` and `componentModel: stateless-v1`.
It is source-reviewed for the multi-tenant contract; it is **not certified** and makes no
claim of live tenant acceptance.

## What is per invocation

- Every `spec.config` value — `server_url`, `api_token`, `timeout_seconds`,
  `allow_insecure_http`, `scope_mode`, `scope_id`, `allow_default_scope`, `auto_recall`,
  `capture_user_messages`, `max_context_bytes`, `search_limit` — is resolved by
  `PowerContextPlugin.settings()` from `self.get_config()` inside the invocation. No config
  value is copied onto the plugin object or any component object.
- The bearer token is resolved from that same per-invocation config and from nowhere else. The
  process environment is not consulted: a process-global credential combined with an
  installation-chosen `server_url` would let one installation send the worker's credential to a
  host it controls. A token configured for installation A is never sent to installation B's
  endpoint.
- `PowerContextSettings.new_client()` builds the transport client for the invocation that is
  about to issue a request. `PowerContextClient` holds no connection: every request opens its
  own `httpx.AsyncClient`, so the client is a thin descriptor carrying this invocation's
  endpoint and bearer token only. The `PromptPreProcessing` bridge resolves settings once per
  turn and reuses that turn's client for resolve/prepare/capture.
- `initialize()` is not overridden: a shared worker attaches it once with an empty config, so
  there is no process-scope place where tenant config could be captured.

## Binding-keyed state

- None. This plugin keeps no process-local tenant state, no Host storage rows, and no detached
  tasks, so there is nothing to key by installation binding and nothing for
  `on_installation_revoked()` to release; the `BasePlugin` default no-op is correct.
- Scope bindings live in the PowerContext Server, keyed by SHA-256 digests of the LangBot
  identity. The worker process caches neither bindings nor resolved scopes.

## Known limits

- Concurrent invocations of different installations share the plugin and component objects.
  The bridge is re-entrant: it holds no mutable state across `await`, and its per-turn state is
  task-local.
- Historical context is injected as untrusted data with an explicit boundary; the plugin does
  not authorize or act on it.
- `api_token` is a Host-stored configuration string scoped to one installation, never a process
  environment variable. Restrict access to plugin configuration and use HTTPS for a remote Server.
- Remote cleartext HTTP stays rejected unless `allow_insecure_http` is explicitly enabled; that
  is a deployment decision, not a network sandbox.
- Tests drive the real plugin and component objects through two `InstallationBinding` values
  with a recording HTTP transport and simulated PowerContext replies. They are not paid or live
  PowerContext Server tests.
- Not certified; independent review, signer approval, and two-Workspace invocation acceptance
  are still required.
