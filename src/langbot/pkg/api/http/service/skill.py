from __future__ import annotations

import io
import inspect
import os
import posixpath
import shutil
import tempfile
import zipfile
from typing import Optional
from urllib.parse import urlparse

import httpx
import yaml

from ....core import app
from ....skill.utils import parse_frontmatter
from ....utils import paths

_FRONTMATTER_FIELDS = (
    'name',
    'display_name',
    'description',
    'auto_activate',
)

_PUBLIC_SKILL_FIELDS = (
    'name',
    'display_name',
    'description',
    'instructions',
    'package_root',
    'auto_activate',
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


def _build_skill_md(metadata: dict, instructions: str) -> str:
    frontmatter = {}
    for key in _FRONTMATTER_FIELDS:
        value = metadata.get(key)
        if value is None:
            continue
        if key == 'auto_activate' and value is True:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        frontmatter[key] = value

    if not frontmatter:
        return instructions

    frontmatter_text = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False).strip()
    return f'---\n{frontmatter_text}\n---\n\n{instructions}'


class SkillService:
    """Filesystem-backed skill management service."""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    @staticmethod
    def _serialize_skill(skill: dict) -> dict:
        return {field: skill.get(field) for field in _PUBLIC_SKILL_FIELDS if field in skill}

    async def list_skills(self) -> list[dict]:
        skills = [dict(skill) for skill in getattr(self.ap.skill_mgr, 'skills', {}).values()]
        skills.sort(key=lambda item: item.get('updated_at', ''), reverse=True)
        return [self._serialize_skill(skill) for skill in skills]

    async def get_skill(self, skill_name: str) -> Optional[dict]:
        skill = getattr(self.ap.skill_mgr, 'get_skill_by_name', lambda _name: None)(skill_name)
        return self._serialize_skill(skill) if skill else None

    async def get_skill_by_name(self, name: str) -> Optional[dict]:
        return await self.get_skill(name)

    async def create_skill(self, data: dict) -> dict:
        name = self._validate_skill_name(data.get('name', ''))
        if await self.get_skill_by_name(name):
            raise ValueError(f'Skill with name "{name}" already exists')

        package_root = self._normalize_package_root(data.get('package_root', ''))
        managed_root = self._managed_skill_path(name)
        target_root = managed_root
        imported_skill_data: dict | None = None

        if package_root and self._managed_install_root_for_package(package_root):
            if not os.path.isdir(package_root):
                raise ValueError(f'Directory does not exist: {package_root}')
            target_root = package_root
            imported_skill_data = self._read_skill_package(target_root)
        elif package_root and package_root != managed_root:
            if not os.path.isdir(package_root):
                raise ValueError(f'Directory does not exist: {package_root}')
            if os.path.exists(managed_root):
                raise ValueError(f'Skill directory already exists: {managed_root}')
            os.makedirs(os.path.dirname(managed_root), exist_ok=True)
            shutil.copytree(package_root, managed_root)
            imported_skill_data = self._read_skill_package(managed_root)
        else:
            os.makedirs(managed_root, exist_ok=True)

        metadata = {
            'name': name,
            'display_name': self._resolve_create_field(data, 'display_name', imported_skill_data, default=''),
            'description': self._resolve_create_field(data, 'description', imported_skill_data, default=''),
            'auto_activate': self._resolve_create_bool(data, 'auto_activate', imported_skill_data, default=True),
        }
        instructions = self._resolve_create_field(data, 'instructions', imported_skill_data, default='')
        self._write_skill_md(target_root, metadata, instructions)

        await self._reload_skills()
        created = await self.get_skill(name)
        if not created:
            raise ValueError(f'Failed to create skill "{name}"')
        return created

    async def update_skill(self, skill_name: str, data: dict) -> dict:
        skill = await self.get_skill(skill_name)
        if not skill:
            raise ValueError(f'Skill "{skill_name}" not found')

        requested_name = str(data.get('name', skill['name']) or skill['name']).strip()
        if requested_name != skill['name']:
            raise ValueError('Renaming skills is not supported')

        requested_package_root = str(data.get('package_root', '') or '').strip()
        existing_package_root = self._normalize_package_root(skill['package_root'])
        if requested_package_root and self._normalize_package_root(requested_package_root) != existing_package_root:
            raise ValueError('Updating package_root is not supported; recreate the skill to import a different package')

        metadata = {
            'name': skill['name'],
            'display_name': data.get('display_name', skill.get('display_name', '')),
            'description': data.get('description', skill.get('description', '')),
            'auto_activate': data.get('auto_activate', skill.get('auto_activate', True)),
        }
        instructions = str(data.get('instructions', skill.get('instructions', '')) or '')
        self._write_skill_md(skill['package_root'], metadata, instructions)

        await self._reload_skills()
        updated = await self.get_skill(skill_name)
        if not updated:
            raise ValueError(f'Skill "{skill_name}" not found after update')
        return updated

    async def delete_skill(self, skill_name: str) -> bool:
        skill = await self.get_skill(skill_name)
        if not skill:
            raise ValueError(f'Skill "{skill_name}" not found')

        package_root = self._normalize_package_root(skill['package_root'])
        managed_install_root = self._managed_install_root_for_package(package_root)
        if not managed_install_root:
            raise ValueError('Only managed skills under data/skills can be deleted via LangBot')

        shutil.rmtree(managed_install_root, ignore_errors=True)
        await self._reload_skills()
        return True

    async def list_skill_files(
        self,
        skill_name: str,
        path: str = '.',
        include_hidden: bool = False,
        max_entries: int = 200,
    ) -> dict:
        skill = await self.get_skill(skill_name)
        if not skill:
            raise ValueError(f'Skill "{skill_name}" not found')

        target_dir, relative_path = self._resolve_skill_path(skill, path, expect_directory=True)
        entries: list[dict] = []
        with os.scandir(target_dir) as iterator:
            for entry in sorted(iterator, key=lambda item: item.name):
                if not include_hidden and entry.name.startswith('.'):
                    continue
                entry_rel_path = entry.name if relative_path in ('', '.') else os.path.join(relative_path, entry.name)
                is_dir = entry.is_dir()
                entries.append(
                    {
                        'path': entry_rel_path.replace(os.sep, '/'),
                        'name': entry.name,
                        'is_dir': is_dir,
                        'size': None if is_dir else entry.stat().st_size,
                    }
                )
                if len(entries) >= max_entries:
                    break

        return {
            'skill': {'name': skill['name']},
            'base_path': '.' if relative_path in ('', '.') else relative_path.replace(os.sep, '/'),
            'entries': entries,
            'truncated': len(entries) >= max_entries,
        }

    async def read_skill_file(self, skill_name: str, path: str) -> dict:
        skill = await self.get_skill(skill_name)
        if not skill:
            raise ValueError(f'Skill "{skill_name}" not found')

        target_path, relative_path = self._resolve_skill_path(skill, path, expect_directory=False)
        if not os.path.isfile(target_path):
            raise ValueError(f'Skill file not found: {relative_path}')

        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError as exc:
            raise ValueError(f'Skill file is not valid UTF-8 text: {relative_path}') from exc

        return {
            'skill': {'name': skill['name']},
            'path': relative_path.replace(os.sep, '/'),
            'content': content,
        }

    async def write_skill_file(self, skill_name: str, path: str, content: str) -> dict:
        skill = await self.get_skill(skill_name)
        if not skill:
            raise ValueError(f'Skill "{skill_name}" not found')

        target_path, relative_path = self._resolve_skill_path(skill, path, expect_directory=False)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(content)

        skill_mgr = getattr(self.ap, 'skill_mgr', None)
        if skill_mgr is not None:
            refresh_skill = getattr(skill_mgr, 'refresh_skill_from_disk', None)
            if callable(refresh_skill):
                refresh_skill(skill.get('name', ''))

        return {
            'skill': {'name': skill['name']},
            'path': relative_path.replace(os.sep, '/'),
            'bytes_written': len(content.encode('utf-8')),
        }

    async def install_from_github(self, data: dict) -> list[dict]:
        owner = str(data['owner']).strip()
        repo = str(data['repo']).strip()
        release_tag = str(data.get('release_tag', '')).strip()
        asset_url = self._validate_github_asset_url(data['asset_url'], owner=owner, repo=repo, release_tag=release_tag)
        source_subdir = str(data.get('source_subdir', '') or '').strip()

        tmp_dir = tempfile.mkdtemp(prefix='langbot_skill_')
        try:
            skill_root = await self._download_github_skill_to_temp(asset_url, tmp_dir)
            skill_root = self._resolve_github_source_root(skill_root, source_subdir)
            previews = self._preview_skill_candidates(
                skill_root,
                base_target_name=repo,
                suffix=release_tag.lstrip('v').replace('/', '-') or 'source',
            )
            selected_previews = self._select_preview_candidates(previews, data)
            scanned = self._install_preview_candidates(skill_root, selected_previews)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        await self._reload_skills()
        return await self._resolve_installed_skills(scanned)

    async def preview_install_from_github(self, data: dict) -> list[dict]:
        owner = str(data['owner']).strip()
        repo = str(data['repo']).strip()
        release_tag = str(data.get('release_tag', '')).strip()
        asset_url = self._validate_github_asset_url(data['asset_url'], owner=owner, repo=repo, release_tag=release_tag)
        source_subdir = str(data.get('source_subdir', '') or '').strip()

        tmp_dir = tempfile.mkdtemp(prefix='langbot_skill_preview_')
        try:
            skill_root = await self._download_github_skill_to_temp(asset_url, tmp_dir)
            skill_root = self._resolve_github_source_root(skill_root, source_subdir)
            return self._preview_skill_candidates(
                skill_root,
                base_target_name=repo,
                suffix=release_tag.lstrip('v').replace('/', '-') or 'source',
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    async def install_from_zip_upload(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        source_paths: list[str] | None = None,
        source_path: str = '',
    ) -> list[dict]:
        if not file_bytes:
            raise ValueError('Uploaded file is empty')

        tmp_dir = tempfile.mkdtemp(prefix='langbot_skill_upload_')
        try:
            skill_root = self._extract_uploaded_skill_to_temp(file_bytes, tmp_dir)
            base_target_name = self._uploaded_skill_target_stem(filename)
            previews = self._preview_skill_candidates(
                skill_root,
                base_target_name=base_target_name,
                suffix='upload',
            )
            selected_previews = self._select_preview_candidates(
                previews,
                {'source_paths': source_paths or [], 'source_path': source_path},
            )
            scanned = self._install_preview_candidates(skill_root, selected_previews)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        await self._reload_skills()
        return await self._resolve_installed_skills(scanned)

    async def preview_install_from_zip_upload(self, *, file_bytes: bytes, filename: str) -> list[dict]:
        if not file_bytes:
            raise ValueError('Uploaded file is empty')

        tmp_dir = tempfile.mkdtemp(prefix='langbot_skill_upload_preview_')
        try:
            skill_root = self._extract_uploaded_skill_to_temp(file_bytes, tmp_dir)
            return self._preview_skill_candidates(
                skill_root,
                base_target_name=self._uploaded_skill_target_stem(filename),
                suffix='upload',
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    async def reload_skills(self) -> list[dict]:
        await self._reload_skills()
        return await self.list_skills()

    def scan_directory(self, path: str) -> dict:
        if not os.path.isdir(path):
            raise ValueError(f'Directory does not exist: {path}')

        discovered = self._discover_skill_directories(path, max_depth=2)
        if not discovered:
            raise ValueError(f'No SKILL.md found in {path} or its subdirectories (max depth: 2)')
        if len(discovered) > 1:
            candidates = ', '.join(found_path for found_path, _entry in discovered)
            raise ValueError(
                f'Multiple skill directories found in {path}. Please choose a more specific path: {candidates}'
            )

        package_root, entry_file = discovered[0]
        entry_path = os.path.join(package_root, entry_file)
        with open(entry_path, 'r', encoding='utf-8') as f:
            content = f.read()

        metadata, instructions = parse_frontmatter(content)
        dir_name = os.path.basename(os.path.normpath(package_root))
        return {
            'package_root': os.path.abspath(package_root),
            'entry_file': entry_file,
            'name': str(metadata.get('name') or dir_name).strip(),
            'display_name': str(metadata.get('display_name') or '').strip(),
            'description': str(metadata.get('description') or '').strip(),
            'instructions': instructions,
            'auto_activate': bool(metadata.get('auto_activate', True)),
        }

    async def _reload_skills(self) -> None:
        skill_mgr = getattr(self.ap, 'skill_mgr', None)
        reload_skills = getattr(skill_mgr, 'reload_skills', None)
        if not callable(reload_skills):
            return
        result = reload_skills()
        if inspect.isawaitable(result):
            await result

    def _read_skill_package(self, package_root: str) -> dict:
        entry = self._find_skill_entry(package_root)
        if entry is None:
            raise ValueError(f'No SKILL.md found in {package_root}')

        resolved_root, entry_file = entry
        entry_path = os.path.join(resolved_root, entry_file)
        with open(entry_path, 'r', encoding='utf-8') as f:
            content = f.read()

        metadata, instructions = parse_frontmatter(content)
        return {
            'entry_file': entry_file,
            'display_name': str(metadata.get('display_name') or '').strip(),
            'description': str(metadata.get('description') or '').strip(),
            'instructions': instructions,
            'auto_activate': bool(metadata.get('auto_activate', True)),
        }

    async def _download_github_skill_to_temp(self, asset_url: str, tmp_dir: str) -> str:
        zip_path = os.path.join(tmp_dir, 'skill.zip')
        async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
            resp = await client.get(asset_url)
            resp.raise_for_status()
            with open(zip_path, 'wb') as f:
                f.write(resp.content)

        extract_dir = os.path.join(tmp_dir, 'extracted')
        with zipfile.ZipFile(zip_path, 'r') as zf:
            self._safe_extract_zip(zf, extract_dir)

        entries = os.listdir(extract_dir)
        if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
            return os.path.join(extract_dir, entries[0])
        return extract_dir

    def _extract_uploaded_skill_to_temp(self, file_bytes: bytes, tmp_dir: str) -> str:
        extract_dir = os.path.join(tmp_dir, 'extracted')
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as zf:
                self._safe_extract_zip(zf, extract_dir)
        except zipfile.BadZipFile as exc:
            raise ValueError('Uploaded file must be a valid .zip archive') from exc

        entries = os.listdir(extract_dir)
        if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
            return os.path.join(extract_dir, entries[0])
        return extract_dir

    def _resolve_github_source_root(self, root_path: str, source_subdir: str) -> str:
        normalized = str(source_subdir or '').strip().replace('\\', '/').strip('/')
        if not normalized:
            return root_path

        target_path = os.path.realpath(os.path.join(root_path, normalized))
        root_path = os.path.realpath(root_path)
        if target_path != root_path and not target_path.startswith(f'{root_path}{os.sep}'):
            raise ValueError('source_subdir must stay within the downloaded repository')
        if not os.path.isdir(target_path):
            raise ValueError(f'source_subdir does not exist in the downloaded repository: {normalized}')
        return target_path

    def _uploaded_skill_target_stem(self, filename: str) -> str:
        stem = os.path.splitext(os.path.basename(str(filename or '').strip()))[0]
        safe_stem = ''.join(ch if ch.isalnum() or ch in ('-', '_') else '-' for ch in stem).strip('-_')
        if not safe_stem:
            safe_stem = 'uploaded-skill'
        return safe_stem

    def _build_preview_target_dir(self, base_target_name: str, source_path: str, suffix: str) -> str:
        relative = str(source_path or '').strip().replace('\\', '/').strip('/')
        leaf_name = relative.split('/')[-1] if relative else ''
        target_name = base_target_name
        if leaf_name and leaf_name != base_target_name:
            target_name = f'{base_target_name}-{leaf_name}'
        if suffix:
            target_name = f'{target_name}-{suffix}'
        return paths.get_data_path('skills', target_name)

    def _preview_skill_candidates(self, root_path: str, *, base_target_name: str, suffix: str) -> list[dict]:
        discovered = self._discover_skill_directories(root_path, max_depth=2)
        if not discovered:
            raise ValueError(f'No SKILL.md found in {root_path} or its subdirectories (max depth: 2)')

        previews: list[dict] = []
        for package_root, entry_file in discovered:
            entry_path = os.path.join(package_root, entry_file)
            with open(entry_path, 'r', encoding='utf-8') as f:
                content = f.read()

            metadata, instructions = parse_frontmatter(content)
            relative_path = os.path.relpath(package_root, root_path)
            if relative_path in ('', '.'):
                relative_path = ''

            dir_name = os.path.basename(os.path.normpath(package_root))
            previews.append(
                {
                    'source_path': relative_path.replace(os.sep, '/'),
                    'entry_file': entry_file,
                    'name': str(metadata.get('name') or dir_name).strip(),
                    'display_name': str(metadata.get('display_name') or '').strip(),
                    'description': str(metadata.get('description') or '').strip(),
                    'instructions': instructions,
                    'auto_activate': bool(metadata.get('auto_activate', True)),
                    'package_root': self._build_preview_target_dir(base_target_name, relative_path, suffix),
                }
            )

        previews.sort(key=lambda item: item['source_path'])
        return previews

    def _select_preview_candidates(self, previews: list[dict], data: dict) -> list[dict]:
        normalized_paths: list[str] = []
        raw_source_paths = data.get('source_paths', [])
        if isinstance(raw_source_paths, list):
            for source_path in raw_source_paths:
                normalized = str(source_path or '').strip().replace('\\', '/').strip('/')
                if normalized not in normalized_paths:
                    normalized_paths.append(normalized)

        legacy_source_path = str(data.get('source_path', '') or '').strip().replace('\\', '/').strip('/')
        if legacy_source_path and legacy_source_path not in normalized_paths:
            normalized_paths.append(legacy_source_path)

        if len(previews) == 1 and not normalized_paths:
            return previews

        if not normalized_paths:
            candidates = ', '.join(item['source_path'] or '.' for item in previews)
            raise ValueError(f'Multiple skills found. Please choose one or more source_paths: {candidates}')

        selected: list[dict] = []
        available = {preview['source_path']: preview for preview in previews}
        for normalized_path in normalized_paths:
            preview = available.get(normalized_path)
            if preview is None:
                candidates = ', '.join(item['source_path'] or '.' for item in previews)
                raise ValueError(f'Invalid source_path "{normalized_path}". Available: {candidates}')
            selected.append(preview)

        return selected

    def _install_preview_candidates(self, root_path: str, selected_previews: list[dict]) -> list[dict]:
        target_dirs: list[str] = []
        for preview in selected_previews:
            target_dir = self._normalize_package_root(preview['package_root'])
            if target_dir in target_dirs:
                raise ValueError(f'Duplicate target directory selected: {target_dir}')
            if os.path.exists(target_dir):
                raise ValueError(f'Skill directory already exists: {target_dir}')
            target_dirs.append(target_dir)

        installed_scans: list[dict] = []
        created_dirs: list[str] = []
        try:
            for preview in selected_previews:
                target_dir = self._normalize_package_root(preview['package_root'])
                source_root = self._preview_source_root(root_path, preview['source_path'])
                os.makedirs(os.path.dirname(target_dir), exist_ok=True)
                shutil.copytree(source_root, target_dir)
                created_dirs.append(target_dir)
                installed_scans.append(self.scan_directory(target_dir))
        except Exception:
            for target_dir in created_dirs:
                shutil.rmtree(target_dir, ignore_errors=True)
            raise

        return installed_scans

    async def _resolve_installed_skills(self, scanned_skills: list[dict]) -> list[dict]:
        installed_skills: list[dict] = []
        for scanned in scanned_skills:
            installed = await self.get_skill(scanned['name'])
            if not installed:
                installed = self._serialize_skill(scanned)
            installed_skills.append(installed)
        return installed_skills

    @staticmethod
    def _preview_source_root(root_path: str, source_path: str) -> str:
        normalized = str(source_path or '').strip().replace('\\', '/').strip('/')
        if not normalized:
            return root_path
        return os.path.join(root_path, normalized)

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
    def _safe_extract_zip(archive: zipfile.ZipFile, target_dir: str) -> None:
        target_root = os.path.realpath(target_dir)
        os.makedirs(target_root, exist_ok=True)

        for member in archive.infolist():
            member_name = member.filename
            if not member_name or member_name.endswith('/'):
                continue

            normalized = posixpath.normpath(member_name)
            if normalized.startswith('../') or normalized == '..' or os.path.isabs(normalized):
                raise ValueError(f'Archive contains an unsafe path: {member_name}')

            destination = os.path.realpath(os.path.join(target_root, normalized))
            if destination != target_root and not destination.startswith(f'{target_root}{os.sep}'):
                raise ValueError(f'Archive contains an unsafe path: {member_name}')

        archive.extractall(target_root)

    @staticmethod
    def _resolve_create_field(data: dict, field: str, imported_skill_data: dict | None, *, default: str) -> str:
        raw_value = data.get(field) if field in data else None
        if raw_value is None:
            if imported_skill_data is not None:
                return str(imported_skill_data.get(field, default) or default)
            return default

        value = str(raw_value or '')
        if imported_skill_data is not None and not value.strip():
            return str(imported_skill_data.get(field, default) or default)
        return value

    @staticmethod
    def _resolve_create_bool(data: dict, field: str, imported_skill_data: dict | None, *, default: bool) -> bool:
        if field in data and data[field] is not None:
            return bool(data[field])
        if imported_skill_data is not None:
            return bool(imported_skill_data.get(field, default))
        return default

    def _write_skill_md(self, package_root: str, metadata: dict, instructions: str) -> None:
        package_root = self._normalize_package_root(package_root)
        os.makedirs(package_root, exist_ok=True)
        content = _build_skill_md(metadata, instructions)
        with open(os.path.join(package_root, 'SKILL.md'), 'w', encoding='utf-8') as f:
            f.write(content)

    def _managed_skill_path(self, skill_name: str) -> str:
        return self._normalize_package_root(paths.get_data_path('skills', skill_name))

    def _managed_install_root_for_package(self, package_root: str) -> str:
        managed_root = self._normalize_package_root(paths.get_data_path('skills'))
        if not package_root or package_root == managed_root:
            return ''

        prefix = f'{managed_root}{os.sep}'
        if not package_root.startswith(prefix):
            return ''

        relative = os.path.relpath(package_root, managed_root)
        top_level = relative.split(os.sep, 1)[0]
        if top_level in ('', '.', '..'):
            return ''
        return os.path.join(managed_root, top_level)

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

    @staticmethod
    def _normalize_package_root(package_root: str) -> str:
        package_root = str(package_root).strip()
        if not package_root:
            return ''
        return os.path.realpath(os.path.abspath(package_root))

    @staticmethod
    def _find_skill_entry(path: str) -> Optional[tuple[str, str]]:
        for candidate in ('SKILL.md', 'skill.md'):
            if os.path.isfile(os.path.join(path, candidate)):
                return path, candidate
        return None

    def _discover_skill_directories(self, root_path: str, max_depth: int = 2) -> list[tuple[str, str]]:
        discovered: list[tuple[str, str]] = []
        queue: list[tuple[str, int]] = [(root_path, 0)]
        seen: set[str] = set()

        while queue:
            current_path, depth = queue.pop(0)
            normalized_path = os.path.abspath(current_path)
            if normalized_path in seen:
                continue
            seen.add(normalized_path)

            found = self._find_skill_entry(normalized_path)
            if found:
                discovered.append(found)
                continue

            if depth >= max_depth:
                continue

            try:
                entries = sorted(os.scandir(normalized_path), key=lambda entry: entry.name)
            except OSError:
                continue

            for entry in entries:
                if entry.is_dir():
                    queue.append((entry.path, depth + 1))

        return discovered

    def _resolve_skill_path(self, skill: dict, path: str, *, expect_directory: bool) -> tuple[str, str]:
        package_root = self._normalize_package_root(skill.get('package_root', ''))
        if not package_root:
            raise ValueError(f'Skill "{skill.get("name", "")}" has no package_root')

        relative_path = str(path or '.').strip() or '.'
        if os.path.isabs(relative_path):
            raise ValueError('path must be relative to the skill package root')

        normalized_relative = os.path.normpath(relative_path)
        if normalized_relative.startswith('..') or normalized_relative == '..':
            raise ValueError('path must stay within the skill package root')

        target_path = os.path.realpath(os.path.join(package_root, normalized_relative))
        if target_path != package_root and not target_path.startswith(f'{package_root}{os.sep}'):
            raise ValueError('path must stay within the skill package root')

        if expect_directory:
            if not os.path.isdir(target_path):
                raise ValueError(f'Skill directory not found: {relative_path}')
        else:
            parent_dir = os.path.dirname(target_path) or package_root
            if parent_dir != package_root and not parent_dir.startswith(f'{package_root}{os.sep}'):
                raise ValueError('path must stay within the skill package root')

        return target_path, normalized_relative
