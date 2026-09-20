# Certified Plugins

## Admission boundary

Core verifies a plugin archive **before** artifact storage, `PluginSetting`
persistence, or a Plugin Runtime apply request. It calls the SDK public
`langbot_plugin.certification.verify_archive()` API, which reads the strict
certificate envelope from the ZIP comment and verifies the signed normalized
ZIP digest without extracting the payload.

Core retains the normalized digest (`normalized_zip_digest()`), verification
state, declared shared-runtime profile, key ID, selected admission profile, and
stable admission code in the durable plugin `install_info._certification`
record. The record belongs to the installation row; no schema migration is
needed for this additive JSON metadata.

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

## Admission matrix

| Deployment | SDK verification | Explicit `administrator_force` | Result |
| --- | --- | --- | --- |
| Cloud | valid envelope declaring `shared-runtime-v1` | any | admitted to the shared profile |
| Cloud | absent | any | reject before storage with `CERTIFIED_PLUGIN_CLOUD_CERTIFICATE_REQUIRED` |
| Cloud | malformed, untrusted, invalid, or non-shared | any | reject before storage with `CERTIFIED_PLUGIN_CLOUD_CERTIFICATE_INVALID` |
| OSS | absent legacy envelope | any | admitted to the dedicated profile |
| OSS | valid envelope declaring `shared-runtime-v1` | any | selected shared profile |
| OSS | malformed or invalid declaration | false | reject with `CERTIFIED_PLUGIN_OSS_FORCE_REQUIRED` |
| OSS | malformed or invalid declaration | true | admitted to the dedicated profile |

`administrator_force` is deliberately strict: it is recognized only when the
install request carries boolean `true`. The local upload endpoint accepts the
multipart field `administrator_force=true`; GitHub and marketplace install
payloads carry the same field. The existing resource-manage authorization fence
protects those endpoints. A force never creates a Cloud dedicated fallback.

## Runtime and logs

The current Plugin Runtime control protocol has one process-wide runtime profile
per Core instance. In Cloud that existing profile is `shared`; Cloud admission
therefore prevents an archive that did not select `shared-runtime-v1` from
reaching its apply API. In OSS the existing `oss_dev` runtime remains the
dedicated compatibility profile. Core records the selected profile for every
installation so a future multi-runtime control protocol can consume it without
re-verifying an already persisted archive.

The existing public plugin-log boundary already applies the immutable
installation binding (including workspace UUID) through
`RuntimeConnectionHandler.installation_scope()` before requesting logs. This is
the actual tenant exposure boundary, so valid shared certificates use that
binding-scoped transport; Core does not invent a second log stream or expose
process-wide log output. Dedicated and invalid/legacy installations use the
same existing installation scope.

## SDK versioning

Core intentionally continues to declare `langbot-plugin==0.5.8` until the SDK
beta containing this public certification API is released. Local development
and the integration tests may install the SDK source checkout, but this Core
change does not publish or pin a prerelease.
