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
from langbot_plugin.entities.io.context import PluginExecutionMode


SHARED_RUNTIME_V1 = 'shared-runtime-v1'
STATELESS_COMPONENT_MODEL_V1 = 'stateless-v1'
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
    UNSIGNED_DEDICATED = 'CERTIFIED_PLUGIN_UNSIGNED_DEDICATED'
    CLOUD_CERTIFICATE_INVALID = 'CERTIFIED_PLUGIN_CLOUD_CERTIFICATE_INVALID'
    OSS_LEGACY_DEDICATED = 'CERTIFIED_PLUGIN_OSS_LEGACY_DEDICATED'
    OSS_FORCE_REQUIRED = 'CERTIFIED_PLUGIN_OSS_FORCE_REQUIRED'
    OSS_FORCED_DEDICATED = 'CERTIFIED_PLUGIN_OSS_FORCED_DEDICATED'
    OSS_UNTRUSTED_DEDICATED = 'CERTIFIED_PLUGIN_OSS_UNTRUSTED_DEDICATED'


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
    component_model: str | None = None
    certificate_id: str | None = None

    @property
    def is_valid_shared_runtime(self) -> bool:
        return (
            self.verification is CertificateVerification.VALID
            and self.runtime_profile == SHARED_RUNTIME_V1
            and self.component_model == STATELESS_COMPONENT_MODEL_V1
        )

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

    key_ring = trusted_public_key_ring(trusted_public_keys)
    verification = verify_archive(archive, key_ring.get)
    envelope = verification.envelope
    runtime_profile = envelope.shared_runtime if envelope is not None else None
    component_model = envelope.component_model if envelope is not None else None
    # Record the issuer identity only when this instance actually resolved it
    # through the configured ring. When the ring is empty (for example a
    # self-hosted deployment that never configured
    # ``plugin.certification.trusted_public_keys``) the declaration is
    # unresolvable rather than rejected, so ``certificate_id`` stays unset and
    # admission can degrade to the dedicated profile instead of blocking.
    certificate_id = envelope.key_id if envelope is not None and envelope.key_id in key_ring else None
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
            component_model=component_model,
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
    """Only verified cross-tenant certificates grant shared placement."""

    mode = DeploymentMode(deployment)
    certificate = facts.certificate
    if mode is DeploymentMode.CLOUD and certificate.is_valid_shared_runtime:
        return PluginAdmissionDecision(
            AdmissionDisposition.SHARED_ELIGIBLE,
            AdmissionCode.SHARED_ELIGIBLE,
            SHARED_RUNTIME_V1,
        )

    if certificate.verification is CertificateVerification.ABSENT:
        return PluginAdmissionDecision(
            AdmissionDisposition.DEDICATED_ALLOWED,
            AdmissionCode.UNSIGNED_DEDICATED if mode is DeploymentMode.CLOUD else AdmissionCode.OSS_LEGACY_DEDICATED,
            DEDICATED_RUNTIME,
        )

    # OSS has no cross-tenant shared placement; a verified claim stays dedicated
    # there without inventing a dedicated certification tier.
    if mode is DeploymentMode.OSS and certificate.is_valid_shared_runtime:
        return PluginAdmissionDecision(
            AdmissionDisposition.DEDICATED_ALLOWED,
            AdmissionCode.OSS_UNTRUSTED_DEDICATED,
            DEDICATED_RUNTIME,
        )

    if mode is DeploymentMode.CLOUD:
        return PluginAdmissionDecision(
            AdmissionDisposition.REJECTED, AdmissionCode.CLOUD_CERTIFICATE_INVALID, DEDICATED_RUNTIME
        )

    # A self-hosted deployment that has not configured the issuer key ring cannot
    # verify a marketplace archive's declaration. Falling back to the dedicated
    # runtime (rather than blocking the install) is not a privilege escalation:
    # the certificate is signed by an issuer this instance does not declare
    # trusted, so no shared-runtime privilege may be granted. Shared-runtime
    # isolation is therefore refused while the existing OSS dedicated profile
    # keeps the install working. Cloud remains fail-closed above.
    if not trusted_issuer_configured(facts):
        return PluginAdmissionDecision(
            AdmissionDisposition.DEDICATED_ALLOWED,
            AdmissionCode.OSS_UNTRUSTED_DEDICATED,
            DEDICATED_RUNTIME,
        )

    # The key ring is configured, yet the declaration still failed to verify
    # (malformed, signature mismatch, unsupported schema, ...). Surface that as
    # an explicit decision instead of silently degrading.
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


def trusted_issuer_configured(facts: PluginCertificationFacts) -> bool:
    """Report whether the deployment holds a trusted issuer key for this archive.

    ``CertificateFacts`` records the verifying key only when it was resolved
    through the configured ring, so an unresolvable declaration (``unknown_key``)
    leaves ``certificate_id`` unset. That distinguishes "this operator never
    configured the issuer" from "a configured trust decision rejected the
    archive".
    """

    return bool((facts.certificate.certificate_id or '').strip())


def decide_plugin_log_visibility(facts: PluginCertificationFacts) -> PluginLogVisibility:
    """Select the minimum log visibility compatible with a verified shared runtime."""

    if facts.certificate.is_valid_shared_runtime:
        return PluginLogVisibility.TENANT_SCOPED
    return PluginLogVisibility.DETAILED_PROCESS


def execution_mode_for_persisted_installation(
    *,
    artifact_digest: str,
    install_info: object,
) -> PluginExecutionMode:
    """Derive placement only from persisted facts bound to the exact artifact."""

    if len(artifact_digest) != 64 or any(character not in '0123456789abcdef' for character in artifact_digest.lower()):
        return PluginExecutionMode.DEDICATED
    if not isinstance(install_info, Mapping):
        return PluginExecutionMode.DEDICATED
    certification = install_info.get('_certification')
    if not isinstance(certification, Mapping):
        return PluginExecutionMode.DEDICATED
    normalized_digest = certification.get('normalized_digest')
    if not isinstance(normalized_digest, str) or len(normalized_digest) != 64:
        return PluginExecutionMode.DEDICATED
    if any(character not in '0123456789abcdef' for character in normalized_digest.lower()):
        return PluginExecutionMode.DEDICATED
    certificate_id = certification.get('certificate_id')
    if not isinstance(certificate_id, str) or not certificate_id.strip():
        return PluginExecutionMode.DEDICATED
    shared_facts = {
        'artifact_digest': artifact_digest,
        'verification': CertificateVerification.VALID.value,
        'certificate_runtime_profile': SHARED_RUNTIME_V1,
        'certificate_component_model': STATELESS_COMPONENT_MODEL_V1,
        'runtime_profile': SHARED_RUNTIME_V1,
        'admission_code': AdmissionCode.SHARED_ELIGIBLE.value,
    }
    if all(certification.get(key) == value for key, value in shared_facts.items()):
        return PluginExecutionMode.SHARED_CERTIFIED
    return PluginExecutionMode.DEDICATED
