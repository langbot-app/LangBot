# Certified Plugins

## Admission boundary

Core verifies a plugin archive **before** artifact storage, `PluginSetting`
persistence, or a Plugin Runtime apply request. It calls the SDK public
`langbot_plugin.certification.verify_archive()` API, which reads the strict
certificate envelope from the ZIP comment and verifies the signed normalized
ZIP digest without extracting the payload.

Core retains the artifact SHA-256, normalized digest
(`normalized_zip_digest()`), verification state, declared shared-runtime
profile, `stateless-v1` component model, key ID, selected admission profile, and stable admission code in the
durable plugin `install_info._certification` record. The record belongs to the
installation row; no schema migration is needed for this additive JSON
metadata.

## Trusted issuer configuration

Hosted Cloud provisions the non-secret Ed25519 issuer public-key ring out of
band. Key IDs must match the SDK envelope; values are base64 public keys, never
private signing keys. Invalid configuration fails closed; keep old issuer keys
through rotation while their signed archives remain installed.

```yaml
plugin:
  certification:
    trusted_public_keys:
      issuer-2026-q3: "<base64 encoded 32-byte Ed25519 public key>"
```

Key IDs must match the SDK envelope. Values are standard base64 raw public
keys, not private/signing keys. An invalid key-ring configuration is rejected
rather than weakening verification. Keep active issuer keys during a rotation
until archives signed by retired IDs are no longer installed.

The ring may also be supplied out-of-band, which is how hosted deployments
provision it:

```bash
PLUGIN__CERTIFICATION__TRUSTED_PUBLIC_KEYS_JSON='{"ed25519:issuer":"<base64>"}'
```

An **empty** ring is a supported state, not a misconfiguration. OSS defaults to
it and supports one Workspace; configuring certification keys on OSS is not a
supported way to enable cross-tenant sharing. Cloud provisions the ring to grant
shared placement only to eligible v2 artifacts. Certification means eligibility
for Cloud cross-tenant use of the same Worker and the same plugin/component
singleton, never a dedicated certificate or intermediate trust tier.

## Admission matrix

| Deployment | SDK verification | Explicit `administrator_force` | Result |
| --- | --- | --- | --- |
| Cloud | valid envelope declaring `shared-runtime-v1` + `stateless-v1` | any | admitted to the shared singleton profile |
| Cloud | no signature | any | install on dedicated worker, without shared eligibility |
| Cloud | malformed, untrusted, invalid, or non-shared declaration | any | reject before storage with `CERTIFIED_PLUGIN_CLOUD_CERTIFICATE_INVALID`; do not treat a broken signature as unsigned |
| OSS | absent legacy envelope | any | admitted to the dedicated profile |
| OSS | valid envelope declaring `shared-runtime-v1` + `stateless-v1` | any | dedicated only; OSS has no cross-tenant shared placement |
| OSS | invalid declaration referencing a **key this instance resolves** | false | reject with `CERTIFIED_PLUGIN_OSS_FORCE_REQUIRED` |
| OSS | invalid declaration referencing a **key this instance resolves** | true | admitted to the dedicated profile |
| OSS | declaration this instance **cannot resolve** (empty ring) | any | admitted to the dedicated profile |

There is no dedicated certification, dedicated signature, or intermediate
certification trust tier. Advisory review is an internal prerequisite, not an
installation trust status. An `issued` marketplace badge, source candidate,
matching version, or shared artifact/dependency tree alone does not prove Cloud
admission or Worker sharing. Compare the downloaded archive's ZIP comment,
normalized digest and signed claims with the public version record and deployed
Core trust-key ring. Confirm two Workspace bindings share one Worker PID, one
plugin object, and one object for each declared component before claiming live
cross-tenant sharing.

A declaration is "resolvable" only when its `key_id` is present in the
configured ring. A parseable declaration from a resolved key that fails
signature, digest, identity, profile, or component-model validation requires
`administrator_force` in OSS. Malformed or unsupported envelopes without a
resolved certificate identity are treated as untrusted and stay dedicated.

`administrator_force` is deliberately strict: it is recognized only when the
install request carries boolean `true`. The local upload endpoint accepts the
multipart field `administrator_force=true`; GitHub and marketplace install
payloads carry the same field. The existing resource-manage authorization fence
protects those endpoints. A force never creates a Cloud dedicated fallback or
certifies an invalid signature. A legacy v1 certificate may verify
cryptographically, but without a signed stateless component claim it is
rejected in Cloud; an old marketplace `issued` badge alone grants no placement.
Unsigned Cloud archives are the dedicated fallback.

## Runtime and logs

The first stateless-compatible SDK release will carry the v2 certificate and
singleton component contract; its final version is assigned only at release.
Core must pin that release before sending or selecting the new contract. Core selects `shared-runtime-v1` only when
the persisted certification record says verification was valid, both the
certificate and admission profiles are `shared-runtime-v1`, the admission code
is shared-eligible, and the record's artifact SHA-256 exactly matches the
installation row. Missing, malformed, stale, invalid, or dedicated admission
facts select `dedicated`. Install, upgrade, configuration revision, restart,
and reconnect all use this same persisted-fact derivation.

The certificate must also bind `component_model=stateless-v1`. This profile
creates one `BasePlugin` and one instance of each component per digest Worker.
Installation slots contain immutable config snapshots and authority only;
task-local invocation context selects the active slot. Older certificates that
do not bind the component model are not eligible for shared placement. Their
source packages remain compatible on dedicated Workers under OSS policy.

The existing public plugin-log boundary already applies the immutable
installation binding (including workspace UUID) through
`RuntimeConnectionHandler.installation_scope()` before requesting logs. This is
the actual tenant exposure boundary, so valid shared certificates use that
binding-scoped transport; Core does not invent a second log stream or expose
process-wide log output. Dedicated and invalid/legacy installations use the
same existing installation scope.

## SDK versioning

Ship in dependency order: SDK v2 certificate support, then Core exact pin and
lockfile, then Space signing, then Runtime/Core rollout. Legacy v1 envelopes
remain verifiable but do not carry `stateless-v1`, so they never select shared
singleton placement without re-review and v2 re-signing.
