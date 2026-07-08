from __future__ import annotations

import io
import inspect
import os
import posixpath
import zipfile
from typing import Optional
from urllib.parse import quote, unquote, urlparse

import httpx

from ....core import app
from ....skill.utils import parse_frontmatter


_PUBLIC_SKILL_FIELDS = (
    'name',
    'display_name',
    'description',
    'instructions',
    'package_root',
    'created_at',
    'updated_at',
)

_GITHUB_ASSET_HOSTS = {
    'github.com',
    'api.github.com',
    'objects.githubusercontent.com',
    'githubusercontent.com',
    'raw.githubusercontent.com',
    'codeload.github.com',
}


class SkillService:
    """Filesystem-backed skill management service."""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    def _box_service(self):
        box_service = getattr(self.ap, 'box_service', None)
        if box_service is not None and getattr(box_service, 'available', False):
            return box_service
        return None

    def _require_box(self, action: str):
        """Return the Box service or raise if it is not available.

        Box is the only source of truth for skills. Every read and write
        operation goes through it — there is no local-filesystem fallback.
        """
        box_service = self._box_service()
        if box_service is not None:
            return box_service
        ap_box = getattr(self.ap, 'box_service', None)
        if ap_box is None:
            reason = 'not initialised'
        elif not getattr(ap_box, 'enabled', True):
            reason = 'disabled in config (box.enabled = false)'
        else:
            connector_error = getattr(ap_box, '_connector_error', '') or 'currently unavailable'
            reason = f'unavailable: {connector_error}'
        raise ValueError(
            f'{action} requires the Box runtime, which is {reason}. '
            f'Enable Box in config.yaml (box.enabled = true) and ensure the '
            f'runtime is reachable before retrying.'
        )

    def _require_box_for_write(self, action: str) -> None:
        """Backwards-compatible alias preserved for clarity at call sites."""
        self._require_box(action)

    @staticmethod
    def _serialize_skill(skill: dict) -> dict:
        return {field: skill.get(field) for field in _PUBLIC_SKILL_FIELDS if field in skill}

    async def list_skills(self) -> list[dict]:
        # When Box is unavailable, surface an empty list rather than raising —
        # the skills page should render cleanly, and the UI separately renders
        # a "Box disabled / unavailable" banner via useBoxStatus.
        box_service = self._box_service()
        if box_service is None:
            return []
        return [self._serialize_skill(skill) for skill in await box_service.list_skills()]

    async def get_skill(self, skill_name: str) -> Optional[dict]:
        box_service = self._box_service()
        if box_service is None:
            return None
        skill = await box_service.get_skill(skill_name)
        return self._serialize_skill(skill) if skill else None

    async def get_skill_by_name(self, name: str) -> Optional[dict]:
        return await self.get_skill(name)

    async def create_skill(self, data: dict) -> dict:
        box_service = self._require_box('Creating a skill')
        created = await box_service.create_skill(data)
        await self._reload_skills()
        return self._serialize_skill(created)

    async def update_skill(self, skill_name: str, data: dict) -> dict:
        box_service = self._require_box('Editing a skill')
        updated = await box_service.update_skill(skill_name, data)
        await self._reload_skills()
        return self._serialize_skill(updated)

    async def delete_skill(self, skill_name: str) -> bool:
        box_service = self._require_box('Deleting a skill')
        await box_service.delete_skill(skill_name)
        await self._reload_skills()
        return True

    async def list_skill_files(
        self,
        skill_name: str,
        path: str = '.',
        include_hidden: bool = False,
        max_entries: int = 200,
    ) -> dict:
        box_service = self._require_box('Browsing skill files')
        return await box_service.list_skill_files(skill_name, path, include_hidden, max_entries)

    async def read_skill_file(self, skill_name: str, path: str) -> dict:
        box_service = self._require_box('Reading a skill file')
        return await box_service.read_skill_file(skill_name, path)

    async def write_skill_file(self, skill_name: str, path: str, content: str) -> dict:
        box_service = self._require_box('Editing skill files')
        result = await box_service.write_skill_file(skill_name, path, content)
        await self._reload_skills()
        return result

    async def install_from_github(self, data: dict) -> list[dict]:
        box_service = self._require_box('Installing a skill from GitHub')
        owner = str(data['owner']).strip()
        repo = str(data['repo']).strip()
        release_tag = str(data.get('release_tag', '')).strip()
        raw_asset_url = str(data['asset_url']).strip()
        if self._is_github_skill_md_url(raw_asset_url):
            return await self._install_github_skill_md(raw_asset_url, owner=owner, repo=repo, data=data)

        asset_url = self._validate_github_asset_url(raw_asset_url, owner=owner, repo=repo, release_tag=release_tag)
        source_subdir = str(data.get('source_subdir', '') or '').strip()

        zip_bytes = await self._download_github_asset(asset_url)
        filename = f'{repo}-{release_tag.lstrip("v").replace("/", "-") or "source"}.zip'
        installed = await box_service.install_skill_zip(
            zip_bytes,
            filename,
            source_paths=data.get('source_paths') or [],
            source_path=str(data.get('source_path', '') or ''),
            source_subdir=source_subdir,
        )
        await self._reload_skills()
        return [self._serialize_skill(skill) for skill in installed]

    async def preview_install_from_github(self, data: dict) -> list[dict]:
        box_service = self._require_box('Previewing a skill from GitHub')
        owner = str(data['owner']).strip()
        repo = str(data['repo']).strip()
        release_tag = str(data.get('release_tag', '')).strip()
        raw_asset_url = str(data['asset_url']).strip()
        if self._is_github_skill_md_url(raw_asset_url):
            return await self._preview_github_skill_md(raw_asset_url, owner=owner, repo=repo)

        asset_url = self._validate_github_asset_url(raw_asset_url, owner=owner, repo=repo, release_tag=release_tag)
        source_subdir = str(data.get('source_subdir', '') or '').strip()

        zip_bytes = await self._download_github_asset(asset_url)
        return await box_service.preview_skill_zip(
            zip_bytes,
            f'{repo}-{release_tag.lstrip("v").replace("/", "-") or "source"}.zip',
            source_subdir=source_subdir,
        )

    async def install_from_zip_upload(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        source_paths: list[str] | None = None,
        source_path: str = '',
    ) -> list[dict]:
        box_service = self._require_box('Installing a skill from upload')
        installed = await box_service.install_skill_zip(
            file_bytes,
            filename,
            source_paths=source_paths or [],
            source_path=source_path,
        )
        await self._reload_skills()
        return [self._serialize_skill(skill) for skill in installed]

    async def preview_install_from_zip_upload(self, *, file_bytes: bytes, filename: str) -> list[dict]:
        box_service = self._require_box('Previewing a skill upload')
        return await box_service.preview_skill_zip(file_bytes, filename)

    async def _install_github_skill_md(self, asset_url: str, *, owner: str, repo: str, data: dict) -> list[dict]:
        box_service = self._require_box('Installing a skill from GitHub')
        zip_bytes, filename, _package_name = await self._download_github_skill_directory_as_zip(
            asset_url,
            owner=owner,
            repo=repo,
        )

        installed = await box_service.install_skill_zip(
            zip_bytes,
            filename,
            source_paths=data.get('source_paths') or [],
            source_path=str(data.get('source_path', '') or ''),
            target_suffix='',
        )
        await self._reload_skills()
        return [self._serialize_skill(skill) for skill in installed]

    async def _preview_github_skill_md(self, asset_url: str, *, owner: str, repo: str) -> list[dict]:
        box_service = self._require_box('Previewing a skill from GitHub')
        zip_bytes, _filename, package_name = await self._download_github_skill_directory_as_zip(
            asset_url,
            owner=owner,
            repo=repo,
        )
        return await box_service.preview_skill_zip(zip_bytes, f'{package_name}.zip', target_suffix='')

    async def reload_skills(self) -> list[dict]:
        await self._reload_skills()
        return await self.list_skills()

    async def scan_directory_async(self, path: str) -> dict:
        box_service = self._require_box('Scanning a skill directory')
        return await box_service.scan_skill_directory(path)

    async def _reload_skills(self) -> None:
        skill_mgr = getattr(self.ap, 'skill_mgr', None)
        reload_skills = getattr(skill_mgr, 'reload_skills', None)
        if not callable(reload_skills):
            return
        result = reload_skills()
        if inspect.isawaitable(result):
            await result

    async def _download_github_asset(self, asset_url: str) -> bytes:
        async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
            resp = await client.get(asset_url)
            resp.raise_for_status()
            return resp.content

    async def _download_github_skill_directory_as_zip(
        self, asset_url: str, *, owner: str, repo: str
    ) -> tuple[bytes, str, str]:
        info = self._parse_github_skill_md_url(asset_url, owner=owner, repo=repo)
        archive_url = f'https://codeload.github.com/{owner}/{repo}/zip/{quote(info["ref"], safe="/")}'
        archive_bytes = await self._download_github_asset(archive_url)

        try:
            source_archive = zipfile.ZipFile(io.BytesIO(archive_bytes), 'r')
        except zipfile.BadZipFile as exc:
            raise ValueError('GitHub repository archive must be a valid .zip archive') from exc

        with source_archive as source_zip:
            skill_entry = self._find_github_skill_archive_entry(source_zip, info['file_path'])
            try:
                skill_md_content = source_zip.read(skill_entry).decode('utf-8')
            except UnicodeDecodeError as exc:
                raise ValueError('GitHub SKILL.md must be valid UTF-8 text') from exc

            package_name = self._resolve_github_skill_md_package_name(skill_md_content, info['package_name'])
            source_skill_dir = posixpath.dirname(posixpath.normpath(skill_entry.filename))

            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as target_zip:
                self._copy_github_skill_directory_to_zip(source_zip, target_zip, source_skill_dir, package_name)
        return buffer.getvalue(), f'{package_name}.zip', package_name

    def _find_github_skill_archive_entry(self, archive: zipfile.ZipFile, file_path: str) -> zipfile.ZipInfo:
        normalized_file_path = posixpath.normpath(file_path).lower()
        for member in archive.infolist():
            if member.is_dir():
                continue
            normalized_member = posixpath.normpath(member.filename)
            path_parts = normalized_member.split('/', 1)
            if len(path_parts) != 2:
                continue
            archive_relative_path = path_parts[1].lower()
            if archive_relative_path == normalized_file_path:
                return member
        raise ValueError(f'GitHub archive does not contain requested SKILL.md: {file_path}')

    def _copy_github_skill_directory_to_zip(
        self,
        source_zip: zipfile.ZipFile,
        target_zip: zipfile.ZipFile,
        source_skill_dir: str,
        package_name: str,
    ) -> None:
        normalized_source_dir = posixpath.normpath(source_skill_dir)
        source_prefix = f'{normalized_source_dir}/'
        copied_files = 0

        for member in source_zip.infolist():
            normalized_member = posixpath.normpath(member.filename)
            if normalized_member != normalized_source_dir and not normalized_member.startswith(source_prefix):
                continue

            relative_path = posixpath.relpath(normalized_member, normalized_source_dir)
            if relative_path in ('', '.'):
                continue
            if relative_path.startswith('../') or relative_path == '..' or posixpath.isabs(relative_path):
                raise ValueError(f'GitHub archive contains an unsafe skill path: {member.filename}')

            target_name = f'{package_name}/{relative_path}'
            if member.is_dir() and not target_name.endswith('/'):
                target_name = f'{target_name}/'
            target_info = zipfile.ZipInfo(target_name, date_time=member.date_time)
            target_info.external_attr = member.external_attr
            target_info.compress_type = zipfile.ZIP_DEFLATED

            if member.is_dir():
                target_zip.writestr(target_info, b'')
                continue

            target_zip.writestr(target_info, source_zip.read(member))
            copied_files += 1

        if copied_files == 0:
            raise ValueError('GitHub skill directory is empty')

    def _uploaded_skill_target_stem(self, filename: str) -> str:
        stem = os.path.splitext(os.path.basename(str(filename or '').strip()))[0]
        safe_stem = ''.join(ch if ch.isalnum() or ch in ('-', '_') else '-' for ch in stem).strip('-_')
        if not safe_stem:
            safe_stem = 'uploaded-skill'
        return safe_stem

    @staticmethod
    def _is_github_skill_md_url(asset_url: str) -> bool:
        parsed = urlparse(str(asset_url or '').strip())
        normalized_path = posixpath.normpath(parsed.path or '/')
        return normalized_path.lower().endswith('/skill.md')

    def _parse_github_skill_md_url(self, asset_url: str, *, owner: str, repo: str) -> dict:
        parsed = urlparse(str(asset_url or '').strip())
        if parsed.scheme != 'https' or not parsed.netloc:
            raise ValueError('asset_url must be a valid HTTPS GitHub SKILL.md URL')

        host = parsed.netloc.lower()
        path_parts = [unquote(part) for part in (parsed.path or '').split('/') if part]
        if host == 'github.com':
            if (
                len(path_parts) < 5
                or path_parts[0] != owner
                or path_parts[1] != repo
                or path_parts[2]
                not in (
                    'blob',
                    'raw',
                )
            ):
                raise ValueError('GitHub SKILL.md URL must point to the requested owner/repo blob path')
            ref = path_parts[3]
            file_path = '/'.join(path_parts[4:])
        elif host == 'raw.githubusercontent.com':
            if len(path_parts) < 4 or path_parts[0] != owner or path_parts[1] != repo:
                raise ValueError('GitHub SKILL.md URL must point to the requested owner/repo raw path')
            ref = path_parts[2]
            file_path = '/'.join(path_parts[3:])
        else:
            raise ValueError('asset_url must point to a GitHub SKILL.md file')

        normalized_file_path = posixpath.normpath(file_path)
        normalized_file_path_lower = normalized_file_path.lower()
        if normalized_file_path_lower != 'skill.md' and not normalized_file_path_lower.endswith('/skill.md'):
            raise ValueError('GitHub skill import requires a URL ending with SKILL.md')

        parent_dir = posixpath.basename(posixpath.dirname(normalized_file_path)) or repo
        return {
            'ref': ref,
            'file_path': normalized_file_path,
            'package_name': self._uploaded_skill_target_stem(parent_dir),
        }

    def _resolve_github_skill_md_package_name(self, content: str, fallback: str) -> str:
        metadata, _instructions = parse_frontmatter(content)
        candidate = str(metadata.get('name') or fallback or '').strip()
        try:
            return self._validate_skill_name(candidate)
        except ValueError:
            return self._validate_skill_name(fallback)

    @staticmethod
    def _validate_github_asset_url(asset_url: str, *, owner: str, repo: str, release_tag: str) -> str:
        parsed = urlparse(str(asset_url).strip())
        if parsed.scheme != 'https' or not parsed.netloc:
            raise ValueError('asset_url must be a valid HTTPS GitHub asset URL')

        host = parsed.netloc.lower()
        if host not in _GITHUB_ASSET_HOSTS:
            raise ValueError('asset_url must point to a GitHub-hosted release asset or archive')

        normalized_path = posixpath.normpath(parsed.path or '/')
        allowed_prefixes = [
            f'/repos/{owner}/{repo}/',
            f'/{owner}/{repo}/',
        ]
        if not any(normalized_path.startswith(prefix) for prefix in allowed_prefixes):
            raise ValueError('asset_url does not match the requested owner/repo')

        if release_tag and release_tag not in parsed.path and release_tag not in parsed.query:
            raise ValueError('asset_url does not match the requested release_tag')

        return parsed.geturl()

    @staticmethod
    def _validate_skill_name(name: str) -> str:
        name = str(name or '').strip()
        if not name:
            raise ValueError('Skill name is required')
        if not name.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Skill name can only contain letters, numbers, hyphens and underscores')
        if len(name) > 64:
            raise ValueError('Skill name cannot exceed 64 characters')
        return name
