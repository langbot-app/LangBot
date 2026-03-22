from __future__ import annotations

import os
import re
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


class SkillService:
    """Skill management service"""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def list_skills(
        self,
        skill_type: Optional[str] = None,
        is_enabled: Optional[bool] = None,
        tags: Optional[list[str]] = None,
    ) -> list[dict]:
        """List all skills with optional filters.

        Args:
            skill_type: Filter by skill type ('skill' or 'workflow')
            is_enabled: Filter by enabled status
            tags: Filter by tags (skills containing any of the specified tags)

        Returns:
            List of skill dictionaries
        """
        query = sqlalchemy.select(persistence_skill.Skill)

        if skill_type:
            query = query.where(persistence_skill.Skill.type == skill_type)
        if is_enabled is not None:
            query = query.where(persistence_skill.Skill.is_enabled == is_enabled)

        query = query.order_by(persistence_skill.Skill.created_at.desc())

        result = await self.ap.persistence_mgr.execute_async(query)
        skills = result.all()

        skill_list = [self.ap.persistence_mgr.serialize_model(persistence_skill.Skill, s) for s in skills]

        # Load instructions from SKILL.md for each skill
        for s in skill_list:
            self._load_instructions_from_file(s)

        # Filter by tags if specified (post-query filtering for JSON field)
        if tags:
            skill_list = [s for s in skill_list if any(tag in s.get('tags', []) for tag in tags)]

        return skill_list

    async def get_skill(self, skill_uuid: str) -> Optional[dict]:
        """Get a single skill by UUID.

        Args:
            skill_uuid: Skill UUID

        Returns:
            Skill dictionary or None if not found
        """
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_skill.Skill).where(persistence_skill.Skill.uuid == skill_uuid)
        )
        skill = result.first()
        if not skill:
            return None
        skill_data = self.ap.persistence_mgr.serialize_model(persistence_skill.Skill, skill)
        # Load instructions from SKILL.md for API consumers
        self._load_instructions_from_file(skill_data)
        return skill_data

    async def get_skill_by_name(self, name: str) -> Optional[dict]:
        """Get a single skill by name.

        Args:
            name: Skill name

        Returns:
            Skill dictionary or None if not found
        """
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_skill.Skill).where(persistence_skill.Skill.name == name)
        )
        skill = result.first()
        return self.ap.persistence_mgr.serialize_model(persistence_skill.Skill, skill) if skill else None

    async def create_skill(self, data: dict) -> dict:
        """Create a new skill.

        Args:
            data: Skill data containing:
                - name: Skill name (required, unique)
                - description: Skill description (required)
                - instructions: Markdown instructions (written to SKILL.md, not stored in DB)
                - type: 'skill' or 'workflow' (default: 'skill')
                - package_root: Package root directory (auto-created under data/skills/{name}/ if not provided)
                - entry_file: Package entry file name (default: 'SKILL.md')
                - skill_tools: List of skill tool definitions
                - requires_tools: List of required tool names
                - requires_kbs: List of required knowledge base UUIDs
                - requires_skills: List of required sub-skill names
                - auto_activate: Whether to auto-activate (default: True)
                - trigger_keywords: List of trigger keywords
                - tags: List of tags
                - author: Author name

        Returns:
            Created skill dictionary

        Raises:
            ValueError: If validation fails
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

        # Ensure the directory exists
        os.makedirs(package_root, exist_ok=True)

        # Write instructions to entry file
        if instructions:
            entry_path = os.path.join(package_root, entry_file)
            with open(entry_path, 'w', encoding='utf-8') as f:
                f.write(instructions)

        self._validate_package_fields(package_root, entry_file, data)

        skill_uuid = str(uuid_lib.uuid4())

        skill_data = {
            'uuid': skill_uuid,
            'name': data['name'],
            'description': data['description'],
            'type': data.get('type', 'skill'),
            'package_root': package_root,
            'entry_file': entry_file,
            'skill_tools': data.get('skill_tools', []),
            'requires_tools': data.get('requires_tools', []),
            'requires_kbs': data.get('requires_kbs', []),
            'requires_skills': data.get('requires_skills', []),
            'auto_activate': data.get('auto_activate', True),
            'trigger_keywords': data.get('trigger_keywords', []),
            'is_enabled': data.get('is_enabled', True),
            'is_builtin': data.get('is_builtin', False),
            'author': data.get('author'),
            'version': data.get('version', '1.0.0'),
            'tags': data.get('tags', []),
        }

        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_skill.Skill).values(**skill_data))

        # Reload skills in manager
        await self.ap.skill_mgr.reload_skills()

        return await self.get_skill(skill_uuid)

    async def update_skill(self, skill_uuid: str, data: dict) -> dict:
        """Update an existing skill.

        Args:
            skill_uuid: Skill UUID
            data: Fields to update

        Returns:
            Updated skill dictionary

        Raises:
            ValueError: If skill not found or trying to update builtin skill's protected fields
        """
        skill = await self.get_skill(skill_uuid)
        if not skill:
            raise ValueError(f'Skill {skill_uuid} not found')

        # Prevent certain updates on builtin skills
        if skill.get('is_builtin'):
            protected_fields = ['name', 'is_builtin']
            for field in protected_fields:
                if field in data:
                    del data[field]

        # Remove read-only fields
        read_only_fields = ['uuid', 'created_at', 'updated_at']
        for field in read_only_fields:
            if field in data:
                del data[field]

        # Check for name conflict if name is being updated
        if 'name' in data and data['name'] != skill['name']:
            existing = await self.get_skill_by_name(data['name'])
            if existing:
                raise ValueError(f"Skill with name '{data['name']}' already exists")

        # If instructions content is provided, write it to SKILL.md
        instructions = data.pop('instructions', None)
        if instructions is not None:
            package_root = data.get('package_root', skill.get('package_root', ''))
            entry_file = data.get('entry_file', skill.get('entry_file', 'SKILL.md'))
            if package_root:
                os.makedirs(package_root, exist_ok=True)
                entry_path = os.path.join(package_root, entry_file)
                with open(entry_path, 'w', encoding='utf-8') as f:
                    f.write(instructions)

        if data:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_skill.Skill)
                .where(persistence_skill.Skill.uuid == skill_uuid)
                .values(**data)
            )

            # Reload skills in manager
            await self.ap.skill_mgr.reload_skills()

        return await self.get_skill(skill_uuid)

    async def delete_skill(self, skill_uuid: str) -> bool:
        """Delete a skill.

        Args:
            skill_uuid: Skill UUID

        Returns:
            True if deleted successfully

        Raises:
            ValueError: If skill not found or is a builtin skill
        """
        skill = await self.get_skill(skill_uuid)
        if not skill:
            raise ValueError(f'Skill {skill_uuid} not found')

        if skill.get('is_builtin'):
            raise ValueError('Cannot delete builtin skill')

        # Delete bindings first
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_skill.SkillPipelineBinding).where(
                persistence_skill.SkillPipelineBinding.skill_uuid == skill_uuid
            )
        )

        # Delete skill
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_skill.Skill).where(persistence_skill.Skill.uuid == skill_uuid)
        )

        # Reload skills in manager
        await self.ap.skill_mgr.reload_skills()

        return True

    async def toggle_skill(self, skill_uuid: str, is_enabled: bool) -> dict:
        """Enable or disable a skill.

        Args:
            skill_uuid: Skill UUID
            is_enabled: New enabled status

        Returns:
            Updated skill dictionary
        """
        return await self.update_skill(skill_uuid, {'is_enabled': is_enabled})

    # ========== Pipeline Binding Methods ==========

    async def bind_skill_to_pipeline(self, skill_uuid: str, pipeline_uuid: str, priority: int = 0) -> dict:
        """Bind a skill to a pipeline.

        Args:
            skill_uuid: Skill UUID
            pipeline_uuid: Pipeline UUID
            priority: Binding priority (higher = checked first)

        Returns:
            Binding information
        """
        # Check if binding already exists
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_skill.SkillPipelineBinding).where(
                sqlalchemy.and_(
                    persistence_skill.SkillPipelineBinding.skill_uuid == skill_uuid,
                    persistence_skill.SkillPipelineBinding.pipeline_uuid == pipeline_uuid,
                )
            )
        )
        existing = result.first()

        if existing:
            # Update priority if binding exists
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_skill.SkillPipelineBinding)
                .where(persistence_skill.SkillPipelineBinding.id == existing.id)
                .values(priority=priority, is_enabled=True)
            )
        else:
            # Create new binding
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.insert(persistence_skill.SkillPipelineBinding).values(
                    skill_uuid=skill_uuid,
                    pipeline_uuid=pipeline_uuid,
                    priority=priority,
                    is_enabled=True,
                )
            )

        return {'skill_uuid': skill_uuid, 'pipeline_uuid': pipeline_uuid, 'priority': priority}

    async def unbind_skill_from_pipeline(self, skill_uuid: str, pipeline_uuid: str) -> bool:
        """Remove skill binding from pipeline.

        Args:
            skill_uuid: Skill UUID
            pipeline_uuid: Pipeline UUID

        Returns:
            True if unbinding was successful
        """
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_skill.SkillPipelineBinding).where(
                sqlalchemy.and_(
                    persistence_skill.SkillPipelineBinding.skill_uuid == skill_uuid,
                    persistence_skill.SkillPipelineBinding.pipeline_uuid == pipeline_uuid,
                )
            )
        )
        return True

    async def get_pipeline_skills(self, pipeline_uuid: str) -> list[dict]:
        """Get all skills bound to a pipeline.

        Args:
            pipeline_uuid: Pipeline UUID

        Returns:
            List of skill dictionaries with binding info
        """
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_skill.Skill, persistence_skill.SkillPipelineBinding.priority)
            .join(
                persistence_skill.SkillPipelineBinding,
                persistence_skill.Skill.uuid == persistence_skill.SkillPipelineBinding.skill_uuid,
            )
            .where(persistence_skill.SkillPipelineBinding.pipeline_uuid == pipeline_uuid)
            .where(persistence_skill.SkillPipelineBinding.is_enabled == True)
            .order_by(persistence_skill.SkillPipelineBinding.priority.desc())
        )

        skills = []
        for row in result.all():
            skill_data = self.ap.persistence_mgr.serialize_model(persistence_skill.Skill, row[0])
            skill_data['binding_priority'] = row[1]
            skills.append(skill_data)

        return skills

    async def update_pipeline_skill_bindings(self, pipeline_uuid: str, skill_bindings: list[dict]) -> list[dict]:
        """Update all skill bindings for a pipeline.

        Args:
            pipeline_uuid: Pipeline UUID
            skill_bindings: List of {'skill_uuid': str, 'priority': int}

        Returns:
            Updated list of bound skills
        """
        # Remove all existing bindings
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_skill.SkillPipelineBinding).where(
                persistence_skill.SkillPipelineBinding.pipeline_uuid == pipeline_uuid
            )
        )

        # Create new bindings
        for binding in skill_bindings:
            await self.bind_skill_to_pipeline(
                skill_uuid=binding['skill_uuid'],
                pipeline_uuid=pipeline_uuid,
                priority=binding.get('priority', 0),
            )

        return await self.get_pipeline_skills(pipeline_uuid)

    # ========== Install from GitHub ==========

    async def install_from_github(self, data: dict) -> dict:
        """Install a skill from a GitHub release asset (zip).

        Downloads the zip, extracts to data/skills/{repo}/, scans SKILL.md,
        and creates the skill in the database.

        Args:
            data: Dictionary with asset_url, owner, repo, release_tag

        Returns:
            Created skill dictionary

        Raises:
            ValueError: If download/extraction/scan fails
        """
        asset_url = data['asset_url']
        repo = data['repo']
        release_tag = data.get('release_tag', '')

        # Determine target directory
        target_dir = os.path.join('data', 'skills', repo)
        if os.path.exists(target_dir):
            # Handle name conflicts by appending release tag
            tag_suffix = release_tag.lstrip('v').replace('/', '-')
            target_dir = os.path.join('data', 'skills', f'{repo}-{tag_suffix}')
            if os.path.exists(target_dir):
                raise ValueError(f'Skill directory already exists: {target_dir}')

        tmp_dir = tempfile.mkdtemp(prefix='langbot_skill_')
        try:
            # Download the zip asset
            zip_path = os.path.join(tmp_dir, 'skill.zip')
            async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
                resp = await client.get(asset_url)
                resp.raise_for_status()
                with open(zip_path, 'wb') as f:
                    f.write(resp.content)

            # Extract zip
            extract_dir = os.path.join(tmp_dir, 'extracted')
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extract_dir)

            # Find the skill root – GitHub zips typically have a {repo}-{tag}/ wrapper
            entries = os.listdir(extract_dir)
            if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
                skill_root = os.path.join(extract_dir, entries[0])
            else:
                skill_root = extract_dir

            # Verify SKILL.md exists
            has_skill_md = False
            for candidate in ('SKILL.md', 'skill.md'):
                if os.path.isfile(os.path.join(skill_root, candidate)):
                    has_skill_md = True
                    break
            if not has_skill_md:
                raise ValueError('No SKILL.md found in the downloaded archive')

            # Move to target directory
            os.makedirs(os.path.dirname(target_dir), exist_ok=True)
            shutil.move(skill_root, target_dir)

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        # Scan the extracted directory for metadata
        try:
            scanned = self.scan_directory(target_dir)
        except ValueError:
            # Clean up if scan fails
            shutil.rmtree(target_dir, ignore_errors=True)
            raise

        # Create skill in DB using scanned metadata
        skill_data = {
            'name': scanned['name'],
            'description': scanned.get('description', ''),
            'package_root': scanned['package_root'],
            'entry_file': scanned['entry_file'],
            'author': scanned.get('author'),
            'version': scanned.get('version', '1.0.0'),
            'tags': scanned.get('tags', []),
        }

        try:
            return await self.create_skill(skill_data)
        except ValueError:
            # Clean up directory if DB creation fails (e.g. duplicate name)
            shutil.rmtree(target_dir, ignore_errors=True)
            raise

    # ========== Validation Helpers ==========

    def _load_instructions_from_file(self, skill_data: dict):
        """Load instructions content from SKILL.md into skill_data for API responses."""
        package_root = skill_data.get('package_root', '')
        entry_file = skill_data.get('entry_file', 'SKILL.md')
        if package_root:
            entry_path = os.path.join(package_root, entry_file)
            try:
                with open(entry_path, 'r', encoding='utf-8') as f:
                    skill_data['instructions'] = f.read()
            except (FileNotFoundError, OSError):
                skill_data['instructions'] = ''
        else:
            skill_data['instructions'] = ''

    def _validate_package_fields(self, package_root: str, entry_file: str, data: dict):
        """Validate package_root and entry_file fields."""
        if os.path.isabs(package_root):
            # Validate package_root is within allowed host mount roots
            if hasattr(self.ap, 'box_service') and self.ap.box_service is not None:
                real_root = os.path.realpath(os.path.abspath(package_root))
                allowed_roots = self.ap.box_service.allowed_host_mount_roots
                if allowed_roots:
                    is_allowed = any(
                        real_root == ar or real_root.startswith(f'{ar}{os.sep}')
                        for ar in allowed_roots
                    )
                    if not is_allowed:
                        raise ValueError(
                            f'package_root is outside allowed_host_mount_roots'
                        )

        if os.path.isabs(entry_file):
            raise ValueError('entry_file must not be an absolute path')
        if '..' in entry_file.split(os.sep):
            raise ValueError('entry_file must not contain path traversal')

        # Validate skill_tools entries
        for tool in data.get('skill_tools', []):
            self._validate_skill_tool_entry(tool)

    @staticmethod
    def _validate_skill_tool_entry(tool: dict):
        """Validate a single skill_tools entry."""
        if not tool.get('name'):
            raise ValueError('skill tool name is required')
        if not re.match(r'^[a-zA-Z0-9_-]+$', tool['name']):
            raise ValueError(f'skill tool name contains invalid characters: {tool["name"]}')

        entry = tool.get('entry', '')
        if not entry:
            raise ValueError(f'skill tool entry is required for tool "{tool["name"]}"')
        if os.path.isabs(entry):
            raise ValueError(f'skill tool entry must be a relative path: {entry}')
        if '..' in entry.split(os.sep):
            raise ValueError(f'skill tool entry must not contain path traversal: {entry}')

    # ========== Scan / Import ==========

    def scan_directory(self, path: str) -> dict:
        """Scan a directory for skill metadata.

        Reads SKILL.md (or other entry file) and parses YAML frontmatter
        to extract name, description, author, version, tags, etc.

        Args:
            path: Directory path to scan

        Returns:
            Dictionary with detected metadata and instructions

        Raises:
            ValueError: If path is invalid or no entry file found
        """
        if not os.path.isdir(path):
            raise ValueError(f'Directory does not exist: {path}')

        # Try common entry files
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

        # Parse YAML frontmatter
        metadata, instructions = self._parse_frontmatter(content)

        # Use directory name as fallback skill name
        dir_name = os.path.basename(os.path.normpath(path))

        result = {
            'package_root': os.path.abspath(path),
            'entry_file': entry_file,
            'name': metadata.get('name', dir_name),
            'description': metadata.get('description', ''),
            'author': metadata.get('author'),
            'version': metadata.get('version', '1.0.0'),
            'tags': metadata.get('tags', []),
            'instructions': instructions,
        }

        return result

    @staticmethod
    def _parse_frontmatter(content: str) -> tuple[dict, str]:
        """Parse YAML frontmatter from markdown content.

        Expects format:
            ---
            name: my-skill
            description: Does something
            ---
            # Actual instructions...

        Returns:
            Tuple of (metadata dict, remaining content)
        """
        if not content.startswith('---'):
            return {}, content

        parts = content.split('---', 2)
        if len(parts) < 3:
            return {}, content

        frontmatter_str = parts[1].strip()
        instructions = parts[2].strip()

        try:
            metadata = yaml.safe_load(frontmatter_str) or {}
        except yaml.YAMLError:
            metadata = {}

        if not isinstance(metadata, dict):
            metadata = {}

        return metadata, instructions
