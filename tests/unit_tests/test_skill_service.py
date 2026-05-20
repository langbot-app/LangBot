from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.http.service.skill import SkillService


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


class TestRequireBoxForWrite:
    """Box is the only source of truth for skills — there is no local
    filesystem fallback. Every write and (most) read methods refuse cleanly
    when the Box runtime is disabled, unreachable, or simply not installed."""

    def _ap_with_disabled_box(self):
        return SimpleNamespace(
            skill_mgr=SimpleNamespace(reload_skills=AsyncMock()),
            box_service=SimpleNamespace(
                available=False,
                enabled=False,
                _connector_error='Box runtime is disabled in config (box.enabled = false)',
            ),
        )

    def _ap_with_failed_box(self):
        return SimpleNamespace(
            skill_mgr=SimpleNamespace(reload_skills=AsyncMock()),
            box_service=SimpleNamespace(
                available=False,
                enabled=True,
                _connector_error='docker daemon not running',
            ),
        )

    @pytest.mark.asyncio
    async def test_create_skill_refused_when_box_disabled(self):
        service = SkillService(self._ap_with_disabled_box())
        with pytest.raises(ValueError, match='disabled in config'):
            await service.create_skill({'name': 'x'})

    @pytest.mark.asyncio
    async def test_create_skill_refused_when_box_failed(self):
        service = SkillService(self._ap_with_failed_box())
        with pytest.raises(ValueError, match='docker daemon not running'):
            await service.create_skill({'name': 'x'})

    @pytest.mark.asyncio
    async def test_update_skill_refused_when_box_disabled(self):
        service = SkillService(self._ap_with_disabled_box())
        with pytest.raises(ValueError, match='Editing a skill requires the Box runtime'):
            await service.update_skill('x', {})

    @pytest.mark.asyncio
    async def test_write_skill_file_refused_when_box_disabled(self):
        service = SkillService(self._ap_with_disabled_box())
        with pytest.raises(ValueError, match='Editing skill files requires the Box runtime'):
            await service.write_skill_file('x', 'a.txt', 'hi')

    @pytest.mark.asyncio
    async def test_install_from_github_refused_when_box_disabled(self):
        service = SkillService(self._ap_with_disabled_box())
        with pytest.raises(ValueError, match='Installing a skill from GitHub'):
            await service.install_from_github({'owner': 'o', 'repo': 'r', 'asset_url': 'https://example/x.zip'})

    @pytest.mark.asyncio
    async def test_install_from_zip_upload_refused_when_box_disabled(self):
        service = SkillService(self._ap_with_disabled_box())
        with pytest.raises(ValueError, match='Installing a skill from upload'):
            await service.install_from_zip_upload(file_bytes=b'', filename='x.zip')

    @pytest.mark.asyncio
    async def test_create_skill_refused_when_box_service_missing_entirely(self):
        """No ap.box_service attribute at all (truly minimal setup):
        Box is the only source of truth, so creation must still refuse."""
        service = SkillService(SimpleNamespace(skill_mgr=SimpleNamespace(reload_skills=AsyncMock())))
        with pytest.raises(ValueError, match='not initialised'):
            await service.create_skill({'name': 'x'})

    @pytest.mark.asyncio
    async def test_list_skills_returns_empty_when_box_unavailable(self):
        """list_skills should render an empty surface (not crash) so the
        skills page can show a banner instead of a broken state."""
        service = SkillService(self._ap_with_disabled_box())
        assert await service.list_skills() == []

    @pytest.mark.asyncio
    async def test_read_skill_file_refused_when_box_unavailable(self):
        service = SkillService(self._ap_with_disabled_box())
        with pytest.raises(ValueError, match='Reading a skill file'):
            await service.read_skill_file('x', 'a.txt')
