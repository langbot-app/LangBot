# Shared runtime source candidate (SDK >=0.7.4)

This source declares `sharedRuntime: shared-runtime-v1` and `componentModel: stateless-v1`.
It is source-reviewed for the multi-tenant contract; it is **not certified** and makes no
claim of live tenant acceptance.

- Configuration is read per invocation with `self.get_config()` /
  `self.get_plugin_config()`. HelloPlugin declares no config items (`spec.config: []`), so
  the shared worker never reads tenant settings; nothing from an installation is copied
  onto the plugin, the components or module globals.
- `initialize()` is empty, so a shared worker is never initialized with another
  installation's settings.

## Per invocation

- `GetWeatherAlerts.call` builds the NWS URL from its arguments and creates a fresh
  `httpx.AsyncClient` for every request (`components/tools/get_weather_alerts.py`); no
  client, response or parameter is cached on the shared tool object.
- `DefaultEventListener`'s handler only assigns `event_context.event.user_message_alter`
  on the event it received; it keeps no state across events.
- `Info` builds its reply from the `ExecuteContext` of the current command invocation.
- No SDK process-global settings are modified.

## Identity

No upstream/tenant identity is derived: the plugin exposes no per-user vendor state and
calls no identity-scoped Host API.

## Tests

`tests/test_shared_runtime.py` drives one plugin/component object graph across two
distinct `InstallationBinding` values with the real SDK `bind_invocation(...)` and
`InstallationBinding`, and asserts (a) the shared tool resolves the invocation config and
produces installation-independent results while retaining no attributes, and (b) the
listener mutates only the per-event context. HTTP replies are simulated; no live network
or vendor account is used.

## Known limits

- `spec.config` is empty: there are no installation settings to resolve, and the shared
  and dedicated paths behave identically.
- No claim of certification; independent review and two-Workspace invocation acceptance
  are still required.
