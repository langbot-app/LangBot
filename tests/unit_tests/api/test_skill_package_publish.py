"""Complete package publication shares the SDK validator, CAS and binary manifest."""

import dataclasses
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock
import zipfile

import pytest
import quart
from quart.datastructures import FileStorage

from langbot.pkg.api.application.operation_docs import get_operation_doc
from langbot.pkg.api.application.service_operations import operations
from langbot.pkg.api.authz import PermissionDeniedError
from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from langbot.pkg.api.http.service.skill import SkillService
from langbot.pkg.api.http.controller.groups.skills import SkillsRouterGroup
from langbot.pkg.skill.repository import SkillRevisionConflictError
from tests.unit_tests.test_skill_repository import _repository


CONTEXT = RequestContext(
    instance_uuid='instance-a',
    placement_generation=1,
    request_id='test',
    auth_type='api_key',
    principal=PrincipalContext(PrincipalType.API_KEY, api_key_uuid='key-a'),
    workspace=WorkspaceContext('workspace-a', None, None, frozenset({'resource.view', 'resource.manage'})),
)


def package(version, name='packet', resource='current.bin'):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('SKILL.md', f'---\nname: {name}\ndescription: Package\n---\n{version}\n')
        archive.writestr(f'references/{resource}', b'\x00\xff' + version.encode())
        script = zipfile.ZipInfo('scripts/run.sh')
        script.external_attr = 0o100755 << 16
        archive.writestr(script, '#!/bin/sh\necho ready\n')
    return output.getvalue()


@pytest.fixture
def service(tmp_path):
    repository = _repository(tmp_path)
    repository.ap.skill_repository = repository
    repository.ap.skill_mgr = SimpleNamespace(reload_skills=AsyncMock())
    return SkillService(repository.ap)


@pytest.mark.asyncio
async def test_preview_is_read_only_and_publish_replaces_binary_files(service):
    repository = service.ap.skill_repository
    first = await repository.import_skill_zip(CONTEXT, package('first', resource='old.bin'), {})
    original = await repository.get_skill_package(CONTEXT, 'packet', first['revision'])
    archive = package('second', resource='new.bin')
    plan = await service.preview_skill_package(CONTEXT, 'packet', archive, first['revision'])
    assert plan['dry_run'] and plan['can_publish']
    assert plan['changes']['added'] == ['references/new.bin']
    assert plan['changes']['deleted'] == ['references/old.bin']
    assert plan['changes']['modified'] == ['SKILL.md']
    assert (await repository.get_skill(CONTEXT, 'packet'))['revision'] == first['revision']
    service.ap.skill_mgr.reload_skills.assert_not_awaited()
    published = await service.publish_skill_package(CONTEXT, 'packet', archive, first['revision'])
    assert published['skill']['revision'] == plan['proposed_revision']
    assert not published['dry_run']
    current = await repository.get_skill_package(CONTEXT, 'packet')
    with zipfile.ZipFile(io.BytesIO(current['content'])) as files:
        assert files.read('references/new.bin') == b'\x00\xffsecond'
        assert 'references/old.bin' not in files.namelist()
        assert files.getinfo('scripts/run.sh').external_attr >> 16 & 0o111
    assert await repository.get_skill_package(CONTEXT, 'packet', first['revision']) == original
    service.ap.skill_mgr.reload_skills.assert_awaited_once()


@pytest.mark.asyncio
async def test_rejects_stale_or_missing_revision_wrong_name_and_invalid_archive(service):
    repository = service.ap.skill_repository
    first = await repository.import_skill_zip(CONTEXT, package('first'), {})
    for revision in ['', 'sha256:' + 'b' * 64]:
        with pytest.raises(SkillRevisionConflictError):
            await service.publish_skill_package(CONTEXT, 'packet', package('second'), revision)
    for content in [b'invalid zip', package('other', name='other')]:
        with pytest.raises(ValueError):
            await service.publish_skill_package(CONTEXT, 'packet', content, first['revision'])
    assert (await repository.get_skill(CONTEXT, 'packet'))['revision'] == first['revision']
    assert await repository.get_skill(CONTEXT, 'other') is None
    service.ap.skill_mgr.reload_skills.assert_not_awaited()


@pytest.mark.asyncio
async def test_viewer_can_preview_but_cannot_publish(service):
    first = await service.ap.skill_repository.import_skill_zip(CONTEXT, package('first'), {})
    viewer = dataclasses.replace(
        CONTEXT, workspace=dataclasses.replace(CONTEXT.workspace, permissions=frozenset({'resource.view'}))
    )
    plan = await service.preview_skill_package(viewer, 'packet', package('second'), first['revision'])
    assert not plan['can_publish']
    with pytest.raises(PermissionDeniedError):
        await service.publish_skill_package(viewer, 'packet', package('second'), first['revision'])
    denied = dataclasses.replace(viewer, workspace=dataclasses.replace(viewer.workspace, permissions=frozenset()))
    with pytest.raises(PermissionDeniedError):
        await service.preview_skill_package(denied, 'packet', package('second'), first['revision'])


@pytest.mark.asyncio
async def test_concurrent_change_after_preview_still_fails_cas(service, monkeypatch):
    repository = service.ap.skill_repository
    first = await repository.import_skill_zip(CONTEXT, package('first'), {})
    inspect = service.preview_skill_package

    async def race(*args):
        plan = await inspect(*args)
        await repository.import_skill_zip(CONTEXT, package('concurrent'), {}, base_revision=first['revision'])
        return plan

    monkeypatch.setattr(service, 'preview_skill_package', race)
    with pytest.raises(SkillRevisionConflictError):
        await service.publish_skill_package(CONTEXT, 'packet', package('second'), first['revision'])
    assert 'concurrent' in (await repository.get_skill(CONTEXT, 'packet'))['instructions']


def test_package_operations_have_read_write_permissions_and_no_agent_exposure():
    catalog = {operation.operation_id: operation for operation in operations()}
    for identifier, permission, write in [
        ('skill.package.preview', 'resource.view', False),
        ('skill.package.publish', 'resource.manage', True),
    ]:
        operation = catalog[identifier]
        assert operation.permission.value == permission
        assert operation.side_effect is write
        assert operation.principals == frozenset({PrincipalType.ACCOUNT, PrincipalType.API_KEY})
        assert get_operation_doc(identifier).exposure == 'none'


@pytest.mark.asyncio
@pytest.mark.parametrize('role', ['developer', 'viewer'])
async def test_http_package_transport_and_permissions(service, role):
    repository = service.ap.skill_repository
    first = await repository.import_skill_zip(CONTEXT, package('first'), {})
    app = quart.Quart(__name__)
    service.ap.skill_service = service
    service.ap.user_service = SimpleNamespace(
        get_authenticated_account=AsyncMock(return_value=SimpleNamespace(uuid='account-a', user='test@example.com'))
    )
    service.ap.workspace_collaboration_service = SimpleNamespace(
        resolve_account_workspace=AsyncMock(
            return_value=SimpleNamespace(
                execution=SimpleNamespace(instance_uuid='instance-a', placement_generation=1),
                workspace=SimpleNamespace(uuid='workspace-a'),
                membership=SimpleNamespace(uuid='member-a', role=role, projection_revision=1),
            )
        )
    )
    await SkillsRouterGroup(service.ap, app).initialize()
    client = app.test_client()

    async def post(suffix, content=None, revision=None):
        return await client.post(
            '/api/v1/skills/packet/package' + suffix,
            headers={'Authorization': 'Bearer test-token'},
            form={'base_revision': revision or first['revision']},
            files={'file': FileStorage(stream=io.BytesIO(content or package('second')), filename='draft.zip')},
        )

    preview = await post('/preview')
    assert preview.status_code == 200
    assert (await preview.get_json())['data']['can_publish'] is (role == 'developer')
    assert (await repository.get_skill(CONTEXT, 'packet'))['revision'] == first['revision']
    published = await post('')
    assert published.status_code == (200 if role == 'developer' else 403)
    if role == 'developer':
        assert (await post('')).status_code == 409
        current = (await repository.get_skill(CONTEXT, 'packet'))['revision']
        assert (await post('', package('wrong', name='other'), current)).status_code == 400
        assert (await post('/preview', b'x' * (10 * 1024 * 1024 + 1), current)).status_code == 413
        missing = await client.post(
            '/api/v1/skills/packet/package',
            headers={'Authorization': 'Bearer test-token'},
            form={'base_revision': current},
        )
        assert missing.status_code == 400
