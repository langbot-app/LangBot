from __future__ import annotations

import re
import typing

import sqlalchemy

from ..core import app
from ..entity.persistence import skill as persistence_skill

if typing.TYPE_CHECKING:
    import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


class SkillManager:
    """Skill manager for loading, matching and resolving skills.

    Responsibilities:
    - Load skills from database
    - Build skill index for LLM matching
    - Detect skill activation from LLM responses
    - Resolve skill instructions with sub-skill support
    """

    INVOKE_SKILL_PATTERN = r'\{\{INVOKE_SKILL:\s*(\S+)\s*\}\}'
    SKILL_ACTIVATION_MARKER = '[ACTIVATE_SKILL:'

    ap: app.Application

    skills: dict[str, dict]
    """Skills indexed by name"""

    skills_by_uuid: dict[str, dict]
    """Skills indexed by UUID"""

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.skills = {}
        self.skills_by_uuid = {}

    async def initialize(self):
        """Initialize skill manager and load skills from database"""
        await self.reload_skills()

    async def reload_skills(self):
        """Reload all skills from database"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_skill.Skill).where(persistence_skill.Skill.is_enabled == True)
        )
        skills_list = result.all()

        self.skills = {}
        self.skills_by_uuid = {}

        for skill in skills_list:
            skill_data = self.ap.persistence_mgr.serialize_model(persistence_skill.Skill, skill)
            self.skills[skill_data['name']] = skill_data
            self.skills_by_uuid[skill_data['uuid']] = skill_data

        self.ap.logger.info(f'Loaded {len(self.skills)} skills')

    def get_skill_by_name(self, name: str) -> dict | None:
        """Get skill by name"""
        return self.skills.get(name)

    def get_skill_by_uuid(self, uuid: str) -> dict | None:
        """Get skill by UUID"""
        return self.skills_by_uuid.get(uuid)

    def get_skill_index(self, pipeline_uuid: str | None = None, bound_skills: list[str] | None = None) -> str:
        """Generate skill index for LLM system prompt.

        Args:
            pipeline_uuid: Optional pipeline UUID to filter bound skills
            bound_skills: Optional list of skill UUIDs to include

        Returns:
            Formatted skill index string
        """
        skills_to_index = []

        for skill in self.skills.values():
            # Only include auto-activatable skills
            if not skill.get('auto_activate', True):
                continue

            # Filter by bound skills if specified
            if bound_skills is not None and skill['uuid'] not in bound_skills:
                continue

            skills_to_index.append(skill)

        if not skills_to_index:
            return ''

        lines = ['Available Skills:']
        for skill in skills_to_index:
            skill_type_tag = '[workflow]' if skill['type'] == 'workflow' else ''
            lines.append(f"- {skill['name']}{skill_type_tag}: {skill['description']}")

        return '\n'.join(lines)

    def build_skill_aware_prompt_addition(self, pipeline_uuid: str | None = None, bound_skills: list[str] | None = None) -> str:
        """Build the skill awareness instruction to add to system prompt.

        Args:
            pipeline_uuid: Optional pipeline UUID
            bound_skills: Optional list of skill UUIDs

        Returns:
            Skill awareness instruction string
        """
        skill_index = self.get_skill_index(pipeline_uuid, bound_skills)

        if not skill_index:
            return ''

        return f"""

{skill_index}

When the user's request clearly matches a skill's purpose based on its description, you should activate that skill.
To activate a skill, include this marker at the beginning of your response: [ACTIVATE_SKILL: skill-name]
After activation, the skill's detailed instructions will be loaded for you to follow.
Only activate ONE skill at a time. If no skill matches, respond normally without activation.
"""

    def detect_skill_activation(self, response: str) -> str | None:
        """Detect skill activation request from LLM response.

        Args:
            response: LLM response text

        Returns:
            Skill name if activation detected, None otherwise
        """
        if self.SKILL_ACTIVATION_MARKER not in response:
            return None

        # Extract skill name using regex
        match = re.search(r'\[ACTIVATE_SKILL:\s*(\S+?)\s*\]', response)
        if match:
            skill_name = match.group(1)
            # Validate skill exists
            if skill_name in self.skills:
                return skill_name

        return None

    def resolve_skill_instructions(self, skill_name: str, depth: int = 0) -> str:
        """Resolve skill instructions with sub-skill expansion.

        Args:
            skill_name: Name of the skill to resolve
            depth: Current recursion depth (to prevent infinite loops)

        Returns:
            Resolved instructions with sub-skills expanded
        """
        if depth > 5:
            return f'[ERROR: Maximum skill nesting depth exceeded for {skill_name}]'

        skill = self.skills.get(skill_name)
        if not skill:
            return f'[ERROR: Skill "{skill_name}" not found]'

        instructions = skill['instructions']

        # Find and expand sub-skill references
        def replace_invoke(match):
            sub_skill_name = match.group(1)
            sub_skill = self.skills.get(sub_skill_name)

            if not sub_skill:
                return f'[Sub-skill "{sub_skill_name}" not found]'

            # Recursively resolve sub-skill
            sub_instructions = self.resolve_skill_instructions(sub_skill_name, depth + 1)

            return f"""
<sub_skill name="{sub_skill_name}" type="{sub_skill['type']}">
{sub_instructions}
</sub_skill>
"""

        resolved = re.sub(self.INVOKE_SKILL_PATTERN, replace_invoke, instructions)
        return resolved

    def get_skill_with_dependencies(self, skill_name: str) -> dict | None:
        """Get skill with all resolved dependencies.

        Args:
            skill_name: Name of the skill

        Returns:
            Dictionary containing:
            - skill: Original skill data
            - resolved_instructions: Instructions with sub-skills expanded
            - all_tools: Combined list of required tools from skill and sub-skills
            - all_kbs: Combined list of required knowledge bases
        """
        skill = self.skills.get(skill_name)
        if not skill:
            return None

        all_tools = set(skill.get('requires_tools', []))
        all_kbs = set(skill.get('requires_kbs', []))

        # Collect dependencies from sub-skills
        for sub_skill_name in skill.get('requires_skills', []):
            sub_skill = self.skills.get(sub_skill_name)
            if sub_skill:
                all_tools.update(sub_skill.get('requires_tools', []))
                all_kbs.update(sub_skill.get('requires_kbs', []))

        return {
            'skill': skill,
            'resolved_instructions': self.resolve_skill_instructions(skill_name),
            'all_tools': list(all_tools),
            'all_kbs': list(all_kbs),
        }

    def build_activation_prompt(self, skill_name: str) -> str:
        """Build the prompt to inject when a skill is activated.

        Args:
            skill_name: Name of the activated skill

        Returns:
            Formatted prompt string with skill instructions
        """
        resolved = self.get_skill_with_dependencies(skill_name)
        if not resolved:
            return ''

        skill = resolved['skill']
        instructions = resolved['resolved_instructions']

        tools_info = ', '.join(resolved['all_tools']) if resolved['all_tools'] else 'None specified'
        kbs_info = ', '.join(resolved['all_kbs']) if resolved['all_kbs'] else 'None specified'

        return f"""
<activated_skill name="{skill_name}" type="{skill['type']}">

## Instructions
{instructions}

## Available Resources
- Required Tools: {tools_info}
- Required Knowledge Bases: {kbs_info}

</activated_skill>

Now execute the above skill instructions step by step to complete the user's request.
If the skill contains sub-skills (<sub_skill> tags), execute them in the order they appear.
Respond to the user based on the skill's guidance.
"""

    async def get_pipeline_bound_skills(self, pipeline_uuid: str) -> list[str]:
        """Get list of skill UUIDs bound to a pipeline.

        Args:
            pipeline_uuid: Pipeline UUID

        Returns:
            List of bound skill UUIDs
        """
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_skill.SkillPipelineBinding.skill_uuid)
            .where(persistence_skill.SkillPipelineBinding.pipeline_uuid == pipeline_uuid)
            .where(persistence_skill.SkillPipelineBinding.is_enabled == True)
            .order_by(persistence_skill.SkillPipelineBinding.priority.desc())
        )

        return [row[0] for row in result.all()]

    def remove_activation_marker(self, response: str) -> str:
        """Remove skill activation marker from response.

        Args:
            response: Original response with potential activation marker

        Returns:
            Response with activation marker removed
        """
        return re.sub(r'\[ACTIVATE_SKILL:\s*\S+?\s*\]\s*', '', response, count=1)
