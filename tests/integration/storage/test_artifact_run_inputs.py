"""Run input assets cannot become account assets or cross the run boundary."""
# ruff: noqa: F811

from dataclasses import replace
import uuid

import pytest

from langbot.pkg.api.context import PrincipalContext, PrincipalType
from langbot.pkg.storage.artifacts import ArtifactError
from tests.integration.storage.test_artifacts import (
    _expire,
    artifact_replicas,  # noqa: F401 -- pytest fixture
    persistence_case,  # noqa: F401 -- fixture dependency
    replicas,  # noqa: F401 -- fixture dependency
)


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_BODY = b'Only this authorized run can read this input.'


def _run_context(case, run_id=None):
    return replace(
        case.a.context,
        trigger_principal=PrincipalContext(PrincipalType.PROCESSOR, run_id=run_id or str(uuid.uuid4())),
    )


async def test_run_input_can_be_read_on_another_core_but_not_by_account_or_other_run(artifact_replicas):
    case = artifact_replicas
    context = _run_context(case)
    metadata = await case.a.app.artifact_service.create_run_input(context, 'input.txt', _BODY, 'text/plain')
    assert metadata['source'] == 'input_attachment' and metadata['lifecycle'] == 'temporary'
    downloaded = await case.b.app.artifact_service.read_run_input(context, metadata['id'])
    assert downloaded['content'] == _BODY and downloaded['metadata'] == metadata
    with pytest.raises(FileNotFoundError):
        await case.b.app.artifact_service.read_run_input(_run_context(case), metadata['id'])
    for method, suffix in (('get', ''), ('get', '/content'), ('post', '/retain'), ('delete', '')):
        response = await getattr(case.a.client, method)(
            '/api/v1/artifacts/' + metadata['id'] + suffix,
            headers=case.headers,
        )
        assert response.status_code == 404
    private = await case.a.app.artifact_service.create(case.context, 'private.txt', _BODY, 'text/plain')
    with pytest.raises(FileNotFoundError):
        await case.a.app.artifact_service.read_run_input(context, private['id'])


async def test_run_input_expiry_and_collection_use_the_same_lifecycle(artifact_replicas):
    case = artifact_replicas
    context = _run_context(case)
    metadata = await case.a.app.artifact_service.create_run_input(context, 'expired.txt', _BODY, 'text/plain')
    await _expire(case.a, context, metadata['id'])
    with pytest.raises(ArtifactError) as failure:
        await case.b.app.artifact_service.read_run_input(context, metadata['id'])
    assert failure.value.error_code == 'artifact_expired' and failure.value.status_code == 410
    system = replace(case.a.context, trigger_principal=PrincipalContext(PrincipalType.SYSTEM))
    assert await case.b.app.artifact_service.collect_expired(system) == 1
    with pytest.raises(FileNotFoundError):
        await case.a.app.artifact_service.read_run_input(context, metadata['id'])


async def test_run_input_internal_methods_require_a_run_execution_context(artifact_replicas):
    case = artifact_replicas
    for context in (
        case.context,
        case.a.context,
        replace(case.a.context, trigger_principal=PrincipalContext(PrincipalType.SYSTEM)),
        replace(case.a.context, trigger_principal=PrincipalContext(PrincipalType.PROCESSOR)),
    ):
        with pytest.raises(PermissionError):
            await case.a.app.artifact_service.create_run_input(context, 'input.txt', _BODY, 'text/plain')
        with pytest.raises(PermissionError):
            await case.a.app.artifact_service.read_run_input(context, 'art_' + '0' * 32)
