# Harness Cloud authorization: integration boundary

Cloud Space enrollment is not enabled. `HarnessBindings` currently requires OSS,
emits `kind=self`, and supplies the production HTS1 transport factory through
`harness.wiring.install`. The encrypted RPC dispatcher has password and refresh
grants but no Space approval or exchange. Changing the deployment guard or the
registration kind alone would not enable safe Cloud enrollment.

The existing Core `/api/v1/user/space/callback` consumes WebUI login state or a
Space direct-launch assertion. It reconciles directory state, resolves the
Account and Workspace, and issues a Core account token. That token has neither
a Harness grant row nor binding/device claims. A support-admin launch has no
customer Account to bind. Neither callback branch authorizes a Harness device.
Workspace `harness.manage` controls links issued by that Workspace today; it
does not authorize an operator to act for every tenant of the shared instance.

## Smallest isolated positive acceptance

1. Configure a single official Cloud test origin and its independently trusted
   initial instance pin. Use a test Space OAuth client/purpose, exact HTTPS
   callback, authorization code with S256 PKCE, and an explicit browser consent
   screen. A signed customer `workspace.launch` intended for the WebUI, an
   admin/support launch, a Space PAT, or a Core WebUI token must not be exchanged
   for a Harness grant.
2. Start from an instance binding link issued under approved Cloud policy.
   Enroll the public keys as a pending device. Through pinned HTS1, create a
   short-lived server-owned authorization record scoped to instance, pending
   binding, device, and target Workspace. Bind OAuth state and the callback to
   this record. Browser approval records the Space Account's stable UUID and
   authorized Workspace, never an email match or an Account UUID supplied by
   the Harness client. The browser does not receive a Harness access or refresh
   token. Use a one-shot browser approval, not the OAuth Device Flow.
3. On encrypted redemption, check that the same device proved possession on
   the same instance, reconcile the trusted directory, and resolve the current
   active Account and membership. Atomically consume the approval, activate
   binding/device, and write the existing WS-compatible Harness grant. Do not
   carry Space billing/admin scopes into the grant. `workspace.select`, if
   enabled, must recheck the live membership and the Cloud Harness policy for
   the destination; a one-Workspace pilot must not let selection widen access.
4. Use an isolated Space account and two Workspaces, with a real consent and
   callback, then redeem over HTTPS/HTS1 and authenticate WSS with the issued
   grant. Prove a second device and wrong Workspace cannot redeem, replay does
   not mint another grant, and cancel/expiry leaves no active binding/grant.
   Verify directory removal stops subsequent RPC and WSS frame authorization.
   Run with the actual restricted Cloud runtime database role: establish the
   explicit grant/enrollment table access it needs without granting broad
   access to tenant data or disabling existing Workspace RLS.

The current executable baseline is negative: Cloud mode does not install the
transport or expose registration/handshake, and a valid Core browser account
token is denied inside a real self-hosted HTS1 RPC even for an enrolled device.
The existing Space assertion and self-hosted Harness tests exercise their
respective sides independently; they are not evidence of Cloud enrollment.
