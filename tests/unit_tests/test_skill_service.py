from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langbot_plugin.entities.io.errors import ActionCallTimeoutError

from langbot.pkg.api.http.service.skill import SkillService


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
    async def test_list_skills_returns_empty_when_box_action_times_out(self):
        """A transient Box list failure should not break unrelated extension surfaces."""
        box_service = SimpleNamespace(
            available=True,
            list_skills=AsyncMock(side_effect=ActionCallTimeoutError('Action box_list_skills call timed out')),
        )
        service = SkillService(SimpleNamespace(skill_mgr=SimpleNamespace(reload_skills=AsyncMock()), box_service=box_service))

        assert await service.list_skills() == []

    @pytest.mark.asyncio
    async def test_read_skill_file_refused_when_box_unavailable(self):
        service = SkillService(self._ap_with_disabled_box())
        with pytest.raises(ValueError, match='Reading a skill file'):
            await service.read_skill_file('x', 'a.txt')
