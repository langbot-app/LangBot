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
_DB_FIELDS = {'uuid', 'name', 'package_root', 'entry_file', 'sandbox_timeout_sec', 'sandbox_network', 'is_enabled', 'is_builtin'}

# Fields that live in SKILL.md frontmatter (package metadata)
_FRONTMATTER_FIELDS = {
    'display_name', 'description', 'type', 'author', 'version', 'tags',
    'auto_activate', 'trigger_keywords', 'requires_tools', 'requires_kbs', 'requires_skills',
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

        skill_uuid = str(uuid_lib.uuid4())

        # Only store registry fields in DB
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

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_skill.Skill).where(persistence_skill.Skill.uuid == skill_uuid)
        )

        await self.ap.skill_mgr.reload_skills()
        return True

    async def toggle_skill(self, skill_uuid: str, is_enabled: bool) -> dict:
        """Enable or disable a skill."""
        return await self.update_skill(skill_uuid, {'is_enabled': is_enabled})

    # ========== Install from GitHub ==========

    async def install_from_github(self, data: dict) -> dict:
        """Install a skill from a GitHub release asset (zip)."""
        asset_url = data['asset_url']
        repo = data['repo']
        release_tag = data.get('release_tag', '')

        target_dir = os.path.join('data', 'skills', repo)
        if os.path.exists(target_dir):
            tag_suffix = release_tag.lstrip('v').replace('/', '-')
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

            has_skill_md = False
            for candidate in ('SKILL.md', 'skill.md'):
                if os.path.isfile(os.path.join(skill_root, candidate)):
                    has_skill_md = True
                    break
            if not has_skill_md:
                raise ValueError('No SKILL.md found in the downloaded archive')

            os.makedirs(os.path.dirname(target_dir), exist_ok=True)
            shutil.move(skill_root, target_dir)

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        try:
            scanned = self.scan_directory(target_dir)
        except ValueError:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise

        # Only pass registry fields + name to create_skill
        skill_data = {
            'name': scanned['name'],
            'package_root': scanned['package_root'],
            'entry_file': scanned['entry_file'],
        }

        try:
            return await self.create_skill(skill_data)
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
                elif key in ('tags', 'requires_tools', 'requires_kbs', 'requires_skills', 'trigger_keywords'):
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
                is_allowed = any(
                    real_root == ar or real_root.startswith(f'{ar}{os.sep}')
                    for ar in allowed_roots
                )
                if not is_allowed:
                    raise ValueError('package_root is outside allowed_host_mount_roots')

        if os.path.isabs(entry_file):
            raise ValueError('entry_file must not be an absolute path')
        if '..' in entry_file.split(os.sep):
            raise ValueError('entry_file must not contain path traversal')

    def scan_directory(self, path: str) -> dict:
        """Scan a directory for skill metadata from SKILL.md frontmatter."""
        if not os.path.isdir(path):
            raise ValueError(f'Directory does not exist: {path}')

        entry_file = None
        for candidate in ('SKILL.md', 'skill.md', 'README.md'):
            if os.path.isfile(os.path.join(path, candidate)):
                entry_file = candidate
                break

        if not entry_file:
            raise ValueError(f'No SKILL.md found in {path}')

        entry_path = os.path.join(path, entry_file)
        with open(entry_path, 'r', encoding='utf-8') as f:
            content = f.read()

        metadata, instructions = parse_frontmatter(content)
        dir_name = os.path.basename(os.path.normpath(path))

        result = {
            'package_root': os.path.abspath(path),
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
