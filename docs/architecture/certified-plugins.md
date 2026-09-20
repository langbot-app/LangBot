# Certified Plugins

## Scope

Core now owns the pure, fail-closed policy boundary for certified plugin
admission and log visibility. It does **not** implement archive signature
verification or alter process/runtime plumbing. The SDK verifier remains the
future authority for certificate cryptography, issuer trust, and the binding of
a certificate to an archive digest.

## Archive facts

`langbot.pkg.plugin.archive.inspect_plugin_archive()` returns a
`PluginArchiveInspection` with the immutable SHA-256 `artifact_digest` and a
bounded certificate declaration parsed from `manifest.yaml`:

```yaml
certification:
  runtime_profile: shared-runtime-v1
  certificate:
    # SDK-owned certificate payload
```

Its certificate state is syntactic only:

| State | Meaning |
| --- | --- |
| `absent` | No `certification` declaration exists. |
| `malformed` | The declaration lacks a non-empty `runtime_profile` or an object `certificate`. |
| `declared` | The declaration can be passed to an SDK verifier; it is not trusted yet. |

`inspect_plugin_archive_metadata()` deliberately preserves its legacy
`(manifest, requirements, names)` tuple. New callers that need certification
facts must use `inspect_plugin_archive()`.

## Verifier handoff

The SDK verifier should convert an archive declaration into Core's
`CertificateFacts` and bind it to the same immutable `artifact_digest` and
`installation_uuid` in `PluginCertificationFacts`.

`CertificateVerification.VALID` has a strict meaning: the verifier validated
the certificate, trusted issuer, declared profile, and artifact-digest binding.
Core never promotes `declared` to `valid` itself. A malformed declaration maps
to `MALFORMED`; a failed verifier result maps to `INVALID`.

## Admission compatibility matrix

| Deployment | Certificate result | Administrator force | Decision | Stable code |
| --- | --- | --- | --- | --- |
| Cloud | valid `shared-runtime-v1` | any | shared eligible | `CERTIFIED_PLUGIN_SHARED_ELIGIBLE` |
| Cloud | absent | any | reject; no dedicated fallback | `CERTIFIED_PLUGIN_CLOUD_CERTIFICATE_REQUIRED` |
| Cloud | malformed, invalid, or another profile | any | reject; no dedicated fallback | `CERTIFIED_PLUGIN_CLOUD_CERTIFICATE_INVALID` |
| OSS | absent | any | dedicated allowed (legacy compatibility) | `CERTIFIED_PLUGIN_OSS_LEGACY_DEDICATED` |
| OSS | valid `shared-runtime-v1` | any | shared eligible | `CERTIFIED_PLUGIN_SHARED_ELIGIBLE` |
| OSS | valid non-shared profile | any | dedicated allowed | `CERTIFIED_PLUGIN_OSS_CERTIFIED_DEDICATED` |
| OSS | malformed or invalid | false | require explicit administrator force | `CERTIFIED_PLUGIN_OSS_FORCE_REQUIRED` |
| OSS | malformed or invalid | true | dedicated allowed | `CERTIFIED_PLUGIN_OSS_FORCED_DEDICATED` |

The pure policy is `decide_plugin_admission()`. A force flag can never admit a
Cloud plugin or create a Cloud dedicated-runtime fallback.

## Tenant log visibility

`decide_plugin_log_visibility()` returns `tenant_scoped` only for a valid
`shared-runtime-v1` certificate. Every other certificate state and profile uses
`detailed_process`. This is a policy decision only; existing log transport and
process plumbing remain unchanged.

## Persistence and runtime wiring

No `PluginSetting` certification columns or Alembic revision are introduced in
this foundation. No existing install/apply path yet produces verified facts or
consumes an admission decision, so persisting unenforced facts would create
ambiguous state. When SDK wiring lands, add additive `PluginSetting` fields and
a matching Alembic migration in the same change that writes and reads them.

## SDK wiring still required

1. Have the SDK emit and verify the certificate payload and artifact-digest
   binding.
2. Map the verifier result to `CertificateFacts` at the existing archive
   install/apply boundary.
3. Persist those facts atomically with the plugin artifact when a real
   `PluginSetting` reader/writer consumes them.
4. Call `decide_plugin_admission()` before selecting a runtime, and pass
   `decide_plugin_log_visibility()` into the log emission boundary.
5. Add integration coverage for the SDK-to-Core handoff and runtime behavior.
