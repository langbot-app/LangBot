"""Migrate real legacy versions without changing bytes, owners or current pins."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
import zipfile

import pytest
import sqlalchemy as sa
from langbot_plugin.skill_store import SkillStore, skill_namespace

from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata
from langbot.pkg.entity.persistence.skill import SkillRegistry, SkillVersion
from langbot.pkg.persistence.legacy_migration import MigrationBusyError, MigrationLeaseLostError, WorkspaceMigration
from langbot.pkg.skill import migration
from langbot.pkg.skill.migration import initialize_skill_migration
from tests.integration.skill import test_persistent_skill_replicas as persistence_tests
from tests.integration.skill.test_persistent_skill_replicas import (
    _select_backend,
)

persistence_case = persistence_tests.persistence_case
replicas = persistence_tests.replicas


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skill_persistence,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not callable(getattr(SkillStore, 'publication_inventory', None)),
        reason='legacy Skill migration requires the coordinated SDK',
    ),
]

_BINARY = bytes(range(256)) * 8
_GUIDE_ONE = '# Guide\nExact original 你好\n'
_GUIDE_TWO = '# Guide\nNext immutable publication\n'
_SCRIPT = b'#!/usr/bin/env python3\nprint("original executable")\n'


@pytest.fixture(autouse=True)
def migration_content_backend(replicas):
    if replicas.minio:
        _select_backend(replicas.a, 'archive')
        _select_backend(replicas.b, 'archive')


def _source(replica, tmp_path):
    root = Path(replica.app.skill_repository._skills_root())
    namespace = skill_namespace(replica.context.instance_uuid, replica.context.workspace_uuid)
    store = SkillStore(root).scoped(namespace)
    package = tmp_path / 'source-package'
    package.mkdir()
    (package / 'SKILL.md').write_text('---\nname: kept\nreleased: 2024-01-02\n---\nUse references.\n')
    (package / 'references').mkdir()
    (package / 'references/guide.md').write_text(_GUIDE_ONE)
    (package / 'references/payload.bin').write_bytes(_BINARY)
    (package / 'scripts').mkdir()
    (package / 'scripts/probe.py').write_bytes(_SCRIPT)
    os.chmod(package / 'scripts/probe.py', 0o755)
    first = store.import_skill_directory(str(package), {'name': 'kept'}, source_root=str(tmp_path))
    latest = store.write_skill_file('kept', 'references/guide.md', _GUIDE_TWO, base_revision=first['revision'])
    deleted = store.create_skill({'name': 'deleted', 'instructions': 'Retain this deleted registration.'})
    store.delete_skill('deleted')
    return store, first, latest, deleted


async def _registrations(replica):
    async with replica.app.persistence_mgr.tenant_uow(replica.context.workspace_uuid) as uow:
        return list(
            (
                await uow.execute(
                    sa.select(SkillRegistry.name, SkillRegistry.current_revision).where(
                        SkillRegistry.workspace_uuid == replica.context.workspace_uuid,
                        SkillRegistry.instance_uuid == replica.context.instance_uuid,
                    )
                )
            ).all()
        )


def _remove_owned_source(root):
    for directory, _children, _files in os.walk(root):
        os.chmod(directory, 0o700)
    shutil.rmtree(root)


@pytest.mark.contract('legacy_skill_import')
async def test_import_preserves_history_deleted_registration_and_restart(replicas, tmp_path):
    a, b = replicas.a, replicas.b
    await initialize_skill_migration(a.app)
    _store, first, latest, deleted = _source(a, tmp_path)
    await initialize_skill_migration(a.app, source_required=True)
    assert await _registrations(a) == [('kept', latest['revision'])]
    for revision, expected in ((first['revision'], _GUIDE_ONE), (latest['revision'], _GUIDE_TWO)):
        package = await b.app.skill_repository.get_skill_package(b.context, 'kept', revision)
        assert package['revision'] == revision
        with zipfile.ZipFile(io.BytesIO(package['content'])) as archive:
            assert archive.read('references/guide.md').decode() == expected
            assert archive.read('references/payload.bin') == _BINARY
            assert archive.read('scripts/probe.py') == _SCRIPT
            assert archive.getinfo('scripts/probe.py').external_attr >> 16 & 0o111
    retained = await b.app.skill_repository.get_skill_package(b.context, 'deleted', deleted['revision'])
    with zipfile.ZipFile(io.BytesIO(retained['content'])) as archive:
        assert b'Retain this deleted registration.' in archive.read('SKILL.md')
    current = await b.app.skill_repository.get_skill(b.context, 'kept')
    assert current['created_at'] == first['created_at']
    assert current['metadata']['released'] == '2024-01-02'
    old_root = Path(a.app.skill_repository._skills_root())
    _remove_owned_source(old_root)
    restarted = await replicas.create('core-restarted')
    restarted.app.instance_config.data['skills']['root'] = str(old_root)
    await initialize_skill_migration(restarted.app, source_required=True)
    package = await restarted.app.skill_repository.get_skill_package(restarted.context, 'kept', first['revision'])
    with zipfile.ZipFile(io.BytesIO(package['content'])) as archive:
        assert archive.read('references/guide.md').decode() == _GUIDE_ONE
    assert not old_root.exists()


async def test_failed_version_import_retries_without_partial_current_pointer(replicas, tmp_path, monkeypatch):
    a = replicas.a
    source, _first, latest, _deleted = _source(a, tmp_path)
    database = a.app.skill_repository._database
    original = database.import_retained_publication
    calls = 0

    async def fail_second(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError('Injected import interruption')
        return await original(*args)

    monkeypatch.setattr(database, 'import_retained_publication', fail_second)
    with pytest.raises(RuntimeError, match='Injected import interruption'):
        await initialize_skill_migration(a.app, source_required=True)
    assert await _registrations(a) == []
    assert source.get_skill_snapshot('kept')['revision'] == latest['revision']
    async with a.app.persistence_mgr.tenant_uow(a.context.workspace_uuid) as uow:
        assert (
            await uow.execute(
                sa.select(sa.func.count())
                .select_from(SkillVersion)
                .where(
                    SkillVersion.workspace_uuid == a.context.workspace_uuid,
                    SkillVersion.instance_uuid == a.context.instance_uuid,
                )
            )
        ).scalar_one() == 1
    monkeypatch.setattr(database, 'import_retained_publication', original)
    await initialize_skill_migration(a.app, source_required=True)
    assert await _registrations(a) == [('kept', latest['revision'])]
    async with a.app.persistence_mgr.tenant_uow(a.context.workspace_uuid) as uow:
        assert (
            await uow.execute(
                sa.select(sa.func.count())
                .select_from(SkillVersion)
                .where(
                    SkillVersion.workspace_uuid == a.context.workspace_uuid,
                    SkillVersion.instance_uuid == a.context.instance_uuid,
                )
            )
        ).scalar_one() == 3


async def test_import_rejects_corrupt_source_and_missing_recorded_volume(replicas, tmp_path):
    a = replicas.a
    with pytest.raises(ValueError, match='source is unavailable'):
        await initialize_skill_migration(a.app, source_required=True)
    source, first, _latest, _deleted = _source(a, tmp_path)
    package = source.get_skill_snapshot('kept', first['revision'])
    guide = Path(package['package_root']) / 'references/guide.md'
    os.chmod(guide, 0o600)
    guide.write_text('tampered after publication')
    with pytest.raises(ValueError, match='revision|manifest|publication'):
        await initialize_skill_migration(a.app, source_required=True)
    assert await _registrations(a) == []
    _remove_owned_source(Path(a.app.skill_repository._skills_root()))
    with pytest.raises(ValueError, match='source is unavailable'):
        await initialize_skill_migration(a.app)


async def test_source_disappearing_after_discovery_is_not_a_fresh_replica(replicas, tmp_path, monkeypatch):
    a = replicas.a
    _source(a, tmp_path)
    root = Path(a.app.skill_repository._skills_root())
    scandir = migration.os.scandir

    def disappeared(path):
        if Path(path) == root:
            raise FileNotFoundError('Legacy source disappeared after its initial stat')
        return scandir(path)

    monkeypatch.setattr(migration.os, 'scandir', disappeared)
    with pytest.raises(FileNotFoundError, match='source disappeared'):
        await initialize_skill_migration(a.app)
    assert await _registrations(a) == []


async def test_import_never_overwrites_a_conflicting_database_current(replicas, tmp_path):
    a = replicas.a
    _source(a, tmp_path)
    current = await a.app.skill_repository.create_skill(
        a.context, {'name': 'kept', 'instructions': 'Database authority.'}
    )
    with pytest.raises(ValueError, match='conflicts with the current database registration'):
        await initialize_skill_migration(a.app, source_required=True)
    assert await _registrations(a) == [('kept', current['revision'])]


async def test_only_pending_nonempty_import_requires_network_handshake(replicas, tmp_path):
    a = replicas.a
    _source(a, tmp_path)
    a.app.box_service = SimpleNamespace(enabled=True, file_transfer_mode='network', available=False)
    with pytest.raises(RuntimeError, match='network Box handshake'):
        await initialize_skill_migration(a.app, source_required=True)
    assert await _registrations(a) == []
    a.app.box_service.available = True
    await initialize_skill_migration(a.app, source_required=True)
    _remove_owned_source(Path(a.app.skill_repository._skills_root()))
    a.app.box_service.available = False
    await initialize_skill_migration(a.app, source_required=True)
    assert len(await _registrations(a)) == 1


async def test_inventory_capability_is_required_only_for_an_actual_import(replicas, tmp_path, monkeypatch):
    a = replicas.a
    monkeypatch.delattr(SkillStore, 'publication_inventory')
    await initialize_skill_migration(a.app)
    root = Path(a.app.skill_repository._skills_root())
    (root / '.database-cache').mkdir(parents=True)
    await initialize_skill_migration(a.app)
    checkpoint = WorkspaceMigration(a.app, a.context, 'skills-filesystem-v1')
    assert await checkpoint.checkpoint() is None
    _source(a, tmp_path)
    with pytest.raises(ValueError, match='compatible Core and SDK'):
        await initialize_skill_migration(a.app, source_required=True)
    assert (await checkpoint.checkpoint())['progress']['source']
    _remove_owned_source(root)
    with pytest.raises(ValueError, match='source is unavailable'):
        await initialize_skill_migration(a.app)


@pytest.mark.contract('migration_fencing')
async def test_database_owner_fences_second_core_and_expired_previous_owner(replicas):
    a, b = replicas.a, replicas.b
    first = WorkspaceMigration(a.app, a.context, 'migration-owner-test')
    second = WorkspaceMigration(b.app, b.context, 'migration-owner-test')
    async with first:
        with pytest.raises(MigrationBusyError):
            async with second:
                pytest.fail('A second Core acquired the active migration')
        async with a.app.persistence_mgr.tenant_uow(a.context.workspace_uuid) as uow:
            value = (
                await uow.execute(
                    sa.select(WorkspaceMetadata.value).where(
                        WorkspaceMetadata.workspace_uuid == a.context.workspace_uuid,
                        WorkspaceMetadata.key == first.key,
                    )
                )
            ).scalar_one()
            expired = json.loads(value)
            expired['lease_until'] = 1
            await uow.execute(
                sa.update(WorkspaceMetadata)
                .where(
                    WorkspaceMetadata.workspace_uuid == a.context.workspace_uuid,
                    WorkspaceMetadata.key == first.key,
                )
                .values(value=json.dumps(expired))
            )
        async with second:
            with pytest.raises(MigrationLeaseLostError):
                async with first.transaction(complete=True):
                    pytest.fail('An expired owner obtained a write transaction')
            async with second.transaction(complete=True) as (_uow, progress):
                progress['winner'] = 'second Core'
    checkpoint = await second.checkpoint()
    assert checkpoint['status'] == 'completed'
    assert checkpoint['progress']['winner'] == 'second Core'
