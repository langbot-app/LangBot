# Shared runtime source candidate (SDK >=0.7.4)

This source declares `sharedRuntime: shared-runtime-v1` and `componentModel: stateless-v1`.
It is source-reviewed for the multi-tenant contract; it is **not certified** and makes no
claim of live tenant acceptance.

## What is per invocation

- `openai_api_key`, `api_base_url`, `model_name`, and `image_size` are read from
  `self.get_plugin_config()` inside the `!draw` invocation. Nothing from tenant config is
  copied onto the plugin object or the `Draw` component.
- `AIImagePlugin.create_client()` builds a fresh `AsyncOpenAI` from that invocation's
  `openai_api_key` and `api_base_url`. The SDK client is a thin httpx wrapper and is cheap to
  construct; the command closes it in a `finally` so no connection pool outlives the
  invocation.
- `initialize()` is not overridden and no client is cached on the plugin: a shared worker
  attaches it once with an empty config, so a cached client would carry one installation's API
  key and base URL into every other installation's `!draw`.

## Binding-keyed state

- None. No process-local tenant cache, no Host storage rows, and no detached tasks exist, so
  `on_installation_revoked()` keeps the `BasePlugin` no-op.

## Known limits

- One `!draw` performs one async image request; a slow or failing provider fails only that
  command and the client is still closed.
- The API key is a Host-stored configuration string. Restrict access to plugin configuration.
- The `openai` package is not installed in the local test environment, so the test replaces
  `sys.modules["openai"]` with a recorder and drives two installation bindings through one
  plugin/component object. These are not live provider tests.
- Not certified; independent review, signer approval, and two-Workspace invocation acceptance
  are still required.
