from __future__ import annotations

import uuid as uuid_lib
from typing import Optional

import sqlalchemy

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
        return self.ap.persistence_mgr.serialize_model(persistence_skill.Skill, skill) if skill else None

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
                - instructions: Markdown instructions (required)
                - type: 'skill' or 'workflow' (default: 'skill')
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
            ValueError: If a skill with the same name already exists
        """
        # Check for duplicate name
        existing = await self.get_skill_by_name(data['name'])
        if existing:
            raise ValueError(f"Skill with name '{data['name']}' already exists")

        skill_uuid = str(uuid_lib.uuid4())

        skill_data = {
            'uuid': skill_uuid,
            'name': data['name'],
            'description': data['description'],
            'instructions': data['instructions'],
            'type': data.get('type', 'skill'),
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
