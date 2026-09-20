"""Pure certified-plugin facts and admission policies.

This module intentionally does not verify signatures.  An SDK-backed verifier
must produce ``CertificateFacts`` from an inspected archive before admission.
"""

from __future__ import annotations

import base64
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from langbot_plugin.certification import normalized_zip_digest, verify_archive


SHARED_RUNTIME_V1 = 'shared-runtime-v1'
DEDICATED_RUNTIME = 'dedicated'


class CertificateVerification(str, Enum):
    ABSENT = 'absent'
    MALFORMED = 'malformed'
    INVALID = 'invalid'
    VALID = 'valid'


class DeploymentMode(str, Enum):
    CLOUD = 'cloud'
    OSS = 'oss'


class AdmissionDisposition(str, Enum):
    SHARED_ELIGIBLE = 'shared_eligible'
    DEDICATED_ALLOWED = 'dedicated_allowed'
    REJECTED = 'rejected'
    ADMINISTRATOR_FORCE_REQUIRED = 'administrator_force_required'


class AdmissionCode(str, Enum):
    SHARED_ELIGIBLE = 'CERTIFIED_PLUGIN_SHARED_ELIGIBLE'
    CLOUD_CERTIFICATE_REQUIRED = 'CERTIFIED_PLUGIN_CLOUD_CERTIFICATE_REQUIRED'
    CLOUD_CERTIFICATE_INVALID = 'CERTIFIED_PLUGIN_CLOUD_CERTIFICATE_INVALID'
    OSS_LEGACY_DEDICATED = 'CERTIFIED_PLUGIN_OSS_LEGACY_DEDICATED'
    OSS_FORCE_REQUIRED = 'CERTIFIED_PLUGIN_OSS_FORCE_REQUIRED'
    OSS_FORCED_DEDICATED = 'CERTIFIED_PLUGIN_OSS_FORCED_DEDICATED'
    OSS_CERTIFIED_DEDICATED = 'CERTIFIED_PLUGIN_OSS_CERTIFIED_DEDICATED'


class PluginLogVisibility(str, Enum):
    TENANT_SCOPED = 'tenant_scoped'
    DETAILED_PROCESS = 'detailed_process'


@dataclass(frozen=True)
class CertificateFacts:
    """Certificate result supplied by an archive verifier.

    ``VALID`` means the verifier has validated both the certificate and its
    binding to the immutable artifact digest in ``PluginCertificationFacts``.
    """

    verification: CertificateVerification
    runtime_profile: str | None = None
    certificate_id: str | None = None

    @property
    def is_valid_shared_runtime(self) -> bool:
        return self.verification is CertificateVerification.VALID and self.runtime_profile == SHARED_RUNTIME_V1

    @property
    def is_declared(self) -> bool:
        return self.verification is not CertificateVerification.ABSENT


@dataclass(frozen=True)
class PluginCertificationFacts:
    """Immutable Core-side facts for one plugin installation artifact."""

    installation_uuid: str
    artifact_digest: str
    certificate: CertificateFacts

    def __post_init__(self) -> None:
        if len(self.artifact_digest) != 64 or any(
            character not in '0123456789abcdef' for character in self.artifact_digest.lower()
        ):
            raise ValueError('artifact_digest must be a lowercase-or-uppercase SHA-256 hex digest')


@dataclass(frozen=True)
class VerifiedArchiveCertificate:
    """SDK verification facts bound to the comment-normalized ZIP digest."""

    normalized_digest: str
    certificate: CertificateFacts

    def for_installation(self, installation_uuid: str) -> PluginCertificationFacts:
        return PluginCertificationFacts(
            installation_uuid=installation_uuid,
            artifact_digest=self.normalized_digest,
            certificate=self.certificate,
        )


def trusted_public_key_ring(config: object) -> dict[str, Callable[[bytes, bytes], bool]]:
    """Build the non-secret Ed25519 verifier ring from instance configuration.

    ``plugin.certification.trusted_public_keys`` is a mapping of key IDs to
    standard base64-encoded 32-byte Ed25519 public keys.  Configuration errors
    are explicit so an operator never silently gets a weaker trust policy.
    """

    if config is None:
        return {}
    if not isinstance(config, Mapping):
        raise ValueError('plugin.certification.trusted_public_keys must be a mapping')

    ring: dict[str, Callable[[bytes, bytes], bool]] = {}
    for raw_key_id, raw_public_key in config.items():
        key_id = str(raw_key_id).strip()
        if not key_id or not isinstance(raw_public_key, str):
            raise ValueError('plugin.certification.trusted_public_keys entries must have string IDs and values')
        try:
            public_key_bytes = base64.b64decode(raw_public_key.encode('ascii'), validate=True)
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        except (UnicodeEncodeError, ValueError) as exc:
            raise ValueError(f'plugin.certification trusted public key {key_id!r} is invalid') from exc

        def verify(payload: bytes, signature: bytes, *, verifier: Ed25519PublicKey = public_key) -> bool:
            try:
                verifier.verify(signature, payload)
            except (InvalidSignature, TypeError, ValueError):
                return False
            return True

        ring[key_id] = verify
    return ring


def verify_plugin_archive_certificate(
    archive: bytes,
    *,
    trusted_public_keys: object,
) -> VerifiedArchiveCertificate:
    """Use the SDK ZIP-comment API and retain its normalized-digest binding."""

    verification = verify_archive(archive, trusted_public_key_ring(trusted_public_keys).get)
    envelope = verification.envelope
    runtime_profile = envelope.shared_runtime if envelope is not None else None
    certificate_id = envelope.key_id if envelope is not None else None
    state = {
        'absent': CertificateVerification.ABSENT,
        'malformed': CertificateVerification.MALFORMED,
        'valid': CertificateVerification.VALID,
    }.get(verification.status, CertificateVerification.INVALID)
    return VerifiedArchiveCertificate(
        normalized_digest=normalized_zip_digest(archive),
        certificate=CertificateFacts(
            verification=state,
            runtime_profile=runtime_profile,
            certificate_id=certificate_id,
        ),
    )


@dataclass(frozen=True)
class PluginAdmissionDecision:
    disposition: AdmissionDisposition
    code: AdmissionCode
    runtime_profile: str


def decide_plugin_admission(
    *,
    deployment: DeploymentMode | str,
    facts: PluginCertificationFacts,
    administrator_force: bool = False,
) -> PluginAdmissionDecision:
    """Apply Cloud fail-closed and OSS administrator-force admission rules."""

    mode = DeploymentMode(deployment)
    certificate = facts.certificate
    if certificate.is_valid_shared_runtime:
        return PluginAdmissionDecision(
            AdmissionDisposition.SHARED_ELIGIBLE,
            AdmissionCode.SHARED_ELIGIBLE,
            SHARED_RUNTIME_V1,
        )

    if mode is DeploymentMode.CLOUD:
        code = (
            AdmissionCode.CLOUD_CERTIFICATE_REQUIRED
            if certificate.verification is CertificateVerification.ABSENT
            else AdmissionCode.CLOUD_CERTIFICATE_INVALID
        )
        return PluginAdmissionDecision(AdmissionDisposition.REJECTED, code, DEDICATED_RUNTIME)

    if certificate.verification is CertificateVerification.ABSENT:
        return PluginAdmissionDecision(
            AdmissionDisposition.DEDICATED_ALLOWED,
            AdmissionCode.OSS_LEGACY_DEDICATED,
            DEDICATED_RUNTIME,
        )

    if certificate.verification is CertificateVerification.VALID:
        return PluginAdmissionDecision(
            AdmissionDisposition.DEDICATED_ALLOWED,
            AdmissionCode.OSS_CERTIFIED_DEDICATED,
            DEDICATED_RUNTIME,
        )

    if administrator_force:
        return PluginAdmissionDecision(
            AdmissionDisposition.DEDICATED_ALLOWED,
            AdmissionCode.OSS_FORCED_DEDICATED,
            DEDICATED_RUNTIME,
        )

    return PluginAdmissionDecision(
        AdmissionDisposition.ADMINISTRATOR_FORCE_REQUIRED,
        AdmissionCode.OSS_FORCE_REQUIRED,
        DEDICATED_RUNTIME,
    )


def decide_plugin_log_visibility(facts: PluginCertificationFacts) -> PluginLogVisibility:
    """Select the minimum log visibility compatible with a verified shared runtime."""

    if facts.certificate.is_valid_shared_runtime:
        return PluginLogVisibility.TENANT_SCOPED
    return PluginLogVisibility.DETAILED_PROCESS
