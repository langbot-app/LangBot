# Shared runtime source candidate (SDK >=0.7.4)

This source declares shared-runtime-v1 and stateless-v1. It is not certified or a claim of live vendor acceptance.
The exact archive requires independent review, signer approval, and two-Workspace invocation acceptance.

- Configuration and credentials are read per invocation. No SDK process-global
  settings are modified.
- Host-managed state and the SDK connection binding supply authority. User config
  strings and adapter business parameters are not tenant identity.
- Explicit HTTP(S) self-hosted endpoints remain supported, including private service
  addresses. Endpoint validation is syntax validation, NOT an SSRF/network sandbox.
  Shared deployments MUST enforce their own egress policy against metadata/control
  endpoints and foreign tenant services. Do not certify a deployment without that
  network-policy evidence. Environment HTTP proxies are no longer implicitly inherited.
- Redirects are not followed by HTTP clients. Configure the final endpoint/attachment
  URL; redirect-dependent workflows must update their URL rather than forwarding
  credentials to an unreviewed destination.
- Tests use installed SDK types and actual local transports/processes, with explicitly
  simulated vendor replies. They are not paid/live vendor-account tests.

## Optional asset gateway

The listener belongs to the SDK-created Runner component (one per artifact), not
a process-global SDK singleton. Concurrent runs with identical host/port/timeout
share the component listener, with distinct revocable invocation capabilities and expiring tokens. Last release
closes the listener and drains accepted tasks. Conflicting fixed-port settings fail
instead of silently reusing or mutating an active listener. Separate installations require an explicit ingress route to their individual run tokens.
Limits: 16 accepted connections, 16 KiB headers, 1 MiB request/response, 32-message
MCP batches, finite request timeout <=120s and token TTL <=3600s. Tool RPC cancellation
does not promise rollback of an already-dispatched Host operation.

## Identity and per-invocation scope

This plugin derives no upstream user identity. Unlike `coze`/`dify`/`n8n`/`tbox`/
`weknora` there is no `pkg/scoped_identity.py` here and no user id is sent upstream.
The dead, uncalled `_get_user_tag` helper was removed: it returned an unscoped
`{actor_type}_{actor_id}` and fell back to a per-run `user_{run_id}`, and that
per-run fallback is exactly what the shared-runtime identity rule forbids.

Read per invocation from `ctx.config` (never cached on the shared component):
`base-url`, `api-key`, `flow-id`, `input-type`/`output-type`, `tweaks`, `timeout`
and the asset-gateway settings. Each run builds its own `AsyncLangflowClient`
with its own `x-api-key` header; `external.session_id` comes from Host-managed
run state.

Nothing is binding-keyed: the runner keeps no process cache, no detached
tenant-bearing tasks and no module-level mutable tenant state, so
`on_installation_revoked` has nothing to release. The asset-gateway listener is
owned by the SDK-created component and not by any installation.
