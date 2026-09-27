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

Configure the non-secret Ed25519 public-key ring in `data/config.yaml`:

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
it, so a self-hosted instance that has not provisioned any issuer key still
installs packages (see the admission matrix below). Configure the ring to grant
the shared-runtime profile; leave it empty to keep every package on the
dedicated profile.

## Admission matrix

| Deployment | SDK verification | Explicit `administrator_force` | Result |
| --- | --- | --- | --- |
| Cloud | valid envelope declaring `shared-runtime-v1` + `stateless-v1` | any | admitted to the shared singleton profile |
| Cloud | absent | any | reject before storage with `CERTIFIED_PLUGIN_CLOUD_CERTIFICATE_REQUIRED` |
| Cloud | malformed, untrusted, invalid, or non-shared | any | reject before storage with `CERTIFIED_PLUGIN_CLOUD_CERTIFICATE_INVALID` |
| OSS | absent legacy envelope | any | admitted to the dedicated profile |
| OSS | valid envelope declaring `shared-runtime-v1` + `stateless-v1` | any | selected shared singleton profile |
| OSS | declaration signed by a **key this instance resolves** | false | reject with `CERTIFIED_PLUGIN_OSS_FORCE_REQUIRED` |
| OSS | declaration signed by a **key this instance resolves** | true | admitted to the dedicated profile |
| OSS | declaration this instance **cannot resolve** (empty ring) | any | admitted to the dedicated profile |

The OSS row that matters for availability is the last one. Marketplace
packages are signed by the marketplace issuer and declare
`shared-runtime-v1`, while OSS ships an empty key ring by default. Treating that
as a rejection made every certified marketplace package uninstallable with
`CERTIFIED_PLUGIN_OSS_FORCE_REQUIRED` before artifact storage. Because the
certificate is signed by an issuer the instance does not declare trusted, no
shared-runtime privilege may be granted, so admission degrades the install to
the existing `oss_dev` dedicated profile and records
`CERTIFIED_PLUGIN_OSS_UNTRUSTED_DEDICATED`. This is not an escalation: it
withholds the shared profile rather than granting it.

A declaration is "resolvable" only when its `key_id` is present in the
configured ring. A parseable declaration from a resolved key that fails
signature, digest, identity, profile, or component-model validation requires
`administrator_force` in OSS. Malformed or unsupported envelopes without a
resolved certificate identity are treated as untrusted and stay dedicated.

`administrator_force` is deliberately strict: it is recognized only when the
install request carries boolean `true`. The local upload endpoint accepts the
multipart field `administrator_force=true`; GitHub and marketplace install
payloads carry the same field. The existing resource-manage authorization fence
protects those endpoints. A force never creates a Cloud dedicated fallback.

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
