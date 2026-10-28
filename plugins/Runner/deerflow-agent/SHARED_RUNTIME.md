# Shared runtime candidate (SDK >=0.7.4)

This source declares the SDK shared-runtime contract. That declaration is not a
certificate or a claim of live vendor acceptance. Exact archives require a separate
independent review, signer approval, and two-Workspace acceptance.

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

## Identity and per-invocation scope

This plugin derives no upstream user identity. Unlike `coze`/`dify`/`n8n`/`tbox`/
`weknora` there is no `pkg/scoped_identity.py` here and no user id is sent upstream.
The dead, uncalled `_get_user_tag` helper was removed: it returned an unscoped
`{actor_type}_{actor_id}` and fell back to a per-run `user_{run_id}`, and that
per-run fallback is exactly what the shared-runtime identity rule forbids.

Read per invocation from `ctx.config` (never cached on the shared component):
`api-base`, `api-key`/`auth-header`, `assistant-id`, model/thinking/plan/subagent
flags, `timeout` and `recursion-limit`. Each run builds its own
`AsyncDeerFlowClient` with its own Authorization header; `external.thread_id`
comes from Host-managed run state. Handles are never reused across invocations.

Nothing is binding-keyed: the runner keeps no process cache, no detached
tenant-bearing tasks and no module-level mutable tenant state, so
`on_installation_revoked` has nothing to release.
