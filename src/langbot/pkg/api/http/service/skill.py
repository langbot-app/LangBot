from __future__ import annotations

import os
import shutil
import tempfile
import zipfile

import httpx
import yaml

from ....core import app
from ....skill.utils import parse_frontmatter

_FRONTMATTER_FIELDS = (
    'name',
    'display_name',
    'description',
    'auto_activate',
)


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

    async def list_skills(self) -> list[dict]:
        skills = [dict(skill) for skill in getattr(self.ap.skill_mgr, 'skills', {}).values()]
        skills.sort(key=lambda item: item.get('updated_at', ''), reverse=True)
        return skills

    async def get_skill(self, skill_name: str) -> Optional[dict]:
        skill = getattr(self.ap.skill_mgr, 'get_skill_by_name', lambda _name: None)(skill_name)
        return dict(skill) if skill else None

    async def get_skill_by_name(self, name: str) -> Optional[dict]:
        return await self.get_skill(name)

    async def create_skill(self, data: dict) -> dict:
        name = self._validate_skill_name(data.get('name', ''))
        if await self.get_skill_by_name(name):
            raise ValueError(f'Skill with name "{name}" already exists')

        package_root = self._normalize_package_root(data.get('package_root', ''))
        managed_root = self._managed_skill_path(name)
        instructions = str(data.get('instructions', '') or '')

        if package_root and package_root != managed_root:
            if not os.path.isdir(package_root):
                raise ValueError(f'Directory does not exist: {package_root}')
            if os.path.exists(managed_root):
                raise ValueError(f'Skill directory already exists: {managed_root}')
            os.makedirs(os.path.dirname(managed_root), exist_ok=True)
            shutil.copytree(package_root, managed_root)
        else:
            os.makedirs(managed_root, exist_ok=True)

        metadata = {
            'name': name,
            'display_name': str(data.get('display_name', '') or ''),
            'description': str(data.get('description', '') or ''),
            'auto_activate': bool(data.get('auto_activate', True)),
        }
        self._write_skill_md(managed_root, metadata, instructions)

        await self.ap.skill_mgr.reload_skills()
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

        metadata = {
            'name': skill['name'],
            'display_name': data.get('display_name', skill.get('display_name', '')),
            'description': data.get('description', skill.get('description', '')),
            'auto_activate': data.get('auto_activate', skill.get('auto_activate', True)),
        }
        instructions = str(data.get('instructions', skill.get('instructions', '')) or '')
        self._write_skill_md(skill['package_root'], metadata, instructions)

        await self.ap.skill_mgr.reload_skills()
        updated = await self.get_skill(skill_name)
        if not updated:
            raise ValueError(f'Skill "{skill_name}" not found after update')
        return updated

    async def delete_skill(self, skill_name: str) -> bool:
        skill = await self.get_skill(skill_name)
        if not skill:
            raise ValueError(f'Skill "{skill_name}" not found')

        managed_path = self._managed_skill_path(skill_name)
        package_root = self._normalize_package_root(skill['package_root'])
        if package_root != managed_path:
            raise ValueError('Only managed skills under data/skills can be deleted via LangBot')

        shutil.rmtree(managed_path, ignore_errors=True)
        await self.ap.skill_mgr.reload_skills()
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

    async def install_from_github(self, data: dict) -> dict:
        asset_url = data['asset_url']
        repo = data['repo']
        release_tag = data.get('release_tag', '')

        target_dir = os.path.join('data', 'skills', repo)
        if os.path.exists(target_dir):
            tag_suffix = release_tag.lstrip('v').replace('/', '-') or 'source'
            target_dir = os.path.join('data', 'skills', f'{repo}-{tag_suffix}')
            if os.path.exists(target_dir):
                raise ValueError(f'Skill directory already exists: {target_dir}')

        tmp_dir = tempfile.mkdtemp(prefix='langbot_skill_')
        try:
            zip_path = os.path.join(tmp_dir, 'skill.zip')
            async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
                resp = await client.get(asset_url)
                resp.raise_for_status()
                with open(zip_path, 'wb') as f:
                    f.write(resp.content)

            extract_dir = os.path.join(tmp_dir, 'extracted')
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extract_dir)

            entries = os.listdir(extract_dir)
            if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
                skill_root = os.path.join(extract_dir, entries[0])
            else:
                skill_root = extract_dir

            os.makedirs(os.path.dirname(target_dir), exist_ok=True)
            shutil.move(skill_root, target_dir)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        try:
            scanned = self.scan_directory(target_dir)
        except ValueError:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise

        await self.ap.skill_mgr.reload_skills()
        installed = await self.get_skill(scanned['name'])
        if not installed:
            raise ValueError(f'Installed skill "{scanned["name"]}" could not be loaded')
        return installed

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

    def _write_skill_md(self, package_root: str, metadata: dict, instructions: str) -> None:
        package_root = self._normalize_package_root(package_root)
        os.makedirs(package_root, exist_ok=True)
        content = _build_skill_md(metadata, instructions)
        with open(os.path.join(package_root, 'SKILL.md'), 'w', encoding='utf-8') as f:
            f.write(content)

    def _managed_skill_path(self, skill_name: str) -> str:
        return self._normalize_package_root(os.path.join('data', 'skills', skill_name))

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
