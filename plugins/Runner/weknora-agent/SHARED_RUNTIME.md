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

## Upstream identity migration

The identity is derived from the current invocation's trusted SDK installation
binding; the connection binding is only the dedicated-worker fallback, and a
shared worker whose invocation carries no binding refuses the call instead of
falling back to a weaker scope. With that authority,
the user name this plugin derives is a deterministic `lb_` SHA-256 name scoped to
that authority, and it reaches WeKnora as the **session title** (`IM Chat - <name>`).
The agent and knowledge chat request bodies this client builds carry no user field,
so the scoped name is not sent as an upstream user id; any vendor-side per-user state
keyed independently of the session is outside this plugin's control. Dedicated OSS
without either scope retains the existing legacy IDs. Existing vendor conversations
associated with the old unscoped user may require a new conversation after upgrading;
no automatic cross-user memory migration is performed. Host-scoped state is not copied
between tenants. A run whose sender is not a trusted Host actor is refused before any
outbound call instead of minting a per-run vendor user; this plugin exposes no
conversation-scoped `user-id-source` mode, so no vendor user is derived without a
trusted Host actor.
