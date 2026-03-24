from __future__ import annotations

import os
import shutil
import tempfile
import uuid as uuid_lib
import zipfile
from typing import Optional

import httpx
import sqlalchemy
import yaml

from ....core import app
from ....entity.persistence import skill as persistence_skill
from ....skill.utils import parse_frontmatter


# Fields that live in DB (registry/governance)
_DB_FIELDS = {
    'uuid',
    'name',
    'package_root',
    'entry_file',
    'sandbox_timeout_sec',
    'sandbox_network',
    'is_enabled',
    'is_builtin',
}

# Fields that live in SKILL.md frontmatter (package metadata)
_FRONTMATTER_FIELDS = {
    'display_name',
    'description',
    'type',
    'author',
    'version',
    'tags',
    'auto_activate',
    'trigger_keywords',
}


def _build_skill_md(metadata: dict, instructions: str) -> str:
    """Build SKILL.md content from frontmatter metadata and instructions body."""
    fm = {}
    for key in _FRONTMATTER_FIELDS:
        val = metadata.get(key)
        if val is None:
            continue
        # Skip empty defaults, but always keep description and display_name
        if key in ('description', 'display_name'):
            fm[key] = val
        elif val == '' or val == [] or val is False:
            continue
        else:
            fm[key] = val

    if fm:
        frontmatter = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False).strip()
        return f'---\n{frontmatter}\n---\n\n{instructions}'
    else:
        return instructions


class SkillService:
    """Skill management service.

    DB is the registry (uuid, name, package_root, sandbox config, is_enabled).
    SKILL.md frontmatter is the canonical source for package metadata.
    """

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def list_skills(
        self,
        is_enabled: Optional[bool] = None,
    ) -> list[dict]:
        """List all skills, merging DB registry with file metadata."""
        query = sqlalchemy.select(persistence_skill.Skill)

        if is_enabled is not None:
            query = query.where(persistence_skill.Skill.is_enabled == is_enabled)

        query = query.order_by(persistence_skill.Skill.created_at.desc())

        result = await self.ap.persistence_mgr.execute_async(query)
        skills = result.all()

        skill_list = []
        for s in skills:
            skill_data = self.ap.persistence_mgr.serialize_model(persistence_skill.Skill, s)
            self._load_skill_from_file(skill_data)
            skill_list.append(skill_data)

        return skill_list

    async def get_skill(self, skill_uuid: str) -> Optional[dict]:
        """Get a single skill by UUID, merging DB + file metadata."""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_skill.Skill).where(persistence_skill.Skill.uuid == skill_uuid)
        )
        skill = result.first()
        if not skill:
            return None
        skill_data = self.ap.persistence_mgr.serialize_model(persistence_skill.Skill, skill)
        self._load_skill_from_file(skill_data)
        return skill_data

    async def get_skill_by_name(self, name: str) -> Optional[dict]:
        """Get a single skill by name."""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_skill.Skill).where(persistence_skill.Skill.name == name)
        )
        skill = result.first()
        return self.ap.persistence_mgr.serialize_model(persistence_skill.Skill, skill) if skill else None

    async def create_skill(self, data: dict) -> dict:
        """Create a new skill.

        Writes package metadata to SKILL.md frontmatter.
        Only stores registry fields in DB.
        """
        # Check for duplicate name
        existing = await self.get_skill_by_name(data['name'])
        if existing:
            raise ValueError(f"Skill with name '{data['name']}' already exists")

        package_root = data.get('package_root', '').strip()
        entry_file = data.get('entry_file', 'SKILL.md')
        instructions = data.get('instructions', '')

        # Auto-create package_root if not provided
        if not package_root:
            package_root = os.path.join('data', 'skills', data['name'])

        package_root = self._normalize_package_root(package_root)

        self._validate_package_fields(package_root, entry_file)

        # Ensure the directory exists
        os.makedirs(package_root, exist_ok=True)

        # Build and write SKILL.md with frontmatter
        content = _build_skill_md(data, instructions)
        entry_path = os.path.join(package_root, entry_file)
        with open(entry_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return await self._register_existing_skill(
            {
                'name': data['name'],
                'package_root': package_root,
                'entry_file': entry_file,
                'sandbox_timeout_sec': data.get('sandbox_timeout_sec', 120),
                'sandbox_network': data.get('sandbox_network', False),
                'is_enabled': data.get('is_enabled', True),
                'is_builtin': data.get('is_builtin', False),
            }
        )

    async def _register_existing_skill(self, data: dict) -> dict:
        """Register an existing on-disk skill package without rewriting files."""
        existing = await self.get_skill_by_name(data['name'])
        if existing:
            raise ValueError(f"Skill with name '{data['name']}' already exists")

        package_root = self._normalize_package_root(data.get('package_root', ''))
        entry_file = data.get('entry_file', 'SKILL.md')
        self._validate_package_fields(package_root, entry_file)

        entry_path = os.path.join(package_root, entry_file)
        if not os.path.isfile(entry_path):
            raise ValueError(f'Skill entry file not found: {entry_path}')

        skill_uuid = str(uuid_lib.uuid4())
        db_data = {
            'uuid': skill_uuid,
            'name': data['name'],
            'package_root': package_root,
            'entry_file': entry_file,
            'sandbox_timeout_sec': data.get('sandbox_timeout_sec', 120),
            'sandbox_network': data.get('sandbox_network', False),
            'is_enabled': data.get('is_enabled', True),
            'is_builtin': data.get('is_builtin', False),
        }

        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_skill.Skill).values(**db_data))
        await self.ap.skill_mgr.reload_skills()

        return await self.get_skill(skill_uuid)

    async def update_skill(self, skill_uuid: str, data: dict) -> dict:
        """Update an existing skill.

        Package metadata fields update the SKILL.md frontmatter.
        Registry fields update the DB.
        """
        skill = await self.get_skill(skill_uuid)
        if not skill:
            raise ValueError(f'Skill {skill_uuid} not found')

        if skill.get('is_builtin'):
            for field in ['name', 'is_builtin']:
                data.pop(field, None)

        for field in ['uuid', 'created_at', 'updated_at']:
            data.pop(field, None)

        # Check for name conflict
        if 'name' in data and data['name'] != skill['name']:
            existing = await self.get_skill_by_name(data['name'])
            if existing:
                raise ValueError(f"Skill with name '{data['name']}' already exists")

        # Separate DB fields from frontmatter fields
        db_updates = {}
        frontmatter_updates = {}
        instructions = data.pop('instructions', None)

        for key, val in data.items():
            if key in _DB_FIELDS:
                db_updates[key] = val
            elif key in _FRONTMATTER_FIELDS:
                frontmatter_updates[key] = val

        if 'package_root' in db_updates:
            db_updates['package_root'] = self._normalize_package_root(db_updates['package_root'])
            self._validate_package_fields(
                db_updates['package_root'],
                db_updates.get('entry_file', skill.get('entry_file', 'SKILL.md')),
            )

        # Update SKILL.md if any frontmatter fields or instructions changed
        if frontmatter_updates or instructions is not None:
            package_root = db_updates.get('package_root', skill.get('package_root', ''))
            entry_file = db_updates.get('entry_file', skill.get('entry_file', 'SKILL.md'))

            if package_root:
                # Read current file to get existing frontmatter
                entry_path = os.path.join(package_root, entry_file)
                current_metadata = {}
                current_instructions = ''
                try:
                    with open(entry_path, 'r', encoding='utf-8') as f:
                        current_metadata, current_instructions = parse_frontmatter(f.read())
                except (FileNotFoundError, OSError):
                    pass

                # Merge updates
                current_metadata.update(frontmatter_updates)
                if instructions is not None:
                    current_instructions = instructions

                # Write updated file
                os.makedirs(package_root, exist_ok=True)
                content = _build_skill_md(current_metadata, current_instructions)
                with open(entry_path, 'w', encoding='utf-8') as f:
                    f.write(content)

        # Update DB if any registry fields changed
        if db_updates:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_skill.Skill)
                .where(persistence_skill.Skill.uuid == skill_uuid)
                .values(**db_updates)
            )

        await self.ap.skill_mgr.reload_skills()
        return await self.get_skill(skill_uuid)

    async def delete_skill(self, skill_uuid: str) -> bool:
        """Delete a skill."""
        skill = await self.get_skill(skill_uuid)
        if not skill:
            raise ValueError(f'Skill {skill_uuid} not found')

        if skill.get('is_builtin'):
            raise ValueError('Cannot delete builtin skill')

        managed_storage_path = self._get_managed_skill_storage_path(skill.get('package_root', ''))
        if managed_storage_path and os.path.isdir(managed_storage_path):
            shutil.rmtree(managed_storage_path)

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_skill.Skill).where(persistence_skill.Skill.uuid == skill_uuid)
        )

        await self.ap.skill_mgr.reload_skills()
        return True

    async def toggle_skill(self, skill_uuid: str, is_enabled: bool) -> dict:
        """Enable or disable a skill."""
        return await self.update_skill(skill_uuid, {'is_enabled': is_enabled})

    async def list_skill_files(
        self,
        skill_uuid: str,
        path: str = '.',
        include_hidden: bool = False,
        max_entries: int = 200,
    ) -> dict:
        """List files under a registered skill package."""
        skill = await self.get_skill(skill_uuid)
        if not skill:
            raise ValueError(f'Skill {skill_uuid} not found')

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
            'skill': {'uuid': skill['uuid'], 'name': skill['name']},
            'base_path': '.' if relative_path in ('', '.') else relative_path.replace(os.sep, '/'),
            'entries': entries,
            'truncated': len(entries) >= max_entries,
        }

    async def read_skill_file(self, skill_uuid: str, path: str) -> dict:
        """Read a UTF-8 text file under a registered skill package."""
        skill = await self.get_skill(skill_uuid)
        if not skill:
            raise ValueError(f'Skill {skill_uuid} not found')

        target_path, relative_path = self._resolve_skill_path(skill, path, expect_directory=False)
        if not os.path.isfile(target_path):
            raise ValueError(f'Skill file not found: {relative_path}')

        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError as exc:
            raise ValueError(f'Skill file is not valid UTF-8 text: {relative_path}') from exc

        return {
            'skill': {'uuid': skill['uuid'], 'name': skill['name']},
            'path': relative_path.replace(os.sep, '/'),
            'content': content,
        }

    async def write_skill_file(self, skill_uuid: str, path: str, content: str) -> dict:
        """Write a UTF-8 text file under a registered skill package."""
        skill = await self.get_skill(skill_uuid)
        if not skill:
            raise ValueError(f'Skill {skill_uuid} not found')

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
            'skill': {'uuid': skill['uuid'], 'name': skill['name']},
            'path': relative_path.replace(os.sep, '/'),
            'bytes_written': len(content.encode('utf-8')),
        }

    # ========== Install from GitHub ==========

    async def install_from_github(self, data: dict) -> dict:
        """Install a skill from a GitHub release asset (zip)."""
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

        skill_data = {
            'name': scanned['name'],
            'package_root': scanned['package_root'],
            'entry_file': scanned['entry_file'],
        }

        try:
            return await self._register_existing_skill(skill_data)
        except ValueError:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise

    # ========== Helpers ==========

    def _load_skill_from_file(self, skill_data: dict):
        """Load SKILL.md and merge frontmatter metadata into skill_data for API responses."""
        package_root = skill_data.get('package_root', '')
        entry_file = skill_data.get('entry_file', 'SKILL.md')
        if not package_root:
            skill_data['instructions'] = ''
            return

        entry_path = os.path.join(package_root, entry_file)
        try:
            with open(entry_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (FileNotFoundError, OSError):
            skill_data['instructions'] = ''
            return

        metadata, instructions = parse_frontmatter(content)
        skill_data['instructions'] = instructions
        skill_data['raw_content'] = content

        # Merge frontmatter metadata
        for key in _FRONTMATTER_FIELDS:
            if key in metadata:
                skill_data[key] = metadata[key]
            elif key not in skill_data:
                # Set defaults for missing fields
                if key in ('display_name', 'description', 'author', 'type'):
                    skill_data[key] = '' if key != 'type' else 'skill'
                elif key in ('tags', 'trigger_keywords'):
                    skill_data[key] = []
                elif key == 'auto_activate':
                    skill_data[key] = True
                elif key == 'version':
                    skill_data[key] = '1.0.0'

    def _validate_package_fields(self, package_root: str, entry_file: str):
        """Validate package_root and entry_file fields."""
        real_root = self._normalize_package_root(package_root)
        if real_root and hasattr(self.ap, 'box_service') and self.ap.box_service is not None:
            allowed_roots = self.ap.box_service.allowed_host_mount_roots
            if allowed_roots:
                is_allowed = any(real_root == ar or real_root.startswith(f'{ar}{os.sep}') for ar in allowed_roots)
                if not is_allowed:
                    raise ValueError('package_root is outside allowed_host_mount_roots')

        if os.path.isabs(entry_file):
            raise ValueError('entry_file must not be an absolute path')
        if '..' in entry_file.split(os.sep):
            raise ValueError('entry_file must not contain path traversal')

    def _find_skill_entry(self, path: str) -> Optional[tuple[str, str]]:
        for candidate in ('SKILL.md', 'skill.md', 'README.md'):
            if os.path.isfile(os.path.join(path, candidate)):
                return path, candidate
        return None

    def _discover_skill_directories(self, root_path: str, max_depth: int = 2) -> list[tuple[str, str]]:
        """Find skill entry files in root_path and its child directories up to max_depth."""
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

    def scan_directory(self, path: str) -> dict:
        """Scan a directory for skill metadata from SKILL.md frontmatter."""
        if not os.path.isdir(path):
            raise ValueError(f'Directory does not exist: {path}')

        discovered = self._discover_skill_directories(path, max_depth=2)
        if not discovered:
            raise ValueError(f'No SKILL.md found in {path} or its subdirectories (max depth: 2)')
        if len(discovered) > 1:
            candidates = ', '.join(found_path for found_path, _ in discovered)
            raise ValueError(
                f'Multiple skill directories found in {path}. Please choose a more specific path: {candidates}'
            )

        package_root, entry_file = discovered[0]

        entry_path = os.path.join(package_root, entry_file)
        with open(entry_path, 'r', encoding='utf-8') as f:
            content = f.read()

        metadata, instructions = parse_frontmatter(content)
        dir_name = os.path.basename(os.path.normpath(package_root))

        result = {
            'package_root': os.path.abspath(package_root),
            'entry_file': entry_file,
            'name': metadata.get('name', dir_name),
            'instructions': instructions,
            # Include all frontmatter metadata
            **{k: metadata.get(k, '') for k in _FRONTMATTER_FIELDS if k in metadata},
        }

        return result

    def _normalize_package_root(self, package_root: str) -> str:
        package_root = str(package_root).strip()
        if not package_root:
            return ''
        return os.path.realpath(os.path.abspath(package_root))

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

    def _get_managed_skill_storage_path(self, package_root: str) -> str:
        normalized_root = self._normalize_package_root(package_root)
        if not normalized_root:
            return ''

        managed_root = self._normalize_package_root(os.path.join('data', 'skills'))
        if normalized_root != managed_root and not normalized_root.startswith(f'{managed_root}{os.sep}'):
            return ''

        relative_path = os.path.relpath(normalized_root, managed_root)
        if relative_path in ('.', ''):
            return ''

        managed_entry = relative_path.split(os.sep, 1)[0]
        if managed_entry in ('', '.', '..'):
            return ''

        return os.path.join(managed_root, managed_entry)
