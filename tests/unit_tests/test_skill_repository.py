from types import SimpleNamespace

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.skill.repository import SkillRepository, SkillRevisionMismatchError


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
                }
            }
        ),
    )
    return SkillRepository(app)


def test_repository_prefers_standalone_skill_root(tmp_path):
    repository = _repository(tmp_path)

    assert repository._store.root == str((tmp_path / 'skill-store').resolve())


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

    await repository.create_skill(
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
async def test_repository_rejects_traversal_and_stale_revision(tmp_path):
    repository = _repository(tmp_path)
    await repository.create_skill(
        _CONTEXT,
        {'name': 'safe', 'description': 'Safe', 'instructions': 'Use the reference.'},
    )
    await repository.write_skill_file(_CONTEXT, 'safe', 'reference.md', 'first')
    skill = await repository.get_skill(_CONTEXT, 'safe', snapshot=True)
    assert skill is not None

    with pytest.raises(ValueError, match='stay within'):
        await repository.read_skill_resource(_CONTEXT, 'safe', '../secret.txt')

    await repository.write_skill_file(_CONTEXT, 'safe', 'reference.md', 'second')
    with pytest.raises(SkillRevisionMismatchError, match='reactivate'):
        await repository.read_skill_resource(
            _CONTEXT,
            'safe',
            'reference.md',
            expected_revision=skill['revision'],
        )


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
