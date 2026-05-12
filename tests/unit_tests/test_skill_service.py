import io
import os
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.langbot.pkg.api.http.service.skill import SkillService


def _create_skill_file(
    path,
    *,
    name: str = 'imported-skill',
    display_name: str = '',
    description: str = 'Imported from local directory',
    body: str = 'Skill instructions',
) -> None:
    frontmatter = ['name: ' + name, 'description: ' + description]
    if display_name:
        frontmatter.insert(1, 'display_name: ' + display_name)

    path.write_text(
        '---\n' + '\n'.join(frontmatter) + f'\n---\n\n{body}\n',
        encoding='utf-8',
    )


@pytest.fixture
def skill_service():
    app = SimpleNamespace(
        skill_mgr=SimpleNamespace(
            refresh_skill_from_disk=lambda *_args, **_kwargs: True,
            reload_skills=AsyncMock(),
        )
    )
    return SkillService(app)


def test_scan_directory_supports_nested_skill_within_two_levels(skill_service, tmp_path):
    nested_dir = tmp_path / 'downloaded' / 'self-improving-agent'
    nested_dir.mkdir(parents=True)
    _create_skill_file(nested_dir / 'SKILL.md')

    result = skill_service.scan_directory(str(tmp_path))

    assert result['package_root'] == str(nested_dir.resolve())
    assert result['entry_file'] == 'SKILL.md'
    assert result['name'] == 'imported-skill'
    assert result['instructions'] == 'Skill instructions'


def test_scan_directory_rejects_ambiguous_nested_skill_directories(skill_service, tmp_path):
    first_dir = tmp_path / 'skills' / 'alpha'
    second_dir = tmp_path / 'skills' / 'beta'
    first_dir.mkdir(parents=True)
    second_dir.mkdir(parents=True)
    _create_skill_file(first_dir / 'SKILL.md', body='alpha instructions')
    _create_skill_file(second_dir / 'SKILL.md', body='beta instructions')

    with pytest.raises(ValueError, match='Multiple skill directories found'):
        skill_service.scan_directory(str(tmp_path))


def test_scan_directory_errors_when_skill_is_deeper_than_two_levels(skill_service, tmp_path):
    deep_dir = tmp_path / 'a' / 'b' / 'c'
    deep_dir.mkdir(parents=True)
    _create_skill_file(deep_dir / 'SKILL.md')

    with pytest.raises(ValueError, match='max depth: 2'):
        skill_service.scan_directory(str(tmp_path))


@pytest.mark.asyncio
async def test_create_skill_import_preserves_existing_skill_content_when_form_fields_blank(tmp_path, monkeypatch):
    source_dir = tmp_path / 'external-skills' / 'manual-skill'
    source_dir.mkdir(parents=True)
    _create_skill_file(
        source_dir / 'SKILL.md',
        display_name='Imported Skill',
        description='Imported description',
        body='Original instructions',
    )

    service = SkillService(SimpleNamespace(skill_mgr=SimpleNamespace(reload_skills=AsyncMock())))
    service.get_skill_by_name = AsyncMock(return_value=None)
    managed_root = tmp_path / 'data' / 'skills' / 'imported-skill'
    service.get_skill = AsyncMock(
        return_value={
            'name': 'imported-skill',
            'package_root': str(managed_root.resolve()),
            'description': 'Imported description',
            'instructions': 'Original instructions',
        }
    )

    monkeypatch.setenv('LANGBOT_DATA_ROOT', str(tmp_path / 'data'))

    await service.create_skill(
        {
            'name': 'imported-skill',
            'package_root': str(source_dir),
            'display_name': '',
            'description': '',
            'instructions': '',
        }
    )

    content = (managed_root / 'SKILL.md').read_text(encoding='utf-8')
    assert 'display_name: Imported Skill' in content
    assert 'description: Imported description' in content
    assert content.endswith('Original instructions')


@pytest.mark.asyncio
async def test_create_skill_reuses_existing_managed_directory_without_copying(tmp_path, monkeypatch):
    managed_root = tmp_path / 'data' / 'skills' / 'demo-repo' / 'skills' / 'nested-skill'
    managed_root.mkdir(parents=True)
    _create_skill_file(
        managed_root / 'SKILL.md',
        name='nested-skill',
        display_name='Nested Skill',
        description='Already managed',
        body='Managed instructions',
    )

    service = SkillService(SimpleNamespace(skill_mgr=SimpleNamespace(reload_skills=AsyncMock())))
    service.get_skill_by_name = AsyncMock(return_value=None)
    service.get_skill = AsyncMock(
        return_value={
            'name': 'nested-skill',
            'package_root': str(managed_root.resolve()),
            'description': 'Already managed',
            'instructions': 'Managed instructions',
        }
    )

    monkeypatch.setenv('LANGBOT_DATA_ROOT', str(tmp_path / 'data'))

    await service.create_skill(
        {
            'name': 'nested-skill',
            'package_root': str(managed_root),
            'display_name': '',
            'description': '',
            'instructions': '',
        }
    )

    copied_root = tmp_path / 'data' / 'skills' / 'nested-skill'
    assert not copied_root.exists()
    content = (managed_root / 'SKILL.md').read_text(encoding='utf-8')
    assert 'display_name: Nested Skill' in content
    assert content.endswith('Managed instructions')


def _build_skill_archive() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr(
            'demo-repo-main/skills/nested-skill/SKILL.md',
            '---\nname: imported-skill\ndescription: Imported from GitHub archive\n---\n\nSkill instructions\n',
        )
    return stream.getvalue()


@pytest.mark.asyncio
async def test_install_from_github_supports_nested_skill_archive(skill_service, tmp_path, monkeypatch):
    archive_bytes = _build_skill_archive()

    class _FakeResponse:
        def __init__(self, content: bytes) -> None:
            self.content = content

        def raise_for_status(self) -> None:
            return None

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url: str) -> _FakeResponse:
            return _FakeResponse(archive_bytes)

    monkeypatch.setenv('LANGBOT_DATA_ROOT', str(tmp_path / 'data'))
    monkeypatch.setattr('src.langbot.pkg.api.http.service.skill.httpx.AsyncClient', _FakeAsyncClient)
    skill_service.get_skill = AsyncMock(return_value=None)

    result = await skill_service.install_from_github(
        {
            'asset_url': 'https://api.github.com/repos/example/demo-repo/zipball/main',
            'owner': 'example',
            'repo': 'demo-repo',
            'release_tag': 'main',
        }
    )

    expected_root = tmp_path / 'data' / 'skills' / 'demo-repo-nested-skill-main'
    assert result[0]['package_root'] == str(expected_root.resolve())
    assert (expected_root / 'SKILL.md').read_text(encoding='utf-8').endswith('Skill instructions\n')


@pytest.mark.asyncio
async def test_install_from_github_rejects_asset_url_outside_requested_repo(skill_service, tmp_path, monkeypatch):
    monkeypatch.setenv('LANGBOT_DATA_ROOT', str(tmp_path / 'data'))

    with pytest.raises(ValueError, match='owner/repo'):
        await skill_service.install_from_github(
            {
                'asset_url': 'https://api.github.com/repos/example/other-repo/zipball/main',
                'owner': 'example',
                'repo': 'demo-repo',
                'release_tag': 'main',
            }
        )


@pytest.mark.asyncio
async def test_install_from_github_rejects_zip_with_path_traversal(skill_service, tmp_path, monkeypatch):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('../escape.txt', 'boom')
    archive_bytes = stream.getvalue()

    class _FakeResponse:
        def __init__(self, content: bytes) -> None:
            self.content = content

        def raise_for_status(self) -> None:
            return None

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url: str) -> _FakeResponse:
            return _FakeResponse(archive_bytes)

    monkeypatch.setenv('LANGBOT_DATA_ROOT', str(tmp_path / 'data'))
    monkeypatch.setattr('src.langbot.pkg.api.http.service.skill.httpx.AsyncClient', _FakeAsyncClient)

    with pytest.raises(ValueError, match='unsafe path'):
        await skill_service.install_from_github(
            {
                'asset_url': 'https://api.github.com/repos/example/demo-repo/zipball/main',
                'owner': 'example',
                'repo': 'demo-repo',
                'release_tag': 'main',
            }
        )


@pytest.mark.asyncio
async def test_skill_file_operations_stay_within_package_root(skill_service, tmp_path):
    skill_dir = tmp_path / 'mood-logger'
    skill_dir.mkdir()
    _create_skill_file(skill_dir / 'SKILL.md')
    (skill_dir / 'resources').mkdir()
    (skill_dir / 'resources' / 'keywords_zh.json').write_text('{"hello": 1}\n', encoding='utf-8')

    skill_record = {
        'name': 'mood-logger',
        'package_root': str(skill_dir),
        'entry_file': 'SKILL.md',
    }
    skill_service.get_skill = AsyncMock(return_value=skill_record)

    listed = await skill_service.list_skill_files('mood-logger', path='resources')
    assert listed['entries'] == [
        {
            'path': 'resources/keywords_zh.json',
            'name': 'keywords_zh.json',
            'is_dir': False,
            'size': os.path.getsize(skill_dir / 'resources' / 'keywords_zh.json'),
        }
    ]

    read_back = await skill_service.read_skill_file('mood-logger', 'resources/keywords_zh.json')
    assert read_back['content'] == '{"hello": 1}\n'

    written = await skill_service.write_skill_file('mood-logger', 'resources/affinity.py', 'print("ok")\n')
    assert written['path'] == 'resources/affinity.py'
    assert (skill_dir / 'resources' / 'affinity.py').read_text(encoding='utf-8') == 'print("ok")\n'


@pytest.mark.asyncio
async def test_skill_file_operations_reject_path_traversal(skill_service, tmp_path):
    skill_dir = tmp_path / 'mood-logger'
    skill_dir.mkdir()
    _create_skill_file(skill_dir / 'SKILL.md')

    skill_service.get_skill = AsyncMock(
        return_value={
            'name': 'mood-logger',
            'package_root': str(skill_dir),
            'entry_file': 'SKILL.md',
        }
    )

    with pytest.raises(ValueError, match='path must stay within the skill package root'):
        await skill_service.read_skill_file('mood-logger', '../outside.txt')


@pytest.mark.asyncio
async def test_update_skill_rejects_package_root_change(tmp_path):
    service = SkillService(SimpleNamespace(skill_mgr=SimpleNamespace(reload_skills=AsyncMock())))
    skill_root = tmp_path / 'data' / 'skills' / 'writer'
    service.get_skill = AsyncMock(
        return_value={
            'name': 'writer',
            'package_root': str(skill_root.resolve()),
            'display_name': 'Writer',
            'description': 'Writes things',
            'instructions': 'Do work',
        }
    )

    with pytest.raises(ValueError, match='Updating package_root is not supported'):
        await service.update_skill('writer', {'package_root': str(tmp_path / 'other-root')})


@pytest.mark.asyncio
async def test_delete_skill_removes_managed_skill_directory(tmp_path, monkeypatch):
    managed_root = tmp_path / 'data' / 'skills' / 'self-improving-agent'
    managed_root.mkdir(parents=True)
    _create_skill_file(managed_root / 'SKILL.md')

    service = SkillService(SimpleNamespace(skill_mgr=SimpleNamespace(reload_skills=AsyncMock())))
    service.get_skill = AsyncMock(
        return_value={
            'name': 'self-improving-agent',
            'package_root': str(managed_root.resolve()),
        }
    )

    monkeypatch.setenv('LANGBOT_DATA_ROOT', str(tmp_path / 'data'))

    result = await service.delete_skill('self-improving-agent')

    assert result is True
    assert not managed_root.exists()


@pytest.mark.asyncio
async def test_delete_skill_removes_managed_install_root_for_nested_package(tmp_path, monkeypatch):
    install_root = tmp_path / 'data' / 'skills' / 'demo-repo'
    package_root = install_root / 'skills' / 'nested-skill'
    package_root.mkdir(parents=True)
    _create_skill_file(package_root / 'SKILL.md')

    service = SkillService(SimpleNamespace(skill_mgr=SimpleNamespace(reload_skills=AsyncMock())))
    service.get_skill = AsyncMock(
        return_value={
            'name': 'nested-skill',
            'package_root': str(package_root.resolve()),
        }
    )

    monkeypatch.setenv('LANGBOT_DATA_ROOT', str(tmp_path / 'data'))

    await service.delete_skill('nested-skill')

    assert not install_root.exists()


@pytest.mark.asyncio
async def test_delete_skill_rejects_external_package_directory(tmp_path, monkeypatch):
    external_root = tmp_path / 'external-skills' / 'manual-skill'
    external_root.mkdir(parents=True)
    _create_skill_file(external_root / 'SKILL.md')

    service = SkillService(SimpleNamespace(skill_mgr=SimpleNamespace(reload_skills=AsyncMock())))
    service.get_skill = AsyncMock(
        return_value={
            'name': 'manual-skill',
            'package_root': str(external_root.resolve()),
        }
    )

    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match='Only managed skills under data/skills'):
        await service.delete_skill('manual-skill')
