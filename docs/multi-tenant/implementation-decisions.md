# Multi-tenant implementation decisions

This log records implementation choices made while delivering the Workspace architecture. It is intended to make trade-offs auditable without interrupting implementation for routine decisions.

> Open challenges that may supersede parts of this log are tracked in
> [pending-architecture-decisions.md](./pending-architecture-decisions.md). They remain proposals until a decision is recorded here.

## 2026-07-18

### OSS remains a singleton Workspace with multiple Accounts

- Decision: Community builds create exactly one Workspace per LangBot instance and allow multiple Accounts through invitations.
- Reason: This preserves a simple self-hosted deployment while making authorization and ownership explicit. Creating a second Workspace is an edition error, not a hidden fallback.
- SaaS boundary: Multi-Workspace directory, placement, entitlement, and billing are the responsibility of a separate closed SaaS Control Plane. Core consumes a validated projection and remains the final isolation and authorization enforcement point; it does not become the SaaS system of record or billing engine.
- Deployment boundary: Cloud v2 is a greenfield deployment design. The previous Space instance/pod deployment scheme is not migrated, preserved for compatibility, or extended by this implementation. Existing Space OAuth, marketplace, and payment concepts may be reused only through explicit adapters where they still fit; `langbot-space` itself is not changed.

### Workspace selection is trusted only after authentication

- Decision: Browser requests carry `X-Workspace-Id`, but the server resolves it against the authenticated Account membership. API keys, public Bot routes, webhooks, jobs, and plugin calls derive Workspace from their trusted owning resource or binding instead of trusting the header.
- Reason: A selector is routing input, not authorization evidence.
- Compatibility: Community builds may select the singleton Workspace when the header is omitted. A multi-Workspace-capable build must reject an omitted selector.

### Stable Account UUID is the token subject

- Decision: New JWTs use the stable Account UUID as `sub`; a bounded compatibility path accepts legacy email-subject tokens and rotates them when checked.
- Reason: Email can change and therefore cannot be a durable authorization identity.

### Fixed roles are authoritative in Core

- Decision: `owner`, `admin`, `developer`, `operator`, and `viewer` map to a fixed permission matrix in LangBot Core. The last owner cannot be removed or demoted, and invitations cannot create an owner directly.
- Reason: Core must remain the final authorization boundary in both OSS and SaaS deployments.

### Cross-Workspace access is indistinguishable from absence

- Decision: Resource lookups always include Workspace UUID. A guessed UUID belonging to another Workspace returns 404; a visible resource with insufficient same-Workspace permission returns 403.
- Reason: This avoids leaking resource existence across tenants while preserving actionable same-tenant errors.

### Plugin Runtime binds to exactly one Workspace

- Decision: A trusted LangBot control connection binds a Plugin Runtime to one `instance_uuid`, `workspace_uuid`, `placement_generation`, and optional installation. Repeating the same binding is idempotent; rebinding is rejected. Plugin-supplied context fields are stripped.
- Reason: One untrusted plugin process must never become a cross-Workspace router.
- Compatibility: Older SDK payloads without context still deserialize, but Workspace storage and tenant Host APIs fail explicitly until a trusted binding is established.
- Startup fence: The Runtime does not launch or register plugins until `SET_RUNTIME_CONFIG` establishes the trusted Workspace binding. A cloud or multi-Workspace connector must be constructed for one explicit projected Workspace and generation; it never falls back to a migration-created local compatibility Workspace.

### Invitation delivery does not require SMTP

- Decision: Core returns an invitation secret once for copy-and-share, persists only its hash, and supports expiry, revocation, and one-time acceptance.
- Reason: Self-hosted OSS must support adding users without an email service while avoiding recoverable invitation secrets at rest.
- Browser handling: The copyable invitation URL carries the secret in its fragment, which browsers do not send in HTTP requests or Referer headers. The acceptance page immediately removes the fragment and keeps the secret only in `sessionStorage` until login or acceptance completes; it is never placed in a path, query string, analytics event, or persistent local storage.

### Schema rollout is additive before enforcement

- Decision: Add Account/Workspace directory tables first, then add non-null Workspace ownership to every tenant resource with a deterministic default-Workspace backfill. Runtime and service enforcement is enabled only with matching migration and isolation tests.
- Reason: A Workspace column alone is not isolation, and enforcing queries before data backfill would break upgraded installations.

### Login capability discovery is instance-scoped, not account-scoped

- Decision: The unauthenticated login bootstrap endpoint reports only which login mechanisms the instance supports. It does not inspect the first Account or expose whether that Account has a password. Both password and Space OAuth entry points are available on a multi-user instance; the submitted identity determines which mechanism is valid.
- Reason: This avoids projecting the original owner's authentication type onto invited users and removes a public Account-state disclosure.

### Space OAuth identity does not choose a SaaS Workspace

- Decision: Space OAuth tokens remain Account credentials. In OSS singleton mode, an OAuth refresh may update the singleton Workspace's Space provider only when that Account's role can manage provider secrets. In SaaS multi-Workspace mode an OAuth callback without an authenticated Workspace selector never guesses which Workspace to mutate; explicit Workspace configuration or the closed control plane owns that linkage.
- Reason: An Account may belong to several Workspaces, and authentication must not silently mutate a shared tenant secret.

### SaaS execution state is a validated Core projection

- Decision: Core can resolve both local and `cloud_projection` Workspaces, but only from an explicit Workspace UUID and an active, unfenced `WorkspaceExecutionState` for the current instance and matching source. OSS-only bootstrap paths additionally require `source=local`.
- Reason: The closed control plane owns placement decisions, while Core remains the enforcement point for instance binding, generation, and write fences.

### API-key secrets are one-time and Workspace-bound

- Decision: Database API keys persist only a globally unique SHA-256 hash, an opaque UUID, one Workspace UUID, explicit fixed-permission scopes, status, expiry, creator, and last-used time. The raw secret is returned once. Authentication derives Workspace and generation from the key record and ignores Workspace selectors. Legacy plaintext keys are hashed during migration and receive a compatibility `*` scope. The plaintext config key works only for the OSS singleton Workspace and is disabled in multi-Workspace mode.
- Reason: A bearer key is an identity and routing credential, not merely a password layered on top of caller-controlled tenant selection.

### MCP tools inherit the authenticated API-key context

- Decision: The MCP ASGI mount authenticates the API key once, binds an immutable per-request `RequestContext`, and every tool checks a fixed permission before calling tenant services with that same context.
- Reason: Authenticating the transport without propagating Workspace identity into tool calls would leave the direct service path globally scoped.

### Unreleased SDK protocol is pinned reproducibly without publishing

- Decision: The SDK tenancy protocol is versioned as 0.4.15. This task does not create a GitHub release or publish PyPI because the user authorized pushing code, not a package release. After the SDK feature branch is final, LangBot's feature branch temporarily pins the exact pushed SDK Git commit. Before merging to master, the release gate is to publish `langbot-plugin==0.4.15` and replace the Git pin with the registry pin.
- Reason: PyPI 0.4.14 does not contain `ActionContext`; pinning it makes clean installs fail, while pinning an unpublished 0.4.15 makes dependency sync impossible. An exact Git commit is reproducible and keeps the feature branch testable without expanding release authority.

### Cloud directory writes stay outside Core

- Decision: The open-source Core startup always installs `SingleWorkspacePolicy`, creates or repairs one local Workspace, and permits local membership/invitation workflows. Changing mutable configuration such as `system.edition` cannot activate multi-Workspace routing. The future closed Cloud bootstrap will install `CloudWorkspacePolicy` only after verifying a signed `InstanceManifest`; that policy requires an explicit projected Workspace selector, does not create Workspaces, and rejects invitation or membership mutations with `control_plane_required`; member reads use the versioned local projection.
- Ownership split: The closed Control Plane owns the global Account/Workspace/Membership/Invitation directory, placement and lease generations, entitlements, subscription state, usage aggregation, and billing decisions. Core owns request authorization, resource scoping, execution-generation validation, and fail-closed enforcement. Provisioning and invoice computation do not belong in open-source Core.
- Reason: The closed control plane is authoritative for SaaS Account, Workspace, Membership, and Invitation state. Allowing Core to mutate the same directory would create split-brain ownership and would make an ownerless compatibility Workspace a dangerous fallback.
- Release gate: Multi-Workspace activation is deliberately unavailable in the open-source bootstrap. Production Cloud v2 must implement the signed `InstanceManifest` verifier and closed bootstrap described in the architecture document before it can inject `CloudWorkspacePolicy`; `edition=cloud`, an environment variable, or any unsigned local configuration is never a valid activation credential.

### Workspace bootstrap is reactive and ordered before browser resource calls

- Decision: The web application blocks Workspace-owned pages until Account and current Workspace bootstrap completes. A `useSyncExternalStore` Workspace store publishes permission changes to React consumers; direct mutation-only routes and controls are hidden or disabled when the fixed role lacks the required permission.
- Reason: Mutating a module-level variable after the initial React render did not reliably re-render permission controls, and mounting resource pages before the selector was established could issue tenant requests without `X-Workspace-Id`.

### JWTs are bound to one LangBot instance

- Decision: New Core JWTs require `iss=langbot-core`, an audience derived from the immutable instance UUID, and an expiry. Legacy community tokens are accepted only when they have the historical issuer, carry no audience, and the active policy is the OSS singleton policy.
- Reason: A token issued by one instance must not authenticate against another instance that happens to share a secret, and a compatibility decoder must not become an alternate path around the SaaS trust boundary.

### Runtime control transports authenticate before protocol dispatch

- Decision: External Plugin Runtime and Box WebSocket control channels require independent strong shared secrets in handshake headers. Locally managed child processes receive ephemeral secrets through their environment; secrets are not placed in URLs, process arguments, request payloads, or logs. Box additionally binds the first authenticated control channel to one trusted instance. Plugin Runtime debug and control credentials remain separate.
- Reason: Workspace context inside an RPC payload is not trustworthy until the transport peer itself is authenticated. Separating control and debug credentials also limits accidental privilege reuse.
- Deployment consequence: Docker Compose and Kubernetes wire one shared secret to each host/runtime pair. An empty external-runtime secret fails startup instead of silently exposing an unauthenticated socket.

### Dashboard WebSocket sessions are tenant runtime objects

- Decision: A dashboard WebSocket sends an authentication frame immediately after upgrade. The server validates Account, Membership, permission, Pipeline ownership, instance, Workspace, and placement generation before registering the connection. Connection indexes, sessions, broadcasts, attachments, and resets include the complete execution scope.
- Reason: Browser WebSocket APIs cannot attach the normal authorization headers, and a process-global `pipeline_uuid` or `session_type` index can collide across Workspaces.

### Read permissions never imply secret permissions

- Decision: `resource.view` responses recursively redact Bot, Plugin, MCP, and provider credentials. Provider secrets require `provider_secret.manage`; Bot and Plugin configuration writes require `resource.manage`. Masked Plugin values can be round-tripped by a manager without overwriting the stored secret. Plugin Runtime debug credentials require `resource.manage`, not the operator-only `runtime.operate` permission.
- Reason: A multi-user Workspace needs useful viewer access without turning every visible configuration endpoint into credential export. Plugin debug attachment can register executable code and is therefore a resource-management operation.

### Temporary credential exchanges are bound to their initiator

- Decision: Lark, Weixin, DingTalk, WeComBot, and QQOfficial one-click registration sessions require `resource.manage` and store the initiating instance, Workspace, placement generation, and principal. Status and cancellation by any other scope return the same 404 as an unknown session.
- Reason: Random session IDs reduce guessing probability but do not authorize access to credentials returned by a completed exchange.

### Uploaded images and documents use different storage capabilities

- Decision: Browser images use the scoped `upload_image` owner type and may be resolved only through the opaque public-image route. RAG documents use `upload_document` and can be read, sized, or deleted only by an exact instance, Workspace, generation, and owner-type match. Legacy `upload` objects are cleanup-only.
- Reason: Treating every upload as a public image made a leaked document key sufficient to bypass authenticated RAG access.

## 2026-07-19

### Space OAuth state is server-issued and single-use

- Decision: Core issues an opaque, cryptographically random OAuth state for each Space login or Account-binding attempt, stores only its digest, and consumes it exactly once within a short expiry. Login and binding states are different capabilities; a binding state is additionally bound to the authenticated Account. Caller-supplied state, including a LangBot JWT, is rejected.
- Redirect boundary: Callback redirects are accepted only for the known callback path and an origin declared by the server-side `api.webui_url` or `api.webhook_prefix`. Request `Host` and `Origin` headers never expand this allowlist.
- Current deployment: The OSS state store is bounded and process-local, so a Core restart safely invalidates outstanding attempts. A horizontally scaled SaaS deployment must move this exchange to an atomic, shared Control Plane store before enabling the closed Cloud bootstrap.
- Reason: OAuth state is a narrow, one-time CSRF and flow-binding capability. Reusing a bearer JWT or trusting caller-controlled Host or Origin data would turn an authorization redirect into an Account-token theft or open-redirect primitive.

### OAuth provider subjects, not email addresses, bind Accounts

- Decision: A known Space `account_uuid` may refresh the credentials of its already-bound local Account. An unknown provider subject that presents an email belonging to an existing Account is rejected, even when the normalized emails match. The Account owner must authenticate locally and use the one-time, account-bound binding flow.
- Reason: Email is contact and display data, not a stable federated identity key. Email-only auto-linking would let provider verification drift or identity reassignment become a local Account takeover.

### Workspace discovery is an account-only bootstrap capability

- Decision: `ACCOUNT_TOKEN` validates the active Account JWT but intentionally cannot resolve a Workspace, receive `RequestContext`, or declare Workspace permissions. Its narrow bootstrap endpoint returns only active Workspace memberships belonging to that Account and never chooses the first Workspace when several exist. All tenant resource routes still require the explicit selector in multi-Workspace mode.
- Reason: Requiring a Workspace header to discover the Account's Workspaces creates an authentication deadlock; allowing the bootstrap route to perform tenant actions would create an authorization bypass. Separating the two capabilities resolves the cycle without weakening tenant routes.

### SQLite tenancy migrations have a verified recovery boundary

- Decision: Before each destructive tenant-schema boundary, a file-backed SQLite installation creates an online-consistent backup with its source and target revisions, runs `PRAGMA quick_check`, writes a durable manifest, and fsyncs restrictive-permission files and directories. A failed boundary disposes the engine, removes stale journal sidecars, atomically restores the verified source revision, and verifies the restored database before startup continues.
- Compatibility: In-memory SQLite cannot provide this recovery guarantee and is rejected for destructive production migration boundaries; it remains usable in tests that create the final schema directly.
- Reason: SQLite batch table rebuilds can leave an installation between schemas if a process or migration fails. A verified pre-boundary image makes retry behavior recoverable instead of merely idempotent in the happy path.

### Placement generation is an execution revocation capability

- Decision: RuntimeBot, RuntimePipeline, background tasks, object storage, Plugin Runtime, MCP, RAG, and Box operations carry the complete instance, Workspace, and placement-generation scope. They revalidate the active execution binding before accessing a provider or transport; long-running calls validate again before accepting results. A stale generation is fenced before it can read, write, or reuse a cached object.
- Plugin boundary: Each locally launched plugin receives a short-lived, one-use registration capability bound to the expected manifest identity and execution scope. The production child environment does not inherit the reusable debug credential, and Host APIs derive scope from the trusted connection and action context.
- Box boundary: Persistent skill content remains Workspace-scoped, while session/process state and relay requests also include placement generation. A generation change retires matching live sessions and closes a stale relay before further stdin, stdout, or file operations.
- Transaction boundary: Request admission and runtime side effects are fenced in this branch, but ordinary tenant database mutations do not yet hold a generation-aware lock through commit. The closed Cloud bootstrap must remain disabled until Core provides the shared-write/exclusive-cutover transaction primitive and a generation-stamped outbox (or an equivalent atomic publish fence). The OSS singleton policy has a fixed local generation and cannot trigger a placement cutover.
- Durable-object boundary: Current opaque storage keys include generation and therefore fail closed after a generation change. That is safe for OSS's fixed generation, but a Cloud cutover must not strand durable KB files, images, or plugin references. Cloud v2 must publish stable final object identities from generation-scoped staging, or perform an atomic object-and-reference migration before activating the new generation.
- Reason: Workspace UUID prevents cross-tenant collisions, but it cannot revoke work after a Workspace is moved or fenced. Placement generation is the monotonic lease that makes old runtimes unusable.

### Long-lived WebSockets continuously revalidate authority

- Decision: Dashboard WebSockets re-authenticate the Account, Membership, permission, resource ownership, instance, Workspace, and placement generation for every inbound message, not only during the initial frame. A changed role, removed Membership, or fenced placement takes effect without waiting for reconnect.
- Public embed boundary: The embed connection re-resolves its Bot before every message and rejects a Bot that was disabled, deleted, moved, or rebound. The public connection may identify a Bot, but it cannot make the initial Bot object an indefinite authorization capability.
- Reason: Authorization and resource state can change while a socket remains open. Connection-time validation alone leaves a revocation gap.

### Legacy vector migration is an OSS-local compatibility path

- Decision: Status, backup, execute, dismiss, and background entry points for legacy global vector collections require an active local Workspace binding under `SingleWorkspacePolicy`. A `cloud_projection` Workspace cannot observe or migrate the old global collection, even when it carries a legacy marker.
- Reason: The legacy collection predates tenant ownership. Treating it as a SaaS fallback would expose one installation's historical vectors to an arbitrary projected Workspace.

### External errors and persisted URLs are redacted centrally

- Decision: Unhandled HTTP and webhook failures return a stable `internal_error` response and request ID, and expose that ID in `X-Request-Id`; the detailed exception is retained only in server logs correlated by the same ID. Explicit domain and validation errors keep their documented status and code.
- Secret boundary: Shared sanitization removes URL user information and masks sensitive query parameters before provider or MCP configuration is serialized, logged, or shown to a reader. Masked placeholders can be round-tripped by an authorized manager without replacing the stored secret.
- Reason: Tenant isolation is incomplete if framework exceptions, connection URLs, or configuration reads can export credentials across otherwise authorized interfaces.
