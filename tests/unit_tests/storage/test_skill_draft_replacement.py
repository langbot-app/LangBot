"""Complete draft replacements preserve database CAS without reading old package bytes."""

import io
from types import SimpleNamespace
from unittest.mock import AsyncMock
import zipfile

import pytest
import sqlalchemy as sa
from langbot_plugin.skill_store import SkillStore

from langbot.pkg.entity.persistence.content import ContentObject
from langbot.pkg.entity.persistence.skill import SkillRegistry, SkillVersion
from langbot.pkg.skill.repository import SkillRepository, SkillRevisionConflictError
from tests.unit_tests.storage import test_content_store as content_fixtures


storage = content_fixtures.storage
CONTEXT = content_fixtures.context()
pytestmark = pytest.mark.skipif(
    not callable(getattr(SkillStore, '_prepare_skill_zip', None)),
    reason='requires the in-tree Skill draft SDK',
)


def draft(version, *, name='packet', resource='current.txt'):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('SKILL.md', f'---\nname: {name}\ndescription: Complete draft\n---\n{version}\n')
        archive.writestr(f'references/{resource}', version)
    return buffer.getvalue()


@pytest.fixture
async def repository(storage, tmp_path):
    storage.ap.storage_mgr = storage
    storage.ap.instance_config.data['skills'] = {'persistence': 'database', 'root': str(tmp_path / 'cache')}
    storage.ap.box_service = SimpleNamespace(file_transfer_mode='network')
    async with storage.ap.persistence_mgr.get_db_engine().begin() as connection:
        await connection.run_sync(lambda sync: SkillRegistry.__table__.create(sync))
        await connection.run_sync(lambda sync: SkillVersion.__table__.create(sync))
    return SkillRepository(storage.ap)


@pytest.mark.asyncio
async def test_complete_draft_replacement_preserves_identity_history_and_replaces_all_files(repository):
    first = await repository.import_skill_zip(CONTEXT, draft('first', resource='old.txt'), {})
    original = await repository.get_skill_package(CONTEXT, 'packet', first['revision'])
    second = await repository.import_skill_zip(
        CONTEXT, draft('second', resource='new.txt'), {}, base_revision=first['revision']
    )
    assert second['created_at'] == first['created_at']
    assert second['updated_at'] != first['updated_at']
    assert second['revision'] != first['revision']
    assert await repository.get_skill_package(CONTEXT, 'packet', first['revision']) == original
    current = await repository.get_skill_package(CONTEXT, 'packet', second['revision'])
    with zipfile.ZipFile(io.BytesIO(current['content'])) as archive:
        assert archive.read('references/new.txt') == b'second'
        assert 'references/old.txt' not in archive.namelist()


@pytest.mark.asyncio
@pytest.mark.parametrize('created_at', [None, ''])
async def test_replacement_preserves_an_explicit_created_at_value(repository, storage, created_at):
    first = await repository.import_skill_zip(CONTEXT, draft('first'), {})
    changed = {**first, 'created_at': created_at}
    async with storage.ap.persistence_mgr.tenant_uow(CONTEXT.workspace_uuid) as uow:
        await uow.execute(sa.update(SkillRegistry).values(skill_json=changed))
        await uow.execute(sa.update(SkillVersion).values(skill_json=changed))
    second = await repository.import_skill_zip(CONTEXT, draft('second'), {}, base_revision=first['revision'])
    assert 'created_at' in second and second['created_at'] == created_at


@pytest.mark.asyncio
async def test_replacement_keeps_original_missing_required_and_stale_base_errors(repository):
    with pytest.raises(SkillRevisionConflictError, match='does not exist; base_revision must be omitted'):
        await repository.import_skill_zip(CONTEXT, draft('missing'), {}, base_revision='sha256:' + 'a' * 64)
    assert await repository.list_skills(CONTEXT) == []
    first = await repository.import_skill_zip(CONTEXT, draft('first'), {})
    with pytest.raises(SkillRevisionConflictError, match='requires base_revision'):
        await repository.import_skill_zip(CONTEXT, draft('missing base'), {})
    with pytest.raises(SkillRevisionConflictError, match='changed since the draft was created'):
        await repository.import_skill_zip(CONTEXT, draft('stale base'), {}, base_revision='sha256:' + 'b' * 64)
    assert (await repository.get_skill(CONTEXT, 'packet'))['revision'] == first['revision']


@pytest.mark.asyncio
async def test_complete_replacement_does_not_depend_on_the_old_content_backend(repository, storage, monkeypatch):
    first = await repository.import_skill_zip(CONTEXT, draft('first'), {})
    original = await repository.get_skill_package(CONTEXT, 'packet', first['revision'])
    record = await repository._database._record(CONTEXT, 'packet', first['revision'])
    reference = record['content_ref']
    content_get = storage.content_store.get

    async def unavailable_old_content(context, ref, **kwargs):
        if ref == reference:
            raise FileNotFoundError('Old package backend unavailable')
        return await content_get(context, ref, **kwargs)

    faulty_get = AsyncMock(side_effect=unavailable_old_content)
    monkeypatch.setattr(storage.content_store, 'get', faulty_get)
    second = await repository.import_skill_zip(CONTEXT, draft('second'), {}, base_revision=first['revision'])
    faulty_get.assert_not_awaited()
    assert (await repository.get_skill_package(CONTEXT, 'packet', second['revision']))['revision'] == second['revision']
    with pytest.raises(FileNotFoundError, match='Old package backend unavailable'):
        await repository.get_skill_package(CONTEXT, 'packet', first['revision'])
    monkeypatch.setattr(storage.content_store, 'get', content_get)
    assert await repository.get_skill_package(CONTEXT, 'packet', first['revision']) == original


@pytest.mark.asyncio
async def test_another_core_can_win_after_draft_validation_and_final_cas_still_rejects_the_loser(
    repository, storage, monkeypatch
):
    first = await repository.import_skill_zip(CONTEXT, draft('first'), {})
    other_core = SkillRepository(storage.ap)
    publish = repository._database._publish
    winner = None

    async def publish_after_competitor(context, publications, bases):
        nonlocal winner
        winner = await other_core.import_skill_zip(context, draft('winner'), {}, base_revision=first['revision'])
        await publish(context, publications, bases)

    monkeypatch.setattr(repository._database, '_publish', publish_after_competitor)
    with pytest.raises(SkillRevisionConflictError, match='changed since the draft was created'):
        await repository.import_skill_zip(CONTEXT, draft('loser'), {}, base_revision=first['revision'])
    assert (await repository.get_skill(CONTEXT, 'packet'))['revision'] == winner['revision']
    async with storage.ap.persistence_mgr.tenant_uow(CONTEXT.workspace_uuid) as uow:
        assert (await uow.execute(sa.select(sa.func.count()).select_from(SkillVersion))).scalar_one() == 2
        assert (await uow.execute(sa.select(sa.func.count()).select_from(ContentObject))).scalar_one() == 2
