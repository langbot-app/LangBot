"""Pure certified-plugin facts and admission policies.

This module intentionally does not verify signatures.  An SDK-backed verifier
must produce ``CertificateFacts`` from an inspected archive before admission.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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
        if len(self.artifact_digest) != 64 or any(character not in '0123456789abcdef' for character in self.artifact_digest.lower()):
            raise ValueError('artifact_digest must be a lowercase-or-uppercase SHA-256 hex digest')


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
