import base64
import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.skill.repository import (
    SkillRepository,
    SkillRevisionConflictError,
    SkillRevisionMismatchError,
)


_CONTEXT = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid='workspace-a',
    placement_generation=1,
)


async def _binding(workspace_uuid, *, expected_generation):
    return SimpleNamespace(
        instance_uuid=_CONTEXT.instance_uuid,
        workspace_uuid=workspace_uuid,
        placement_generation=expected_generation,
    )


def _repository(tmp_path) -> SkillRepository:
    app = SimpleNamespace(
        workspace_service=SimpleNamespace(
            get_execution_binding=_binding,
        ),
        instance_config=SimpleNamespace(
            data={
                'skills': {'root': str(tmp_path / 'skill-store')},
                'box': {
                    'enabled': False,
                    'local': {
                        'host_root': str(tmp_path / 'box'),
                    },
                },
            }
        ),
    )
    return SkillRepository(app)


def test_repository_prefers_standalone_skill_root(tmp_path):
    repository = _repository(tmp_path)

    assert repository._store.root == str((tmp_path / 'skill-store').resolve())


def test_repository_locks_are_workspace_scoped(tmp_path):
    repository = _repository(tmp_path)

    first = repository._workspace_lock('workspace-a')
    assert repository._workspace_lock('workspace-a') is first
    assert repository._workspace_lock('workspace-b') is not first


def test_repository_keeps_old_box_root_only_for_online_upgrade(tmp_path):
    app = SimpleNamespace(
        workspace_service=SimpleNamespace(get_execution_binding=_binding),
        instance_config=SimpleNamespace(
            data={
                'box': {
                    'local': {
                        'host_root': str(tmp_path / 'box'),
                        'skills_root': 'legacy-skills',
                    }
                }
            }
        ),
    )

    repository = SkillRepository(app)

    assert repository._store.root == str((tmp_path / 'box' / 'legacy-skills').resolve())


@pytest.mark.asyncio
async def test_repository_crud_and_reads_do_not_require_box(tmp_path):
    repository = _repository(tmp_path)

    created = await repository.create_skill(
        _CONTEXT,
        {
            'name': 'docs-only',
            'display_name': 'Docs only',
            'description': 'Read-only guidance',
            'instructions': 'Read references/guide.md.',
        },
    )
    await repository.write_skill_file(
        _CONTEXT,
        'docs-only',
        'references/guide.md',
        '# Guide\n\nNo execution needed.',
        base_revision=created['revision'],
    )

    skill = await repository.get_skill(_CONTEXT, 'docs-only', snapshot=True)
    assert skill is not None
    assert skill['revision'].startswith('sha256:')
    assert [item['name'] for item in await repository.list_skills(_CONTEXT)] == ['docs-only']

    listed = await repository.list_skill_resources(
        _CONTEXT,
        'docs-only',
        'references',
        expected_revision=skill['revision'],
    )
    assert listed['entries'][0]['path'] == 'references/guide.md'
    assert listed['entries'][0]['mime_type'] == 'text/markdown'

    resource = await repository.read_skill_resource(
        _CONTEXT,
        'docs-only',
        'references/guide.md',
        expected_revision=skill['revision'],
    )
    assert resource['content'].startswith('# Guide')
    assert resource['revision'] == skill['revision']


@pytest.mark.asyncio
async def test_repository_rejects_traversal_and_conflicting_update(tmp_path):
    repository = _repository(tmp_path)
    created = await repository.create_skill(
        _CONTEXT,
        {'name': 'safe', 'description': 'Safe', 'instructions': 'Use the reference.'},
    )
    first = await repository.write_skill_file(
        _CONTEXT,
        'safe',
        'reference.md',
        'first',
        base_revision=created['revision'],
    )
    skill = await repository.get_skill(_CONTEXT, 'safe', snapshot=True)
    assert skill is not None

    with pytest.raises(ValueError, match='stay within'):
        await repository.read_skill_resource(_CONTEXT, 'safe', '../secret.txt')

    second = await repository.write_skill_file(
        _CONTEXT,
        'safe',
        'reference.md',
        'second',
        base_revision=first['revision'],
    )
    pinned = await repository.read_skill_resource(
        _CONTEXT,
        'safe',
        'reference.md',
        expected_revision=skill['revision'],
    )
    assert pinned['content'] == 'first'
    with pytest.raises(SkillRevisionConflictError, match='changed since'):
        await repository.update_skill(
            _CONTEXT,
            'safe',
            {'instructions': 'stale'},
            base_revision=first['revision'],
        )
    assert second['revision'] != first['revision']


@pytest.mark.asyncio
async def test_repository_scopes_skills_by_workspace(tmp_path):
    repository = _repository(tmp_path)
    other_context = ExecutionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-b',
        placement_generation=1,
    )

    await repository.create_skill(_CONTEXT, {'name': 'private', 'instructions': 'A'})

    assert [skill['name'] for skill in await repository.list_skills(_CONTEXT)] == ['private']
    assert await repository.list_skills(other_context) == []


@pytest.mark.asyncio
async def test_repository_rejects_stale_workspace_placement(tmp_path):
    repository = _repository(tmp_path)

    async def stale_binding(workspace_uuid, *, expected_generation):
        return SimpleNamespace(
            instance_uuid=_CONTEXT.instance_uuid,
            workspace_uuid=workspace_uuid,
            placement_generation=expected_generation + 1,
        )

    repository.ap.workspace_service.get_execution_binding = stale_binding
    with pytest.raises(ValueError, match='stale Workspace placement'):
        await repository.list_skills(_CONTEXT)


@pytest.mark.asyncio
async def test_repository_imports_only_from_the_fenced_workspace(tmp_path):
    repository = _repository(tmp_path)
    namespace = repository._namespace(_CONTEXT)
    source = tmp_path / 'box' / 'default' / 'tenants' / namespace / 'draft'
    source.mkdir(parents=True)
    (source / 'SKILL.md').write_text(
        '---\nname: draft\ndescription: Draft skill\n---\n\nFollow the guide.',
        encoding='utf-8',
    )
    (source / 'guide.md').write_text('Imported resource', encoding='utf-8')

    scanned = await repository.scan_skill_directory(_CONTEXT, str(source))
    imported = await repository.import_skill_directory(
        _CONTEXT,
        str(source),
        {
            'name': scanned['name'],
            'display_name': scanned['display_name'],
            'description': scanned['description'],
            'instructions': scanned['instructions'],
        },
    )

    assert imported['name'] == 'draft'
    resource = await repository.read_skill_file(_CONTEXT, 'draft', 'guide.md')
    assert resource['content'] == 'Imported resource'

    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'SKILL.md').write_text('Outside', encoding='utf-8')
    with pytest.raises(ValueError, match='trusted source root'):
        await repository.scan_skill_directory(_CONTEXT, str(outside))


@pytest.mark.asyncio
async def test_existing_run_keeps_v1_while_new_run_resolves_v2(tmp_path):
    from langbot.pkg.provider.tools.loaders import skill as skill_loader

    repository = _repository(tmp_path)
    created = await repository.create_skill(
        _CONTEXT,
        {'name': 'runner', 'instructions': 'Run scripts/main.py'},
    )
    v1_write = await repository.write_skill_file(
        _CONTEXT,
        'runner',
        'scripts/main.py',
        "print('v1')",
        base_revision=created['revision'],
    )
    v1 = await repository.get_skill(_CONTEXT, 'runner', snapshot=True)
    old_run = SimpleNamespace(variables={})
    skill_loader.register_activated_skill(old_run, v1)

    await repository.write_skill_file(
        _CONTEXT,
        'runner',
        'scripts/main.py',
        "print('v2')",
        base_revision=v1_write['revision'],
    )
    v2 = await repository.get_skill(_CONTEXT, 'runner', snapshot=True)
    new_run = SimpleNamespace(variables={})
    skill_loader.register_activated_skill(new_run, v2)

    old_resource = await repository.read_skill_resource(
        _CONTEXT,
        'runner',
        'scripts/main.py',
        expected_revision=v1['revision'],
    )
    new_resource = await repository.read_skill_resource(
        _CONTEXT,
        'runner',
        'scripts/main.py',
        expected_revision=v2['revision'],
    )
    app = SimpleNamespace(logger=Mock())
    old_mount = skill_loader.build_execution_mounts(app, old_run)[0]
    new_mount = skill_loader.build_execution_mounts(app, new_run)[0]

    assert old_resource['content'] == "print('v1')"
    assert new_resource['content'] == "print('v2')"
    assert old_mount['host_path'] == v1['package_root']
    assert new_mount['host_path'] == v2['package_root']
    assert old_mount['content_digest'] == v1['revision']
    assert new_mount['content_digest'] == v2['revision']


@pytest.mark.asyncio
async def test_deleted_skill_can_restore_exact_recoverable_run_revision(tmp_path):
    repository = _repository(tmp_path)
    published = await repository.create_skill(
        _CONTEXT,
        {'name': 'recoverable', 'instructions': 'Pinned instructions'},
    )
    await repository.delete_skill(_CONTEXT, 'recoverable')
    restored = await repository.get_skill(_CONTEXT, 'recoverable', snapshot=True, revision=published['revision'])
    assert restored['revision'] == published['revision']
    assert restored['instructions'] == 'Pinned instructions'


_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
    b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)


async def _package_with_binary(repository, tmp_path) -> tuple[str, str]:
    """Publish a skill holding a real PNG and a PDF, return (revision, skill)."""

    source = tmp_path / 'box' / 'default' / 'tenants' / 'ws-695136eeae1cb9b6af4a8226' / 'pkg'
    (source / 'assets').mkdir(parents=True)
    (source / 'SKILL.md').write_text('---\nname: media\ndescription: d\n---\n\nUse the assets.\n')
    (source / 'assets' / 'diagram.png').write_bytes(_PNG)
    (source / 'assets' / 'spec.pdf').write_bytes(b'%PDF-1.4\n%%EOF\n')
    skill = await repository.import_skill_directory(
        _CONTEXT,
        str(source),
        {'name': 'media', 'description': 'd'},
    )
    return skill['revision'], skill


@pytest.mark.asyncio
async def test_binary_resources_are_read_only_when_generated(tmp_path):
    """The UTF-8 gap from #2775: reading a PNG must not be a UTF-8 error."""

    repository = _repository(tmp_path)
    revision, _ = await _package_with_binary(repository, tmp_path)

    with pytest.raises(ValueError, match='not valid UTF-8'):
        await repository._call(_CONTEXT, 'read_skill_resource', 'media', 'assets/diagram.png')

    resource = await repository.read_skill_resource(
        _CONTEXT,
        'media',
        'assets/diagram.png',
        expected_revision=revision,
    )

    assert resource['encoding'] == 'base64'
    assert base64.b64decode(resource['content']) == _PNG
    assert resource['size'] == len(_PNG)
    assert resource['mime_type'] == 'image/png'
    assert resource['revision'] == revision
    assert resource['sha256'] == hashlib.sha256(_PNG).hexdigest()


@pytest.mark.asyncio
async def test_binary_resource_requires_activation_and_pins_revision(tmp_path):
    repository = _repository(tmp_path)
    first_revision, _ = await _package_with_binary(repository, tmp_path)

    with pytest.raises(SkillRevisionMismatchError):
        await repository.read_skill_resource(
            _CONTEXT,
            'media',
            'assets/diagram.png',
            expected_revision='sha256:not-a-revision',
        )

    # A later publication must not change the bytes an existing run resolves.
    rewritten = tmp_path / 'box' / 'default' / 'tenants' / 'ws-695136eeae1cb9b6af4a8226' / 'pkg2'
    (rewritten / 'assets').mkdir(parents=True)
    (rewritten / 'SKILL.md').write_text('---\nname: media\ndescription: d\n---\n\nUse the assets.\n')
    (rewritten / 'assets' / 'diagram.png').write_bytes(_PNG + b'tail')
    updated = await repository.import_skill_directory(
        _CONTEXT,
        str(rewritten),
        {'name': 'media', 'description': 'd'},
        base_revision=first_revision,
    )

    pinned = await repository.read_skill_resource(
        _CONTEXT,
        'media',
        'assets/diagram.png',
        expected_revision=first_revision,
    )
    current = await repository.read_skill_resource(
        _CONTEXT,
        'media',
        'assets/diagram.png',
        expected_revision=updated['revision'],
    )

    assert base64.b64decode(pinned['content']) == _PNG
    assert base64.b64decode(current['content']) == _PNG + b'tail'


@pytest.mark.asyncio
async def test_binary_resource_rejects_escape_missing_and_oversized(tmp_path):
    repository = _repository(tmp_path)
    revision, _ = await _package_with_binary(repository, tmp_path)

    with pytest.raises(ValueError, match='stay within'):
        await repository.read_skill_resource(
            _CONTEXT,
            'media',
            '../secret.png',
            expected_revision=revision,
        )
    with pytest.raises(ValueError, match='not found'):
        await repository.read_skill_resource(
            _CONTEXT,
            'media',
            'assets/missing.png',
            expected_revision=revision,
        )
    with pytest.raises(ValueError, match='read limit'):
        await repository.read_skill_resource_bytes(
            _CONTEXT,
            'media',
            'assets/diagram.png',
            expected_revision=revision,
            max_bytes=4,
        )


@pytest.mark.asyncio
async def test_text_resources_keep_the_string_contract(tmp_path):
    repository = _repository(tmp_path)
    revision, _ = await _package_with_binary(repository, tmp_path)

    text = await repository.read_skill_resource(
        _CONTEXT,
        'media',
        'SKILL.md',
        expected_revision=revision,
    )

    assert text['content'].startswith('---')
    assert 'encoding' not in text
