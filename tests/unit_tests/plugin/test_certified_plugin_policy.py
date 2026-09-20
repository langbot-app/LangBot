from __future__ import annotations

import hashlib
import io
import zipfile

import pytest


@pytest.mark.parametrize(
    ('deployment', 'certificate', 'force', 'expected_disposition', 'expected_code'),
    [
        ('cloud', ('valid', 'shared-runtime-v1'), False, 'shared_eligible', 'CERTIFIED_PLUGIN_SHARED_ELIGIBLE'),
        ('cloud', ('absent', None), False, 'rejected', 'CERTIFIED_PLUGIN_CLOUD_CERTIFICATE_REQUIRED'),
        ('cloud', ('malformed', None), False, 'rejected', 'CERTIFIED_PLUGIN_CLOUD_CERTIFICATE_INVALID'),
        ('cloud', ('invalid', 'shared-runtime-v1'), True, 'rejected', 'CERTIFIED_PLUGIN_CLOUD_CERTIFICATE_INVALID'),
        ('oss', ('absent', None), False, 'dedicated_allowed', 'CERTIFIED_PLUGIN_OSS_LEGACY_DEDICATED'),
        ('oss', ('valid', 'shared-runtime-v1'), False, 'shared_eligible', 'CERTIFIED_PLUGIN_SHARED_ELIGIBLE'),
        ('oss', ('invalid', 'shared-runtime-v1'), False, 'administrator_force_required', 'CERTIFIED_PLUGIN_OSS_FORCE_REQUIRED'),
        ('oss', ('invalid', 'shared-runtime-v1'), True, 'dedicated_allowed', 'CERTIFIED_PLUGIN_OSS_FORCED_DEDICATED'),
    ],
)
def test_admission_policy_enforces_certification_matrix(
    deployment: str,
    certificate: tuple[str, str | None],
    force: bool,
    expected_disposition: str,
    expected_code: str,
) -> None:
    from langbot.pkg.plugin.certification import (
        CertificateFacts,
        CertificateVerification,
        PluginCertificationFacts,
        decide_plugin_admission,
    )

    verification, runtime_profile = certificate
    facts = PluginCertificationFacts(
        installation_uuid='00000000-0000-4000-8000-000000000001',
        artifact_digest='a' * 64,
        certificate=CertificateFacts(
            verification=CertificateVerification(verification),
            runtime_profile=runtime_profile,
        ),
    )

    decision = decide_plugin_admission(
        deployment=deployment,
        facts=facts,
        administrator_force=force,
    )

    assert decision.disposition.value == expected_disposition
    assert decision.code.value == expected_code
    assert decision.runtime_profile == (
        'shared-runtime-v1' if expected_disposition == 'shared_eligible' else 'dedicated'
    )


def test_archive_inspection_preserves_legacy_tuple_and_exposes_certificate_facts() -> None:
    from langbot.pkg.plugin.archive import (
        ArchiveCertificateState,
        inspect_plugin_archive,
        inspect_plugin_archive_metadata,
    )

    manifest = {
        'kind': 'Plugin',
        'metadata': {'name': 'example'},
        'certification': {
            'runtime_profile': 'shared-runtime-v1',
            'certificate': {'issuer': 'sdk-test', 'signature': 'not-verified-by-core'},
        },
    }
    archive_bytes = _archive_bytes(manifest)

    inspection = inspect_plugin_archive(archive_bytes)

    assert inspection.artifact_digest == hashlib.sha256(archive_bytes).hexdigest()
    assert inspection.certificate.state is ArchiveCertificateState.DECLARED
    assert inspection.certificate.runtime_profile == 'shared-runtime-v1'
    assert inspection.certificate.payload == manifest['certification']['certificate']
    assert inspect_plugin_archive_metadata(archive_bytes) == (
        inspection.manifest,
        inspection.requirements,
        inspection.names,
    )


@pytest.mark.parametrize(
    ('certification', 'expected_state'),
    [
        (None, 'absent'),
        ({'runtime_profile': 123, 'certificate': {}}, 'malformed'),
        ({'runtime_profile': 'shared-runtime-v1'}, 'malformed'),
    ],
)
def test_archive_inspection_reports_nonverifying_certificate_states(
    certification: object,
    expected_state: str,
) -> None:
    from langbot.pkg.plugin.archive import inspect_plugin_archive

    manifest: dict[str, object] = {'kind': 'Plugin', 'metadata': {'name': 'example'}}
    if certification is not None:
        manifest['certification'] = certification

    inspection = inspect_plugin_archive(_archive_bytes(manifest))

    assert inspection.certificate.state.value == expected_state


@pytest.mark.parametrize(
    ('verification', 'expected_visibility'),
    [
        ('valid', 'tenant_scoped'),
        ('absent', 'detailed_process'),
        ('malformed', 'detailed_process'),
        ('invalid', 'detailed_process'),
    ],
)
def test_log_visibility_policy_only_scopes_valid_shared_certifications(
    verification: str,
    expected_visibility: str,
) -> None:
    from langbot.pkg.plugin.certification import (
        CertificateFacts,
        CertificateVerification,
        PluginCertificationFacts,
        decide_plugin_log_visibility,
    )

    facts = PluginCertificationFacts(
        installation_uuid='00000000-0000-4000-8000-000000000001',
        artifact_digest='a' * 64,
        certificate=CertificateFacts(
            verification=CertificateVerification(verification),
            runtime_profile='shared-runtime-v1',
        ),
    )

    visibility = decide_plugin_log_visibility(facts)

    assert visibility.value == expected_visibility


def _archive_bytes(manifest: dict[str, object]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        import yaml

        archive.writestr('manifest.yaml', yaml.safe_dump(manifest))
    return buffer.getvalue()
