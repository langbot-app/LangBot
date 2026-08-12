import io
from types import SimpleNamespace
from unittest.mock import AsyncMock
import zipfile

import httpx
import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.api.http.service.skill import SkillService


_CONTEXT = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid='workspace-a',
    placement_generation=1,
)


def _workspace_service():
    return SimpleNamespace(
        get_execution_binding=AsyncMock(return_value=SimpleNamespace(instance_uuid=_CONTEXT.instance_uuid))
    )


class TestRequireBoxForWrite:
    """Box is the only source of truth for skills — there is no local
    filesystem fallback. Every write and (most) read methods refuse cleanly
    when the Box runtime is disabled, unreachable, or simply not installed."""

    def _ap_with_disabled_box(self):
        return SimpleNamespace(
            skill_mgr=SimpleNamespace(reload_skills=AsyncMock()),
            workspace_service=_workspace_service(),
            box_service=SimpleNamespace(
                available=False,
                enabled=False,
                _connector_error='Box runtime is disabled in config (box.enabled = false)',
            ),
        )

    def _ap_with_failed_box(self):
        return SimpleNamespace(
            skill_mgr=SimpleNamespace(reload_skills=AsyncMock()),
            workspace_service=_workspace_service(),
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
            await service.create_skill(_CONTEXT, {'name': 'x'})

    @pytest.mark.asyncio
    async def test_create_skill_refused_when_box_failed(self):
        service = SkillService(self._ap_with_failed_box())
        with pytest.raises(ValueError, match='docker daemon not running'):
            await service.create_skill(_CONTEXT, {'name': 'x'})

    @pytest.mark.asyncio
    async def test_update_skill_refused_when_box_disabled(self):
        service = SkillService(self._ap_with_disabled_box())
        with pytest.raises(ValueError, match='Editing a skill requires the Box runtime'):
            await service.update_skill(_CONTEXT, 'x', {})

    @pytest.mark.asyncio
    async def test_write_skill_file_refused_when_box_disabled(self):
        service = SkillService(self._ap_with_disabled_box())
        with pytest.raises(ValueError, match='Editing skill files requires the Box runtime'):
            await service.write_skill_file(_CONTEXT, 'x', 'a.txt', 'hi')

    @pytest.mark.asyncio
    async def test_install_from_github_refused_when_box_disabled(self):
        service = SkillService(self._ap_with_disabled_box())
        with pytest.raises(ValueError, match='Installing a skill from GitHub'):
            await service.install_from_github(
                _CONTEXT,
                {'owner': 'o', 'repo': 'r', 'asset_url': 'https://example/x.zip'},
            )

    @pytest.mark.asyncio
    async def test_install_from_zip_upload_refused_when_box_disabled(self):
        service = SkillService(self._ap_with_disabled_box())
        with pytest.raises(ValueError, match='Installing a skill from upload'):
            await service.install_from_zip_upload(
                _CONTEXT,
                file_bytes=b'',
                filename='x.zip',
            )

    @pytest.mark.asyncio
    async def test_create_skill_refused_when_box_service_missing_entirely(self):
        """No ap.box_service attribute at all (truly minimal setup):
        Box is the only source of truth, so creation must still refuse."""
        service = SkillService(
            SimpleNamespace(
                skill_mgr=SimpleNamespace(reload_skills=AsyncMock()),
                workspace_service=_workspace_service(),
            )
        )
        with pytest.raises(ValueError, match='not initialised'):
            await service.create_skill(_CONTEXT, {'name': 'x'})

    @pytest.mark.asyncio
    async def test_list_skills_returns_empty_when_box_unavailable(self):
        """list_skills should render an empty surface (not crash) so the
        skills page can show a banner instead of a broken state."""
        service = SkillService(self._ap_with_disabled_box())
        assert await service.list_skills(_CONTEXT) == []

    @pytest.mark.asyncio
    async def test_read_skill_file_refused_when_box_unavailable(self):
        service = SkillService(self._ap_with_disabled_box())
        with pytest.raises(ValueError, match='Reading a skill file'):
            await service.read_skill_file(_CONTEXT, 'x', 'a.txt')


class TestGithubSkillArchiveLimits:
    @staticmethod
    def _service() -> SkillService:
        return SkillService(SimpleNamespace())

    @pytest.mark.asyncio
    async def test_download_rejects_declared_oversized_archive(self, monkeypatch):
        import langbot.pkg.api.http.service.skill as skill_module

        real_client = httpx.AsyncClient

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={'content-length': str(10 * 1024 * 1024 + 1)},
                content=b'',
                request=request,
            )

        monkeypatch.setattr(
            skill_module.httpx,
            'AsyncClient',
            lambda **_kwargs: real_client(transport=httpx.MockTransport(handler)),
        )

        with pytest.raises(ValueError, match='compressed size limit'):
            await self._service()._download_github_asset('https://codeload.github.com/o/r/zip/main')

    def test_copy_rejects_high_compression_ratio_before_extracting(self):
        source_buffer = io.BytesIO()
        with zipfile.ZipFile(source_buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('repo-main/skill/SKILL.md', b'---\nname: safe\n---\n')
            archive.writestr('repo-main/skill/bomb.bin', b'0' * (1024 * 1024))

        source_buffer.seek(0)
        target_buffer = io.BytesIO()
        with (
            zipfile.ZipFile(source_buffer, 'r') as source_zip,
            zipfile.ZipFile(target_buffer, 'w', zipfile.ZIP_DEFLATED) as target_zip,
        ):
            with pytest.raises(ValueError, match='compression-ratio limit'):
                self._service()._copy_github_skill_directory_to_zip(
                    source_zip,
                    target_zip,
                    'repo-main/skill',
                    'safe',
                )
