# Certified Plugin Archives

`langbot_plugin.certification` provides an opt-in archive certification format **only for Cloud cross-tenant sharing of the same Worker and the same plugin/component singleton**. It does not change `lbp build` output: unsigned `.lbpkg` archives retain an empty ZIP comment and verify as `absent`; Cloud installs them on dedicated Workers. There is no dedicated certificate or intermediate trust tier.

## Manifest runtime profile

A plugin manifest may opt into the certified shared-runtime profile only with:

```yaml
execution:
  python:
    path: main.py
    attr: Plugin
  sharedRuntime: shared-runtime-v1
  componentModel: stateless-v1
```

If `execution.sharedRuntime` is absent, the manifest remains a dedicated-runtime manifest. `shared-runtime-v1` requires `componentModel: stateless-v1`; this declares the [stateless singleton component contract](stateless-components.md). Legacy per-installation object behavior remains compatible on dedicated workers but is not certifiable.

## Envelope format

The envelope is compact, sorted UTF-8 JSON in the ZIP comment. New stateless certificates use `certified-plugin-envelope-v2` with exactly these fields. Legacy v1 envelopes remain readable and verifiable, but have no signed `component_model` and cannot authorize shared singleton placement.

```json
{
  "schema": "certified-plugin-envelope-v2",
  "key_id": "issuer-key-id",
  "plugin_id": {"author": "publisher", "name": "plugin"},
  "version": "1.2.3",
  "digest": "lowercase-sha256-hex",
  "shared_runtime": "shared-runtime-v1",
  "component_model": "stateless-v1",
  "signature": "base64-signature"
}
```

New v2 envelopes require `shared_runtime: shared-runtime-v1` and `component_model: stateless-v1`. Dedicated manifests must remain unsigned; historical v2 envelopes with null claims do not verify as certification. Older v1 schemas may carry null claims, but cannot grant Cloud sharing or be treated as unsigned. The digest is SHA-256 of the original ZIP bytes with only its ZIP comment removed, so adding or replacing the envelope does not change the signed digest. ZIP comments are limited to 16 KiB; archive manifests are read without extraction and limited to 1 MiB.

## Signing and verification

The module is algorithm-neutral and does not add a cryptography dependency. Supply the signing callback and a trusted-key resolver from the deployment that owns issuer keys. Cloud issuers use Ed25519. OSS ships without a built-in issuer public key, supports one Workspace, and does not support configuring a certification key or shared-certified execution. Do not use the test-only HMAC pattern as a trust boundary.

```python
from langbot_plugin.certification import create_envelope, verify_archive, write_envelope

# signer(payload: bytes) -> bytes signs with the issuer's private key.
envelope = create_envelope(archive_bytes, "issuer-key-id", signer)
certified_archive = write_envelope(archive_bytes, envelope)

# key_resolver(key_id) -> verifier | None, where verifier(payload, signature) -> bool.
result = verify_archive(certified_archive, key_resolver)
if result.status != "valid":
    raise ValueError(result.status)
```

Verification binds the envelope's `plugin_id.author`, `plugin_id.name`, `version`, normalized digest, `shared_runtime`, and `component_model` to `manifest.yaml`. Legacy v1 signatures can still verify cryptographically but never grant singleton sharing because they lack the signed `stateless-v1` claim. Malformed or untrusted signatures are not unsigned archives and Cloud must reject them. Verification alone is not placement: compare the exact downloaded artifact, public version record and deployed Core trust ring. A reviewed source candidate, `issued` badge, or shared code/dependency tree does not prove a live shared Worker.

## Verification statuses

- `absent`: no ZIP comment; legacy archive.
- `valid`: envelope, signature, digest, and manifest bindings all match.
- `malformed`: invalid ZIP comment or malformed envelope.
- `unknown_key`: the configured resolver does not trust `key_id`.
- `signature_invalid`: the trusted key rejected the envelope signature.
- `digest_mismatch`: archive bytes outside the ZIP comment changed.
- `manifest_mismatch`: the signed identity or runtime profile differs from `manifest.yaml`.
- `unsupported_schema`: a well-formed envelope uses an unsupported schema.
