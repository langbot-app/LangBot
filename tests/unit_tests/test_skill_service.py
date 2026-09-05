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


class TestSkillRepositoryBoundary:
    """Skill management and reads remain available without Box execution."""

    @staticmethod
    def _ap_with_repository():
        repository = SimpleNamespace(
            list_skills=AsyncMock(return_value=[{'name': 'x', 'instructions': 'Do work'}]),
            get_skill=AsyncMock(return_value={'name': 'x', 'instructions': 'Do work', 'revision': 'sha256:x'}),
            create_skill=AsyncMock(return_value={'name': 'x', 'instructions': 'Do work'}),
            update_skill=AsyncMock(return_value={'name': 'x', 'instructions': 'Updated'}),
            delete_skill=AsyncMock(),
            read_skill_file=AsyncMock(return_value={'path': 'a.txt', 'content': 'hello'}),
            write_skill_file=AsyncMock(return_value={'path': 'a.txt'}),
        )
        return SimpleNamespace(
            skill_mgr=SimpleNamespace(reload_skills=AsyncMock()),
            workspace_service=_workspace_service(),
            box_service=SimpleNamespace(available=False, enabled=False),
            skill_repository=repository,
        )

    @pytest.mark.asyncio
    async def test_list_and_read_work_when_box_disabled(self):
        ap = self._ap_with_repository()
        service = SkillService(ap)

        assert await service.list_skills(_CONTEXT) == [{'name': 'x', 'instructions': 'Do work'}]
        assert await service.read_skill_file(_CONTEXT, 'x', 'a.txt') == {
            'path': 'a.txt',
            'content': 'hello',
        }
        ap.skill_repository.read_skill_file.assert_awaited_once_with(_CONTEXT, 'x', 'a.txt')

    @pytest.mark.asyncio
    async def test_create_update_and_write_work_when_box_disabled(self):
        ap = self._ap_with_repository()
        service = SkillService(ap)

        await service.create_skill(_CONTEXT, {'name': 'x'})
        await service.update_skill(_CONTEXT, 'x', {'instructions': 'Updated'})
        await service.write_skill_file(_CONTEXT, 'x', 'a.txt', 'hello')

        ap.skill_repository.create_skill.assert_awaited_once_with(_CONTEXT, {'name': 'x'})
        ap.skill_repository.update_skill.assert_awaited_once_with(_CONTEXT, 'x', {'instructions': 'Updated'})
        ap.skill_repository.write_skill_file.assert_awaited_once_with(_CONTEXT, 'x', 'a.txt', 'hello')

    @pytest.mark.asyncio
    async def test_get_skill_returns_repository_revision(self):
        ap = self._ap_with_repository()
        service = SkillService(ap)

        skill = await service.get_skill(_CONTEXT, 'x')

        assert skill['revision'] == 'sha256:x'
        ap.skill_repository.get_skill.assert_awaited_once_with(_CONTEXT, 'x', snapshot=True)

    @pytest.mark.asyncio
    async def test_missing_repository_is_explicit(self):
        service = SkillService(
            SimpleNamespace(
                skill_mgr=SimpleNamespace(reload_skills=AsyncMock()),
                workspace_service=_workspace_service(),
            )
        )
        with pytest.raises(ValueError, match='repository is not initialised'):
            await service.create_skill(_CONTEXT, {'name': 'x'})


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
