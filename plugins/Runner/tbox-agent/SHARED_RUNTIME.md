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

## Upstream identity migration

The identity is derived from the current invocation's trusted SDK installation
binding; the connection binding is only the dedicated-worker fallback, and a
shared worker whose invocation carries no binding refuses the call instead of
falling back to a weaker scope. With that authority,
upstream user IDs are deterministic `lb_` SHA-256 names scoped to that authority.
The same actor/legacy launcher in different installations/Workspaces no longer
collides. Dedicated OSS without either scope retains the existing legacy IDs.
Existing vendor conversations associated with the old unscoped user may require
a new conversation after upgrading; no automatic cross-user memory migration is
performed. Host-scoped state is not copied between tenants. A run whose sender is
not a trusted Host actor is refused before any outbound call instead of minting a
per-run vendor user; a conversation-scoped vendor user must be selected explicitly
through this plugin's `user-id-source` legacy mode.

## Synchronous vendor SDK isolation

Every SDK operation executes in a new killable Python subprocess, using only the
request's credentials and a minimal environment. Linux/Unix `resource` support is
required; native Windows is not supported by this candidate. Worker address-space
budget is 512 MiB; frame budget 1 MiB; stream budget 16 MiB. OS pipes apply bounded
backpressure. Timeout, cancellation and early close kill/reap the child before
returning. Host run concurrency/cgroup limits remain necessary. No daemon threads
or executor uploads survive cancellation. Parent-owned private temporary directories
are removed after reaping, including killed Tbox uploads. This is not proof of the
production nsjail subprocess/rlimit policy; exercise that policy before signing.
