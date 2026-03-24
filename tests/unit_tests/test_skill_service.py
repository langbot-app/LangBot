import io
import os
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.langbot.pkg.api.http.service.skill import SkillService


def _create_skill_file(path, body: str = 'Skill instructions') -> None:
    path.write_text(
        '---\n'
        'name: imported-skill\n'
        'description: Imported from local directory\n'
        '---\n\n'
        f'{body}\n',
        encoding='utf-8',
    )


@pytest.fixture
def skill_service():
    return SkillService(SimpleNamespace(skill_mgr=SimpleNamespace(refresh_skill_from_disk=lambda *_args, **_kwargs: True)))


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


def _build_skill_archive() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr(
            'demo-repo-main/skills/nested-skill/SKILL.md',
            '---\n'
            'name: imported-skill\n'
            'description: Imported from GitHub archive\n'
            '---\n\n'
            'Skill instructions\n',
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

    captured: dict = {}

    async def _fake_register_existing_skill(data: dict) -> dict:
        captured.update(data)
        skill_md_path = tmp_path / 'data' / 'skills' / 'demo-repo' / 'skills' / 'nested-skill' / 'SKILL.md'
        captured['skill_md_content'] = skill_md_path.read_text(encoding='utf-8')
        return data

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('src.langbot.pkg.api.http.service.skill.httpx.AsyncClient', _FakeAsyncClient)
    skill_service._register_existing_skill = AsyncMock(side_effect=_fake_register_existing_skill)

    result = await skill_service.install_from_github(
        {
            'asset_url': 'https://api.github.com/repos/example/demo-repo/zipball/main',
            'owner': 'example',
            'repo': 'demo-repo',
            'release_tag': 'main',
        }
    )

    expected_root = tmp_path / 'data' / 'skills' / 'demo-repo' / 'skills' / 'nested-skill'
    assert captured['name'] == 'imported-skill'
    assert captured['entry_file'] == 'SKILL.md'
    assert captured['package_root'] == str(expected_root.resolve())
    assert captured['skill_md_content'].endswith('Skill instructions\n')
    assert result['package_root'] == str(expected_root.resolve())


@pytest.mark.asyncio
async def test_skill_file_operations_stay_within_package_root(skill_service, tmp_path):
    skill_dir = tmp_path / 'mood-logger'
    skill_dir.mkdir()
    _create_skill_file(skill_dir / 'SKILL.md')
    (skill_dir / 'resources').mkdir()
    (skill_dir / 'resources' / 'keywords_zh.json').write_text('{"hello": 1}\n', encoding='utf-8')

    skill_record = {
        'uuid': 'uuid-mood',
        'name': 'mood-logger',
        'package_root': str(skill_dir),
        'entry_file': 'SKILL.md',
    }
    skill_service.get_skill = AsyncMock(return_value=skill_record)

    listed = await skill_service.list_skill_files('uuid-mood', path='resources')
    assert listed['entries'] == [
        {
            'path': 'resources/keywords_zh.json',
            'name': 'keywords_zh.json',
            'is_dir': False,
            'size': os.path.getsize(skill_dir / 'resources' / 'keywords_zh.json'),
        }
    ]

    read_back = await skill_service.read_skill_file('uuid-mood', 'resources/keywords_zh.json')
    assert read_back['content'] == '{"hello": 1}\n'

    written = await skill_service.write_skill_file('uuid-mood', 'resources/affinity.py', 'print("ok")\n')
    assert written['path'] == 'resources/affinity.py'
    assert (skill_dir / 'resources' / 'affinity.py').read_text(encoding='utf-8') == 'print("ok")\n'


@pytest.mark.asyncio
async def test_skill_file_operations_reject_path_traversal(skill_service, tmp_path):
    skill_dir = tmp_path / 'mood-logger'
    skill_dir.mkdir()
    _create_skill_file(skill_dir / 'SKILL.md')

    skill_service.get_skill = AsyncMock(
        return_value={
            'uuid': 'uuid-mood',
            'name': 'mood-logger',
            'package_root': str(skill_dir),
            'entry_file': 'SKILL.md',
        }
    )

    with pytest.raises(ValueError, match='path must stay within the skill package root'):
        await skill_service.read_skill_file('uuid-mood', '../outside.txt')


@pytest.mark.asyncio
async def test_delete_skill_removes_managed_skill_directory(tmp_path, monkeypatch):
    managed_root = tmp_path / 'data' / 'skills' / 'self-improving-agent'
    managed_root.mkdir(parents=True)
    _create_skill_file(managed_root / 'SKILL.md')

    service = SkillService(
        SimpleNamespace(
            persistence_mgr=SimpleNamespace(execute_async=AsyncMock()),
            skill_mgr=SimpleNamespace(reload_skills=AsyncMock()),
        )
    )
    service.get_skill = AsyncMock(
        return_value={
            'uuid': 'skill-1',
            'name': 'self-improving-agent',
            'package_root': str(managed_root.resolve()),
            'is_builtin': False,
        }
    )

    monkeypatch.chdir(tmp_path)

    result = await service.delete_skill('skill-1')

    assert result is True
    assert not managed_root.exists()


@pytest.mark.asyncio
async def test_delete_skill_removes_managed_install_root_for_nested_package(tmp_path, monkeypatch):
    install_root = tmp_path / 'data' / 'skills' / 'demo-repo'
    package_root = install_root / 'skills' / 'nested-skill'
    package_root.mkdir(parents=True)
    _create_skill_file(package_root / 'SKILL.md')

    service = SkillService(
        SimpleNamespace(
            persistence_mgr=SimpleNamespace(execute_async=AsyncMock()),
            skill_mgr=SimpleNamespace(reload_skills=AsyncMock()),
        )
    )
    service.get_skill = AsyncMock(
        return_value={
            'uuid': 'skill-2',
            'name': 'nested-skill',
            'package_root': str(package_root.resolve()),
            'is_builtin': False,
        }
    )

    monkeypatch.chdir(tmp_path)

    await service.delete_skill('skill-2')

    assert not install_root.exists()


@pytest.mark.asyncio
async def test_delete_skill_keeps_external_package_directory(tmp_path, monkeypatch):
    external_root = tmp_path / 'external-skills' / 'manual-skill'
    external_root.mkdir(parents=True)
    _create_skill_file(external_root / 'SKILL.md')

    service = SkillService(
        SimpleNamespace(
            persistence_mgr=SimpleNamespace(execute_async=AsyncMock()),
            skill_mgr=SimpleNamespace(reload_skills=AsyncMock()),
        )
    )
    service.get_skill = AsyncMock(
        return_value={
            'uuid': 'skill-3',
            'name': 'manual-skill',
            'package_root': str(external_root.resolve()),
            'is_builtin': False,
        }
    )

    monkeypatch.chdir(tmp_path)

    await service.delete_skill('skill-3')

    assert external_root.exists()
