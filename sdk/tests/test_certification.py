from __future__ import annotations

import dataclasses
import base64
import hashlib
import hmac
import io
import zipfile

import pytest
import yaml

from langbot_plugin.certification import (
    CertificationEnvelope,
    EnvelopeFormatError,
    canonical_json,
    create_envelope,
    normalized_zip_digest,
    read_envelope,
    sign_envelope,
    verify_archive,
    write_envelope,
)


_TEST_SIGNING_MATERIAL = b"test-only-certification-key"
_MISSING = object()


def _plugin_archive(*, shared_runtime: str | None | object = _MISSING) -> bytes:
    manifest = {
        "apiVersion": "v1",
        "kind": "Plugin",
        "metadata": {
            "author": "certifier",
            "name": "demo",
            "label": {"en_US": "Demo"},
            "version": "1.2.3",
        },
        "spec": {"components": {}},
        "execution": {"python": {"path": "main.py", "attr": "Plugin"}},
    }
    if shared_runtime is not _MISSING:
        manifest["execution"]["sharedRuntime"] = shared_runtime
        if shared_runtime == "shared-runtime-v1":
            manifest["execution"]["componentModel"] = "stateless-v1"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("manifest.yaml", yaml.safe_dump(manifest, sort_keys=False))
        archive.writestr("main.py", "print('plugin')\n")
    return output.getvalue()


def _sign(payload: bytes) -> bytes:
    return hmac.new(_TEST_SIGNING_MATERIAL, payload, hashlib.sha256).digest()


def _resolve(key_id: str):
    if key_id != "test-key":
        return None
    return lambda payload, signature: hmac.compare_digest(_sign(payload), signature)


def _certified_archive(archive: bytes) -> bytes:
    return write_envelope(archive, create_envelope(archive, "test-key", _sign))


def _with_comment(archive: bytes, comment: bytes) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(archive), "r") as source:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as target:
            for info in source.infolist():
                target.writestr(info, source.read(info))
            target.comment = comment
    return output.getvalue()


def test_canonical_json_is_sorted_compact_and_utf8():
    assert canonical_json({"z": "雪", "a": [2, 1]}) == b'{"a":[2,1],"z":"\xe9\x9b\xaa"}'


def test_legacy_archive_without_comment_is_not_certified():
    archive = _plugin_archive()

    assert read_envelope(archive) is None
    assert verify_archive(archive, _resolve).status == "absent"


def test_certificate_creation_rejects_an_explicit_null_shared_runtime():
    with pytest.raises(EnvelopeFormatError, match="sharedRuntime"):
        create_envelope(_plugin_archive(shared_runtime=None), "test-key", _sign)


def test_certificate_creation_rejects_dedicated_manifest():
    with pytest.raises(EnvelopeFormatError, match="sharedRuntime"):
        create_envelope(_plugin_archive(), "test-key", _sign)


def test_legacy_v2_dedicated_signature_is_not_valid_certification():
    archive = _plugin_archive()
    unsigned = {
        "schema": "certified-plugin-envelope-v2",
        "key_id": "test-key",
        "plugin_id": {"author": "certifier", "name": "demo"},
        "version": "1.2.3",
        "digest": normalized_zip_digest(archive),
        "shared_runtime": None,
        "component_model": None,
    }
    signed = {
        **unsigned,
        "signature": base64.b64encode(_sign(canonical_json(unsigned))).decode("ascii"),
    }
    assert (
        verify_archive(_with_comment(archive, canonical_json(signed)), _resolve).status
        != "valid"
    )


def test_valid_signed_envelope_binds_shared_runtime_and_manifest_identity():
    archive = _plugin_archive(shared_runtime="shared-runtime-v1")
    certified = _certified_archive(archive)

    result = verify_archive(certified, _resolve)

    assert result.status == "valid"
    assert result.envelope is not None
    assert result.envelope.plugin_id == {"author": "certifier", "name": "demo"}
    assert result.envelope.version == "1.2.3"
    assert result.envelope.shared_runtime == "shared-runtime-v1"
    assert result.envelope.component_model == "stateless-v1"
    assert result.envelope.digest == normalized_zip_digest(certified)


def test_legacy_v1_envelope_remains_verifiable_but_has_no_stateless_claim():
    archive = _plugin_archive(shared_runtime="shared-runtime-v1")
    # Rebuild a legacy manifest and exact legacy seven-field signed envelope.
    with zipfile.ZipFile(io.BytesIO(archive), "r") as source:
        manifest = yaml.safe_load(source.read("manifest.yaml"))
    manifest["execution"].pop("componentModel")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as target:
        target.writestr("manifest.yaml", yaml.safe_dump(manifest, sort_keys=False))
        target.writestr("main.py", "print('plugin')\n")
    legacy_archive = output.getvalue()
    unsigned = {
        "schema": "certified-plugin-envelope-v1",
        "key_id": "test-key",
        "plugin_id": {"author": "certifier", "name": "demo"},
        "version": "1.2.3",
        "digest": normalized_zip_digest(legacy_archive),
        "shared_runtime": "shared-runtime-v1",
    }
    signed = {
        **unsigned,
        "signature": base64.b64encode(_sign(canonical_json(unsigned))).decode("ascii"),
    }

    result = verify_archive(
        _with_comment(legacy_archive, canonical_json(signed)), _resolve
    )

    assert result.status == "valid"
    assert result.envelope is not None
    assert result.envelope.component_model is None


def test_archive_byte_tamper_reports_digest_mismatch():
    certified = _certified_archive(_plugin_archive(shared_runtime="shared-runtime-v1"))
    tampered = certified.replace(b"print('plugin')", b"print('tamper')", 1)

    assert verify_archive(tampered, _resolve).status == "digest_mismatch"


def test_envelope_comment_tamper_reports_signature_invalid():
    certified = _certified_archive(_plugin_archive(shared_runtime="shared-runtime-v1"))
    envelope = read_envelope(certified)
    assert envelope is not None
    tampered = write_envelope(
        certified,
        dataclasses.replace(envelope, signature="A" * len(envelope.signature)),
    )

    assert verify_archive(tampered, _resolve).status == "signature_invalid"


def test_unknown_signing_key_is_reported():
    certified = _certified_archive(_plugin_archive(shared_runtime="shared-runtime-v1"))

    assert verify_archive(certified, lambda _key_id: None).status == "unknown_key"


def test_manifest_mismatch_is_reported_after_a_valid_signature():
    archive = _plugin_archive(shared_runtime="shared-runtime-v1")
    envelope = create_envelope(archive, "test-key", _sign)
    mismatched = CertificationEnvelope(
        schema=envelope.schema,
        key_id=envelope.key_id,
        plugin_id={"author": "certifier", "name": "other"},
        version=envelope.version,
        digest=envelope.digest,
        shared_runtime=envelope.shared_runtime,
        component_model=envelope.component_model,
        signature="",
    )
    certified = write_envelope(archive, sign_envelope(mismatched, _sign))

    assert verify_archive(certified, _resolve).status == "manifest_mismatch"


def test_normalized_digest_ignores_zip_comment():
    archive = _plugin_archive(shared_runtime="shared-runtime-v1")
    comment_one = write_envelope(archive, create_envelope(archive, "test-key", _sign))
    envelope = read_envelope(comment_one)
    assert envelope is not None
    comment_two = write_envelope(
        comment_one,
        dataclasses.replace(envelope, signature="B" * len(envelope.signature)),
    )

    assert normalized_zip_digest(archive) == normalized_zip_digest(comment_one)
    assert normalized_zip_digest(comment_one) == normalized_zip_digest(comment_two)


def test_write_refuses_an_unsupported_schema():
    archive = _plugin_archive(shared_runtime="shared-runtime-v1")
    envelope = create_envelope(archive, "test-key", _sign)

    with pytest.raises(EnvelopeFormatError, match="unsupported"):
        write_envelope(
            archive,
            dataclasses.replace(envelope, schema="certified-plugin-envelope-v3"),
        )


@pytest.mark.parametrize(
    ("comment", "status"),
    [
        (b"not-json", "malformed"),
        (
            canonical_json(
                {
                    "schema": "certified-plugin-envelope-v3",
                    "key_id": "test-key",
                    "plugin_id": {"author": "certifier", "name": "demo"},
                    "version": "1.2.3",
                    "digest": "0" * 64,
                    "shared_runtime": None,
                    "component_model": None,
                    "signature": "AA==",
                }
            ),
            "unsupported_schema",
        ),
    ],
)
def test_invalid_or_future_envelope_statuses(comment, status):
    archive = _plugin_archive()
    with_comment = _with_comment(archive, comment)

    assert verify_archive(with_comment, _resolve).status == status
