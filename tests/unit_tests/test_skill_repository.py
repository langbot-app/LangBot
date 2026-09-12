from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.skill.repository import SkillRepository, SkillRevisionConflictError


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
    from langbot.pkg.provider.tools.loaders import skill as skill_loader

    repository = _repository(tmp_path)
    published = await repository.create_skill(
        _CONTEXT,
        {'name': 'recoverable', 'instructions': 'Pinned instructions'},
    )
    await repository.delete_skill(_CONTEXT, 'recoverable')
    app = SimpleNamespace(skill_repository=repository)
    query = SimpleNamespace(
        variables={skill_loader.PIPELINE_BOUND_SKILLS_KEY: ['recoverable']},
        instance_uuid=_CONTEXT.instance_uuid,
        workspace_uuid=_CONTEXT.workspace_uuid,
        placement_generation=_CONTEXT.placement_generation,
        bot_uuid=None,
        pipeline_uuid=None,
        query_uuid='recovered-query',
    )

    restored = await skill_loader.restore_activated_skills(
        app,
        query,
        [{'name': 'recoverable', 'revision': published['revision']}],
    )

    assert restored == ['recoverable']
    assert skill_loader.get_activated_skill(query, 'recoverable')['revision'] == published['revision']
