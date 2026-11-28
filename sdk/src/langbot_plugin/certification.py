from __future__ import annotations

import base64
import dataclasses
import hashlib
import io
import json
import struct
import zipfile
from collections.abc import Callable
from typing import Any, TypedDict

import yaml

CERTIFICATION_SCHEMA = "certified-plugin-envelope-v2"
LEGACY_CERTIFICATION_SCHEMA = "certified-plugin-envelope-v1"
MAX_ENVELOPE_COMMENT_BYTES = 16 * 1024
_MAX_MANIFEST_BYTES = 1024 * 1024
_SHA256_HEX_LENGTH = 64

Signer = Callable[[bytes], bytes]
SignatureVerifier = Callable[[bytes, bytes], bool]
KeyResolver = Callable[[str], SignatureVerifier | None]


class ManifestIdentity(TypedDict):
    author: str
    name: str
    version: str
    shared_runtime: str | None
    component_model: str | None


class EnvelopeFormatError(ValueError):
    """The ZIP comment does not contain a valid certification envelope."""


@dataclasses.dataclass(frozen=True, slots=True)
class CertificationEnvelope:
    """The signed metadata stored in a plugin archive ZIP comment."""

    schema: str
    key_id: str
    plugin_id: dict[str, str]
    version: str
    digest: str
    shared_runtime: str | None
    component_model: str | None
    signature: str

    def unsigned_dict(self) -> dict[str, Any]:
        value = {
            "schema": self.schema,
            "key_id": self.key_id,
            "plugin_id": self.plugin_id,
            "version": self.version,
            "digest": self.digest,
            "shared_runtime": self.shared_runtime,
            "component_model": self.component_model,
        }
        if self.schema == LEGACY_CERTIFICATION_SCHEMA:
            value.pop("component_model")
        return value

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "signature": self.signature}


@dataclasses.dataclass(frozen=True, slots=True)
class CertificationVerification:
    status: str
    envelope: CertificationEnvelope | None = None


def canonical_json(value: Any) -> bytes:
    """Serialize JSON as sorted, compact UTF-8 without ASCII escaping."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def normalized_zip_digest(archive: bytes) -> str:
    """SHA-256 of the archive with only its ZIP comment removed."""
    return hashlib.sha256(_without_zip_comment(archive)).hexdigest()


def create_envelope(
    archive: bytes, key_id: str, signer: Signer
) -> CertificationEnvelope:
    """Create a signed envelope bound to the archive digest and manifest identity."""
    identity = _read_manifest_identity(archive)
    if (
        identity["shared_runtime"] != "shared-runtime-v1"
        or identity["component_model"] != "stateless-v1"
    ):
        raise EnvelopeFormatError(
            "certification requires sharedRuntime shared-runtime-v1 and componentModel stateless-v1"
        )
    unsigned = CertificationEnvelope(
        schema=CERTIFICATION_SCHEMA,
        key_id=_required_string(key_id, "key_id"),
        plugin_id={"author": identity["author"], "name": identity["name"]},
        version=identity["version"],
        digest=normalized_zip_digest(archive),
        shared_runtime=identity["shared_runtime"],
        component_model=identity["component_model"],
        signature="",
    )
    return sign_envelope(unsigned, signer)


def sign_envelope(
    envelope: CertificationEnvelope, signer: Signer
) -> CertificationEnvelope:
    """Apply a caller-provided signature to the canonical unsigned envelope."""
    _validate_envelope(
        envelope, allow_unsupported_schema=False, require_signature=False
    )
    signature = signer(canonical_json(envelope.unsigned_dict()))
    if not isinstance(signature, bytes) or not signature:
        raise ValueError("signer must return non-empty bytes")
    return dataclasses.replace(
        envelope, signature=base64.b64encode(signature).decode("ascii")
    )


def read_envelope(archive: bytes) -> CertificationEnvelope | None:
    """Read the strict JSON envelope from the archive ZIP comment, if present."""
    comment = _zip_comment(archive)
    if not comment:
        return None
    if len(comment) > MAX_ENVELOPE_COMMENT_BYTES:
        raise EnvelopeFormatError("certification envelope exceeds the comment limit")
    try:
        value = json.loads(comment.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EnvelopeFormatError("certification envelope is not UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise EnvelopeFormatError("certification envelope must be a JSON object")
    schema = value.get("schema")
    legacy = schema == LEGACY_CERTIFICATION_SCHEMA
    expected_keys = {
        "schema",
        "key_id",
        "plugin_id",
        "version",
        "digest",
        "shared_runtime",
        "component_model",
        "signature",
    }
    if legacy:
        expected_keys.remove("component_model")
    if set(value) != expected_keys:
        raise EnvelopeFormatError("certification envelope fields are invalid")
    plugin_id = value["plugin_id"]
    if not isinstance(plugin_id, dict) or set(plugin_id) != {"author", "name"}:
        raise EnvelopeFormatError("certification envelope plugin_id is invalid")
    envelope = CertificationEnvelope(
        schema=value["schema"],
        key_id=value["key_id"],
        plugin_id={"author": plugin_id["author"], "name": plugin_id["name"]},
        version=value["version"],
        digest=value["digest"],
        shared_runtime=value["shared_runtime"],
        component_model=value.get("component_model"),
        signature=value["signature"],
    )
    _validate_envelope(envelope, allow_unsupported_schema=True)
    return envelope


def write_envelope(archive: bytes, envelope: CertificationEnvelope) -> bytes:
    """Write a bounded strict envelope into the archive ZIP comment."""
    if not isinstance(envelope, CertificationEnvelope):
        raise TypeError("envelope must be a CertificationEnvelope")
    _validate_envelope(envelope, allow_unsupported_schema=False)
    comment = canonical_json(envelope.to_dict())
    if len(comment) > MAX_ENVELOPE_COMMENT_BYTES:
        raise EnvelopeFormatError("certification envelope exceeds the comment limit")
    return _replace_zip_comment(archive, comment)


def verify_archive(
    archive: bytes, key_resolver: KeyResolver
) -> CertificationVerification:
    """Verify a certified plugin archive without extracting its payload."""
    try:
        envelope = read_envelope(archive)
    except (EnvelopeFormatError, ValueError, struct.error):
        return CertificationVerification("malformed")
    if envelope is None:
        return CertificationVerification("absent")
    if envelope.schema not in {CERTIFICATION_SCHEMA, LEGACY_CERTIFICATION_SCHEMA}:
        return CertificationVerification("unsupported_schema", envelope)
    if envelope.schema == CERTIFICATION_SCHEMA and (
        envelope.shared_runtime != "shared-runtime-v1"
        or envelope.component_model != "stateless-v1"
    ):
        return CertificationVerification("malformed", envelope)
    try:
        if normalized_zip_digest(archive) != envelope.digest:
            return CertificationVerification("digest_mismatch", envelope)
        identity = _read_manifest_identity(
            archive,
            allow_legacy_shared=(envelope.schema == LEGACY_CERTIFICATION_SCHEMA),
        )
    except (
        EnvelopeFormatError,
        ValueError,
        struct.error,
        zipfile.BadZipFile,
        yaml.YAMLError,
    ):
        return CertificationVerification("manifest_mismatch", envelope)
    if (
        envelope.plugin_id != {"author": identity["author"], "name": identity["name"]}
        or envelope.version != identity["version"]
        or envelope.shared_runtime != identity["shared_runtime"]
        or envelope.component_model != identity["component_model"]
    ):
        return CertificationVerification("manifest_mismatch", envelope)
    verifier = key_resolver(envelope.key_id)
    if verifier is None:
        return CertificationVerification("unknown_key", envelope)
    try:
        signature = base64.b64decode(envelope.signature.encode("ascii"), validate=True)
        valid = verifier(canonical_json(envelope.unsigned_dict()), signature)
    except (TypeError, ValueError):
        valid = False
    if valid is not True:
        return CertificationVerification("signature_invalid", envelope)
    return CertificationVerification("valid", envelope)


def _validate_envelope(
    envelope: CertificationEnvelope,
    *,
    allow_unsupported_schema: bool,
    require_signature: bool = True,
) -> None:
    if not allow_unsupported_schema and envelope.schema != CERTIFICATION_SCHEMA:
        raise EnvelopeFormatError("certification envelope schema is unsupported")
    _required_string(envelope.schema, "schema")
    _required_string(envelope.key_id, "key_id")
    if not isinstance(envelope.plugin_id, dict) or set(envelope.plugin_id) != {
        "author",
        "name",
    }:
        raise EnvelopeFormatError("certification envelope plugin_id is invalid")
    _required_string(envelope.plugin_id["author"], "plugin_id.author")
    _required_string(envelope.plugin_id["name"], "plugin_id.name")
    _required_string(envelope.version, "version")
    if (
        not isinstance(envelope.digest, str)
        or len(envelope.digest) != _SHA256_HEX_LENGTH
        or any(character not in "0123456789abcdef" for character in envelope.digest)
    ):
        raise EnvelopeFormatError("certification envelope digest is invalid")
    if envelope.shared_runtime not in {None, "shared-runtime-v1"}:
        raise EnvelopeFormatError("certification envelope shared_runtime is invalid")
    if envelope.component_model not in {None, "stateless-v1"}:
        raise EnvelopeFormatError("certification envelope component_model is invalid")
    if envelope.schema == CERTIFICATION_SCHEMA and (
        envelope.shared_runtime != "shared-runtime-v1"
        or envelope.component_model != "stateless-v1"
    ):
        raise EnvelopeFormatError(
            "certification requires shared-runtime-v1 and stateless-v1"
        )
    if (
        envelope.shared_runtime == "shared-runtime-v1"
        and envelope.component_model != "stateless-v1"
        and envelope.schema != LEGACY_CERTIFICATION_SCHEMA
    ):
        raise EnvelopeFormatError(
            "certification envelope shared runtime requires stateless-v1"
        )
    if require_signature:
        _required_string(envelope.signature, "signature")
        try:
            if not base64.b64decode(envelope.signature.encode("ascii"), validate=True):
                raise ValueError
        except (UnicodeEncodeError, ValueError) as exc:
            raise EnvelopeFormatError(
                "certification envelope signature is invalid"
            ) from exc


def _required_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EnvelopeFormatError(f"certification envelope {field_name} is invalid")
    return value


def _read_manifest_identity(
    archive: bytes,
    *,
    allow_legacy_shared: bool = False,
) -> ManifestIdentity:
    with zipfile.ZipFile(io.BytesIO(archive), "r") as package:
        manifests = [
            info for info in package.infolist() if info.filename == "manifest.yaml"
        ]
        if len(manifests) != 1 or manifests[0].file_size > _MAX_MANIFEST_BYTES:
            raise EnvelopeFormatError("plugin manifest is unavailable")
        try:
            content = package.read(manifests[0])
            manifest = yaml.safe_load(content.decode("utf-8"))
        except (UnicodeDecodeError, zipfile.BadZipFile, yaml.YAMLError) as exc:
            raise EnvelopeFormatError("plugin manifest is unavailable") from exc
    if not isinstance(manifest, dict):
        raise EnvelopeFormatError("plugin manifest is invalid")
    metadata = manifest.get("metadata")
    if not isinstance(metadata, dict):
        raise EnvelopeFormatError("plugin manifest metadata is invalid")
    execution = manifest.get("execution")
    if execution is None:
        shared_runtime = None
        component_model = None
    elif not isinstance(execution, dict):
        raise EnvelopeFormatError("plugin manifest execution is invalid")
    else:
        if "sharedRuntime" not in execution:
            shared_runtime = None
        else:
            shared_runtime = execution["sharedRuntime"]
            if shared_runtime != "shared-runtime-v1":
                raise EnvelopeFormatError("plugin manifest sharedRuntime is invalid")
        component_model = execution.get("componentModel")
        if component_model not in {None, "stateless-v1"}:
            raise EnvelopeFormatError("plugin manifest componentModel is invalid")
        if (
            shared_runtime == "shared-runtime-v1"
            and component_model != "stateless-v1"
            and not allow_legacy_shared
        ):
            raise EnvelopeFormatError(
                "plugin manifest sharedRuntime requires componentModel stateless-v1"
            )
    return {
        "author": _required_string(metadata.get("author"), "manifest metadata.author"),
        "name": _required_string(metadata.get("name"), "manifest metadata.name"),
        "version": _required_string(
            metadata.get("version"), "manifest metadata.version"
        ),
        "shared_runtime": shared_runtime,
        "component_model": component_model,
    }


def _zip_comment(archive: bytes) -> bytes:
    offset, comment_length = _locate_zip_eocd(archive)
    return archive[offset + 22 : offset + 22 + comment_length]


def _without_zip_comment(archive: bytes) -> bytes:
    offset, _ = _locate_zip_eocd(archive)
    return archive[: offset + 20] + b"\x00\x00"


def _replace_zip_comment(archive: bytes, comment: bytes) -> bytes:
    if len(comment) > 0xFFFF:
        raise EnvelopeFormatError("ZIP comment exceeds the ZIP limit")
    offset, _ = _locate_zip_eocd(archive)
    return archive[: offset + 20] + struct.pack("<H", len(comment)) + comment


def _locate_zip_eocd(archive: bytes) -> tuple[int, int]:
    if not isinstance(archive, bytes):
        raise TypeError("archive must be bytes")
    start = max(0, len(archive) - (0xFFFF + 22))
    position = archive.rfind(b"PK\x05\x06", start)
    while position >= start:
        if position + 22 <= len(archive):
            comment_length = struct.unpack_from("<H", archive, position + 20)[0]
            if position + 22 + comment_length == len(archive):
                return position, comment_length
        position = archive.rfind(b"PK\x05\x06", start, position)
    raise EnvelopeFormatError(
        "archive has no valid ZIP end-of-central-directory record"
    )
