from __future__ import annotations

import os
import re
import typing

import sqlalchemy

from ..core import app
from ..entity.persistence import skill as persistence_skill
from .utils import parse_frontmatter

if typing.TYPE_CHECKING:
    import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


class SkillManager:
    """Skill manager for loading, matching and resolving skills.

    DB is the registry (uuid, name, package_root, is_enabled, sandbox config).
    SKILL.md frontmatter is the canonical source for package metadata
    (display_name, description, author, type, requires_*, etc.).
    """

    INVOKE_SKILL_PATTERN = r'\{\{INVOKE_SKILL:\s*(\S+)\s*\}\}'
    SKILL_ACTIVATION_MARKER = '[ACTIVATE_SKILL:'

    ap: app.Application

    skills: dict[str, dict]
    """Skills indexed by name — merged from DB registry + file metadata"""

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
        """Reload all skills from database, then parse SKILL.md for metadata."""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_skill.Skill).where(persistence_skill.Skill.is_enabled == True)
        )
        skills_list = result.all()

        self.skills = {}
        self.skills_by_uuid = {}

        for skill in skills_list:
            skill_data = self.ap.persistence_mgr.serialize_model(persistence_skill.Skill, skill)
            skill_data['package_root'] = self._normalize_package_root(skill_data.get('package_root', ''))

            # Load and parse SKILL.md — extracts instructions + frontmatter metadata
            if not self._load_skill_file(skill_data):
                continue

            self.skills[skill_data['name']] = skill_data
            self.skills_by_uuid[skill_data['uuid']] = skill_data

        self.ap.logger.info(f'Loaded {len(self.skills)} skills')

    def refresh_skill_from_disk(self, skill_name: str) -> bool:
        """Refresh one loaded skill in place after its package changes on disk."""
        if not skill_name:
            return False

        skill_data = self.skills.get(skill_name)
        if not skill_data:
            return False

        skill_data['package_root'] = self._normalize_package_root(skill_data.get('package_root', ''))
        if not self._load_skill_file(skill_data):
            return False

        skill_uuid = skill_data.get('uuid')
        if skill_uuid:
            self.skills_by_uuid[skill_uuid] = skill_data
        return True

    def _load_skill_file(self, skill_data: dict) -> bool:
        """Load SKILL.md: parse frontmatter for metadata, body for instructions.

        Populates skill_data with: instructions, display_name, description,
        type, author, version, tags, auto_activate, trigger_keywords,
        requires_tools, requires_kbs, requires_skills.

        Args:
            skill_data: Skill data dict (modified in place)

        Returns:
            True if loaded successfully, False otherwise
        """
        package_root = skill_data.get('package_root')
        entry_file = skill_data.get('entry_file', 'SKILL.md')

        if not package_root:
            self.ap.logger.warning(
                f'Skill "{skill_data["name"]}" has no package_root, skipping'
            )
            return False

        entry_path = os.path.join(package_root, entry_file)
        try:
            with open(entry_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            self.ap.logger.warning(
                f'Skill "{skill_data["name"]}" entry file not found: {entry_path}, skipping'
            )
            return False
        except OSError as e:
            self.ap.logger.warning(
                f'Skill "{skill_data["name"]}" failed to read entry file: {e}, skipping'
            )
            return False

        # Parse frontmatter + body
        metadata, instructions = parse_frontmatter(content)

        # Store raw content and parsed instructions
        skill_data['instructions'] = instructions
        skill_data['raw_content'] = content

        # Merge frontmatter metadata into skill_data (file is canonical source)
        skill_data['display_name'] = metadata.get('display_name', '')
        skill_data['description'] = metadata.get('description', '')
        skill_data['type'] = metadata.get('type', 'skill')
        skill_data['author'] = metadata.get('author', '')
        skill_data['version'] = metadata.get('version', '1.0.0')
        skill_data['tags'] = metadata.get('tags', [])
        skill_data['auto_activate'] = metadata.get('auto_activate', True)
        skill_data['trigger_keywords'] = metadata.get('trigger_keywords', [])
        skill_data['requires_tools'] = metadata.get('requires_tools', [])
        skill_data['requires_kbs'] = metadata.get('requires_kbs', [])
        skill_data['requires_skills'] = metadata.get('requires_skills', [])

        return True

    def _normalize_package_root(self, package_root: str) -> str:
        if not package_root:
            return ''
        return os.path.realpath(os.path.abspath(package_root))

    def get_skill_by_name(self, name: str) -> dict | None:
        """Get skill by name"""
        return self.skills.get(name)

    def get_skill_by_uuid(self, uuid: str) -> dict | None:
        """Get skill by UUID"""
        return self.skills_by_uuid.get(uuid)

    def get_skill_index(self, pipeline_uuid: str | None = None, bound_skills: list[str] | None = None) -> str:
        """Generate skill index for LLM system prompt."""
        skills_to_index = []

        for skill in self.skills.values():
            if not skill.get('auto_activate', True):
                continue
            if bound_skills is not None and skill['uuid'] not in bound_skills:
                continue
            skills_to_index.append(skill)

        if not skills_to_index:
            return ''

        lines = ['Available Skills:']
        for skill in skills_to_index:
            display = skill.get('display_name') or skill['name']
            lines.append(f"- {skill['name']} ({display}): {skill.get('description', '')}")

        return '\n'.join(lines)

    def build_skill_aware_prompt_addition(self, pipeline_uuid: str | None = None, bound_skills: list[str] | None = None) -> str:
        """Build the skill awareness instruction to add to system prompt."""
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
        """Detect skill activation request from LLM response."""
        if self.SKILL_ACTIVATION_MARKER not in response:
            return None

        match = re.search(r'\[ACTIVATE_SKILL:\s*(\S+?)\s*\]', response)
        if match:
            skill_name = match.group(1)
            if skill_name in self.skills:
                return skill_name

        return None

    def resolve_skill_instructions(self, skill_name: str, depth: int = 0) -> str:
        """Resolve skill instructions with sub-skill expansion."""
        if depth > 5:
            return f'[ERROR: Maximum skill nesting depth exceeded for {skill_name}]'

        skill = self.skills.get(skill_name)
        if not skill:
            return f'[ERROR: Skill "{skill_name}" not found]'

        instructions = skill['instructions']

        def replace_invoke(match):
            sub_skill_name = match.group(1)
            sub_skill = self.skills.get(sub_skill_name)

            if not sub_skill:
                return f'[Sub-skill "{sub_skill_name}" not found]'

            sub_instructions = self.resolve_skill_instructions(sub_skill_name, depth + 1)

            return f"""
<sub_skill name="{sub_skill_name}" type="{sub_skill.get('type', 'skill')}">
{sub_instructions}
</sub_skill>
"""

        resolved = re.sub(self.INVOKE_SKILL_PATTERN, replace_invoke, instructions)
        return resolved

    def get_skill_with_dependencies(self, skill_name: str) -> dict | None:
        """Get skill with all resolved dependencies."""
        skill = self.skills.get(skill_name)
        if not skill:
            return None

        all_tools = set(skill.get('requires_tools', []))
        all_kbs = set(skill.get('requires_kbs', []))

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
        """Build the prompt to inject when a skill is activated."""
        resolved = self.get_skill_with_dependencies(skill_name)
        if not resolved:
            return ''

        skill = resolved['skill']
        instructions = resolved['resolved_instructions']

        tools_info = ', '.join(resolved['all_tools']) if resolved['all_tools'] else 'None specified'
        kbs_info = ', '.join(resolved['all_kbs']) if resolved['all_kbs'] else 'None specified'

        return f"""
<activated_skill name="{skill_name}" type="{skill.get('type', 'skill')}">

## Instructions
{instructions}

## Available Resources
- Required Tools: {tools_info}
- Required Knowledge Bases: {kbs_info}

## Sandbox Execution
You have access to the `skill_exec` tool to run commands inside this skill's sandboxed directory.
The skill directory is mounted at /workspace with write access. You can execute scripts, read files,
update the skill package, and run any command available in the sandbox environment.

</activated_skill>

Now execute the above skill instructions step by step to complete the user's request.
If the skill contains sub-skills (<sub_skill> tags), execute them in the order they appear.
Use the `skill_exec` tool with skill_name="{skill_name}" when you need to run scripts or commands.
Respond to the user based on the skill's guidance.
"""

    def remove_activation_marker(self, response: str) -> str:
        """Remove skill activation marker from response."""
        return re.sub(r'\[ACTIVATE_SKILL:\s*\S+?\s*\]\s*', '', response, count=1)
