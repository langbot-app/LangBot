# Shared runtime source candidate (SDK >=0.7.4)

This source declares `sharedRuntime: shared-runtime-v1` and `componentModel: stateless-v1`.
It is source-reviewed for the multi-tenant contract; it is **not certified** and makes no
claim of live tenant acceptance.

- The QWeather API key and subscription type are read per invocation from
  `self.plugin.get_config()`. Nothing is copied onto the plugin or the command component, so
  a shared worker never serves one installation with another installation's key.
- The HTTP fan-out (`Weather.load_data`) is fully async: `pkg/weather_data._get_data` uses
  `httpx.AsyncClient` and is awaited by the command handler. The previous synchronous
  `requests.Session().get` chain is gone, so a slow upstream no longer stalls other tenants
  sharing the event loop. Per-request timeout is 10 s.
- The fan-out is structured: if one request fails, or the invocation is cancelled, the
  remaining request tasks are cancelled and awaited to completion before the error is
  propagated, so no request task (and no in-flight use of this invocation's API key)
  outlives the command call.
- The command module no longer mutates `sys.path` at import or call time; the plugin root is
  only expected on `sys.path` the way the SDK loads `components`/`pkg` packages.

## Per-invocation vs process state

- There is no process-global tenant state: a `Weather` data object (city, key, api type,
  fetched values) is created inside each invocation and discarded when it returns.
- Consequently there is nothing keyed by an installation binding and nothing to release in
  `on_installation_revoked`; the command component holds no caches.

## Known limits

- Each call creates its own `httpx.AsyncClient` (matching the previous per-call
  `requests.Session`); there is no connection pooling across invocations.
- Only the fixed QWeather endpoints are called; no proxy/egress policy is configured here.
- No claim of certification; independent review and two-Workspace invocation acceptance are
  still required.
