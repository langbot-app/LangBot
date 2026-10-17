from __future__ import annotations

import hashlib
import io
import zipfile

import pytest

from langbot_plugin.entities.io.context import PluginExecutionMode


@pytest.mark.parametrize(
    ('deployment', 'certificate', 'certificate_id', 'force', 'expected_disposition', 'expected_code'),
    [
        (
            'cloud',
            ('valid', 'shared-runtime-v1'),
            'issuer',
            False,
            'shared_eligible',
            'CERTIFIED_PLUGIN_SHARED_ELIGIBLE',
        ),
        ('cloud', ('absent', None), None, False, 'dedicated_allowed', 'CERTIFIED_PLUGIN_UNSIGNED_DEDICATED'),
        ('cloud', ('absent', None), None, True, 'dedicated_allowed', 'CERTIFIED_PLUGIN_UNSIGNED_DEDICATED'),
        ('cloud', ('malformed', None), None, False, 'rejected', 'CERTIFIED_PLUGIN_CLOUD_CERTIFICATE_INVALID'),
        (
            'cloud',
            ('invalid', 'shared-runtime-v1'),
            'issuer',
            True,
            'rejected',
            'CERTIFIED_PLUGIN_CLOUD_CERTIFICATE_INVALID',
        ),
        ('oss', ('absent', None), None, False, 'dedicated_allowed', 'CERTIFIED_PLUGIN_OSS_LEGACY_DEDICATED'),
        (
            'oss',
            ('valid', 'shared-runtime-v1'),
            'issuer',
            False,
            'dedicated_allowed',
            'CERTIFIED_PLUGIN_OSS_UNTRUSTED_DEDICATED',
        ),
        (
            'oss',
            ('invalid', 'shared-runtime-v1'),
            'issuer',
            False,
            'administrator_force_required',
            'CERTIFIED_PLUGIN_OSS_FORCE_REQUIRED',
        ),
        (
            'oss',
            ('invalid', 'shared-runtime-v1'),
            'issuer',
            True,
            'dedicated_allowed',
            'CERTIFIED_PLUGIN_OSS_FORCED_DEDICATED',
        ),
        # A declaration the operator cannot resolve (no trusted key ring configured)
        # must keep the OSS install working on the dedicated profile instead of
        # blocking every certified marketplace package.
        (
            'oss',
            ('invalid', 'shared-runtime-v1'),
            None,
            False,
            'dedicated_allowed',
            'CERTIFIED_PLUGIN_OSS_UNTRUSTED_DEDICATED',
        ),
        (
            'oss',
            ('invalid', 'shared-runtime-v1'),
            None,
            True,
            'dedicated_allowed',
            'CERTIFIED_PLUGIN_OSS_UNTRUSTED_DEDICATED',
        ),
        ('oss', ('malformed', None), None, False, 'dedicated_allowed', 'CERTIFIED_PLUGIN_OSS_UNTRUSTED_DEDICATED'),
    ],
)
def test_admission_policy_enforces_certification_matrix(
    deployment: str,
    certificate: tuple[str, str | None],
    certificate_id: str | None,
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
            component_model=(
                'stateless-v1' if verification == 'valid' and runtime_profile == 'shared-runtime-v1' else None
            ),
            certificate_id=certificate_id,
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


def test_legacy_shared_certificate_without_stateless_contract_is_not_shared() -> None:
    from langbot.pkg.plugin.certification import (
        AdmissionDisposition,
        CertificateFacts,
        CertificateVerification,
        DeploymentMode,
        PluginCertificationFacts,
        decide_plugin_admission,
    )

    decision = decide_plugin_admission(
        deployment=DeploymentMode.CLOUD,
        facts=PluginCertificationFacts(
            installation_uuid='00000000-0000-4000-8000-000000000001',
            artifact_digest='a' * 64,
            certificate=CertificateFacts(
                verification=CertificateVerification.VALID,
                runtime_profile='shared-runtime-v1',
                component_model=None,
                certificate_id='legacy-issuer',
            ),
        ),
    )

    assert decision.disposition is AdmissionDisposition.REJECTED


def test_oss_never_selects_shared_even_with_a_resolved_valid_certificate() -> None:
    from langbot.pkg.plugin.certification import (
        CertificateFacts,
        CertificateVerification,
        PluginCertificationFacts,
        decide_plugin_admission,
    )

    facts = PluginCertificationFacts(
        'installation',
        'a' * 64,
        CertificateFacts(
            CertificateVerification.VALID,
            'shared-runtime-v1',
            'stateless-v1',
            'issuer',
        ),
    )
    decision = decide_plugin_admission(deployment='oss', facts=facts)
    assert decision.runtime_profile == 'dedicated'
    assert decision.disposition.value == 'dedicated_allowed'


def test_oss_reconcile_never_reuses_persisted_shared_placement() -> None:
    from types import SimpleNamespace
    from langbot.pkg.plugin.connector import PluginRuntimeConnector

    connector = object.__new__(PluginRuntimeConnector)
    connector.ap = SimpleNamespace(deployment=SimpleNamespace(mode='oss'))
    setting = SimpleNamespace(
        artifact_digest='a' * 64, install_info={'_certification': _complete_persisted_certification()}
    )
    assert connector._execution_mode_from_setting(setting) is PluginExecutionMode.DEDICATED


def test_oss_does_not_treat_valid_nonshared_signature_as_dedicated_certification() -> None:
    from langbot.pkg.plugin.certification import (
        AdmissionDisposition,
        CertificateFacts,
        CertificateVerification,
        PluginCertificationFacts,
        decide_plugin_admission,
    )

    decision = decide_plugin_admission(
        deployment='oss',
        facts=PluginCertificationFacts(
            installation_uuid='00000000-0000-4000-8000-000000000001',
            artifact_digest='a' * 64,
            certificate=CertificateFacts(
                verification=CertificateVerification.VALID,
                runtime_profile=None,
                certificate_id='issuer',
            ),
        ),
    )
    assert decision.disposition is AdmissionDisposition.ADMINISTRATOR_FORCE_REQUIRED


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
            component_model='stateless-v1',
        ),
    )

    visibility = decide_plugin_log_visibility(facts)

    assert visibility.value == expected_visibility


def _complete_persisted_certification() -> dict[str, object]:
    return {
        'artifact_digest': 'a' * 64,
        'normalized_digest': 'b' * 64,
        'verification': 'valid',
        'certificate_runtime_profile': 'shared-runtime-v1',
        'certificate_component_model': 'stateless-v1',
        'certificate_id': 'ed25519:trusted-issuer',
        'runtime_profile': 'shared-runtime-v1',
        'admission_code': 'CERTIFIED_PLUGIN_SHARED_ELIGIBLE',
    }


@pytest.mark.parametrize(
    ('certification', 'expected_mode'),
    [
        (_complete_persisted_certification(), PluginExecutionMode.SHARED_CERTIFIED),
        (None, PluginExecutionMode.DEDICATED),
        ({}, PluginExecutionMode.DEDICATED),
        (
            {
                **_complete_persisted_certification(),
                'verification': 'invalid',
            },
            PluginExecutionMode.DEDICATED,
        ),
        (
            {
                **_complete_persisted_certification(),
                'artifact_digest': 'b' * 64,
            },
            PluginExecutionMode.DEDICATED,
        ),
        (
            {
                **_complete_persisted_certification(),
                'runtime_profile': 'dedicated',
            },
            PluginExecutionMode.DEDICATED,
        ),
        (
            {
                **_complete_persisted_certification(),
                'admission_code': 'CERTIFIED_PLUGIN_OSS_FORCED_DEDICATED',
            },
            PluginExecutionMode.DEDICATED,
        ),
    ],
)
def test_persisted_certification_selects_shared_execution_only_for_exact_admitted_artifact(
    certification: dict[str, object] | None,
    expected_mode: PluginExecutionMode,
) -> None:
    from langbot.pkg.plugin.certification import execution_mode_for_persisted_installation

    install_info = {} if certification is None else {'_certification': certification}

    assert (
        execution_mode_for_persisted_installation(
            artifact_digest='a' * 64,
            install_info=install_info,
        )
        is expected_mode
    )


@pytest.mark.parametrize(
    'missing_field',
    [
        'artifact_digest',
        'normalized_digest',
        'verification',
        'certificate_runtime_profile',
        'certificate_component_model',
        'certificate_id',
        'runtime_profile',
        'admission_code',
    ],
)
def test_persisted_certification_requires_every_shared_admission_fact(missing_field: str) -> None:
    from langbot.pkg.plugin.certification import execution_mode_for_persisted_installation

    certification = _complete_persisted_certification()
    del certification[missing_field]

    assert (
        execution_mode_for_persisted_installation(
            artifact_digest='a' * 64,
            install_info={'_certification': certification},
        )
        is PluginExecutionMode.DEDICATED
    )


@pytest.mark.parametrize(
    ('field', 'malformed_value'),
    [
        ('artifact_digest', None),
        ('artifact_digest', 123),
        ('artifact_digest', ''),
        ('normalized_digest', None),
        ('normalized_digest', 123),
        ('normalized_digest', ''),
        ('normalized_digest', ' ' * 64),
        ('normalized_digest', 'b' * 63),
        ('normalized_digest', 'g' * 64),
        ('certificate_id', None),
        ('certificate_id', 123),
        ('certificate_id', ''),
        ('certificate_id', '   '),
        ('verification', None),
        ('verification', 123),
        ('verification', ''),
        ('certificate_runtime_profile', None),
        ('certificate_runtime_profile', 123),
        ('certificate_runtime_profile', ''),
        ('certificate_component_model', None),
        ('certificate_component_model', 123),
        ('certificate_component_model', ''),
        ('runtime_profile', None),
        ('runtime_profile', 123),
        ('runtime_profile', ''),
        ('admission_code', None),
        ('admission_code', 123),
        ('admission_code', ''),
    ],
)
def test_persisted_certification_rejects_malformed_shared_admission_fact(
    field: str,
    malformed_value: object,
) -> None:
    from langbot.pkg.plugin.certification import execution_mode_for_persisted_installation

    certification = _complete_persisted_certification()
    certification[field] = malformed_value

    assert (
        execution_mode_for_persisted_installation(
            artifact_digest='a' * 64,
            install_info={'_certification': certification},
        )
        is PluginExecutionMode.DEDICATED
    )


@pytest.mark.parametrize('malformed_digest', ['', 'a' * 63, 'g' * 64])
def test_persisted_certification_rejects_malformed_matching_raw_digest(malformed_digest: str) -> None:
    from langbot.pkg.plugin.certification import execution_mode_for_persisted_installation

    certification = _complete_persisted_certification()
    certification['artifact_digest'] = malformed_digest

    assert (
        execution_mode_for_persisted_installation(
            artifact_digest=malformed_digest,
            install_info={'_certification': certification},
        )
        is PluginExecutionMode.DEDICATED
    )


def _archive_bytes(manifest: dict[str, object]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        import yaml

        archive.writestr('manifest.yaml', yaml.safe_dump(manifest))
    return buffer.getvalue()
