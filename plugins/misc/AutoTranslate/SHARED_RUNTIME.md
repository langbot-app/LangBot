# Shared runtime source candidate (SDK >=0.7.4)

This source declares `sharedRuntime: shared-runtime-v1` and `componentModel: stateless-v1`.
It is source-reviewed for the multi-tenant contract; it is **not certified** and makes no
claim of live tenant acceptance.

- Configuration (`target_language`, `model`, `min_text_length`, `enable_private`) is read
  per event with `plugin.get_config()`. Nothing from tenant config is copied onto the
  plugin, the `Translator` component or module globals.
- `initialize()` only logs; a shared worker is never initialized with another
  installation's settings, and no SDK process-global settings are modified.

## Per event

- `Translator._handle_message` resolves the enable/disable flags, minimum length, target
  language and model for the event it is handling. When no model is configured it falls
  back to the first model returned by `plugin.get_llm_models()` for that invocation.
- The translation call `plugin.translate(...)` uses `invoke_llm` under the task-local
  invocation, so the Host model authority comes from the active installation.
- The listener replies through the per-event `EventContext` and retains nothing between
  events.

## Identity

No upstream/tenant identity is derived; the plugin keeps no per-user state and calls no
identity-scoped Host API.

## Tests

`tests/test_shared_runtime.py` drives one plugin/component object graph across two
distinct `InstallationBinding` values with the real SDK `bind_invocation(...)` and
`InstallationBinding`, and asserts (a) target language/model/private gating are resolved
per event, and (b) the model fallback follows the invocation. The LLM call is simulated;
no live network or vendor account is used.

## Known limits

- The plugin ships no `requirements.txt`: the suite depends only on the SDK, the standard
  library and pytest.
- Translation quality and language detection depend entirely on the Host-provided model.
- No claim of certification; independent review and two-Workspace invocation acceptance
  are still required.
