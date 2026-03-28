from __future__ import annotations

import datetime as dt
import os
import re
import typing

from ..core import app
from .utils import parse_frontmatter
from ..utils import paths

if typing.TYPE_CHECKING:
    pass


class SkillManager:
    """Skill manager backed purely by filesystem packages under data/skills."""

    SKILL_ACTIVATION_MARKER = '[ACTIVATE_SKILL:'

    ap: app.Application
    skills: dict[str, dict]

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.skills = {}

    async def initialize(self):
        await self.reload_skills()

    async def reload_skills(self):
        self.skills = {}

        skills_root = self.get_managed_skills_root()
        if not os.path.isdir(skills_root):
            self.ap.logger.info('Loaded 0 skills')
            return

        for package_root, entry_file in self._discover_skill_directories(skills_root):
            skill_data = {
                'package_root': package_root,
                'entry_file': entry_file,
            }
            if not self._load_skill_file(skill_data):
                continue

            skill_name = skill_data['name']
            if skill_name in self.skills:
                self.ap.logger.warning(
                    f'Duplicate skill name "{skill_name}" found at {package_root}, skipping later entry'
                )
                continue

            self.skills[skill_name] = skill_data

        self.ap.logger.info(f'Loaded {len(self.skills)} skills')

    def refresh_skill_from_disk(self, skill_name: str) -> bool:
        if not skill_name:
            return False

        skill_data = self.skills.get(skill_name)
        if not skill_data:
            return False

        if not self._load_skill_file(skill_data):
            return False

        self.skills[skill_name] = skill_data
        return True

    @staticmethod
    def get_managed_skills_root() -> str:
        return paths.get_data_path('skills')

    def _discover_skill_directories(self, root_path: str, max_depth: int = 6) -> list[tuple[str, str]]:
        discovered: list[tuple[str, str]] = []
        root_path = os.path.realpath(os.path.abspath(root_path))
        root_depth = root_path.rstrip(os.sep).count(os.sep)

        for current_root, dirs, _files in os.walk(root_path):
            current_root = os.path.realpath(current_root)
            depth = current_root.rstrip(os.sep).count(os.sep) - root_depth
            if depth > max_depth:
                dirs[:] = []
                continue

            found = self._find_skill_entry(current_root)
            if found is not None:
                discovered.append(found)
                dirs[:] = []

        discovered.sort(key=lambda item: item[0])
        return discovered

    @staticmethod
    def _find_skill_entry(path: str) -> tuple[str, str] | None:
        for candidate in ('SKILL.md', 'skill.md'):
            if os.path.isfile(os.path.join(path, candidate)):
                return path, candidate
        return None

    def _load_skill_file(self, skill_data: dict) -> bool:
        package_root = self._normalize_package_root(skill_data.get('package_root', ''))
        entry_file = skill_data.get('entry_file', 'SKILL.md')
        if not package_root:
            self.ap.logger.warning('Skill package_root is empty, skipping')
            return False

        entry_path = os.path.join(package_root, entry_file)
        try:
            with open(entry_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            self.ap.logger.warning(f'Skill entry file not found: {entry_path}, skipping')
            return False
        except OSError as exc:
            self.ap.logger.warning(f'Failed to read skill entry file {entry_path}: {exc}, skipping')
            return False

        metadata, instructions = parse_frontmatter(content)
        name = str(metadata.get('name') or os.path.basename(os.path.normpath(package_root))).strip()
        if not name:
            self.ap.logger.warning(f'Skill at {package_root} has no valid name, skipping')
            return False

        stat = os.stat(entry_path)
        skill_data.clear()
        skill_data.update(
            {
                'name': name,
                'display_name': str(metadata.get('display_name') or name).strip(),
                'description': str(metadata.get('description') or '').strip(),
                'instructions': instructions,
                'raw_content': content,
                'package_root': package_root,
                'entry_file': entry_file,
                'auto_activate': bool(metadata.get('auto_activate', True)),
                'created_at': dt.datetime.fromtimestamp(stat.st_ctime, tz=dt.timezone.utc).isoformat(),
                'updated_at': dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc).isoformat(),
            }
        )
        return True

    @staticmethod
    def _normalize_package_root(package_root: str) -> str:
        if not package_root:
            return ''
        return os.path.realpath(os.path.abspath(package_root))

    def get_skill_by_name(self, name: str) -> dict | None:
        return self.skills.get(name)

    def get_skill_index(self, pipeline_uuid: str | None = None, bound_skills: list[str] | None = None) -> str:
        skills_to_index = []
        for skill in self.skills.values():
            if not skill.get('auto_activate', True):
                continue
            if bound_skills is not None and skill['name'] not in bound_skills:
                continue
            skills_to_index.append(skill)

        if not skills_to_index:
            return ''

        lines = ['Available Skills:']
        for skill in skills_to_index:
            display = skill.get('display_name') or skill['name']
            lines.append(f'- {skill["name"]} ({display}): {skill.get("description", "")}')
        return '\n'.join(lines)

    def build_skill_aware_prompt_addition(
        self, pipeline_uuid: str | None = None, bound_skills: list[str] | None = None
    ) -> str:
        skill_index = self.get_skill_index(pipeline_uuid, bound_skills)
        if not skill_index:
            return ''

        return f"""

{skill_index}

When the user's request clearly matches one or more skills based on their descriptions, you should activate them.
To activate a skill, include this marker at the beginning of your response: [ACTIVATE_SKILL: skill-name]
If multiple skills are needed, include multiple activation markers at the beginning of your response, one per line.
After activation, the selected skills' detailed instructions will be loaded for you to follow.
Use the first activated skill as the primary skill. Use any additional activated skills as supporting guidance.
If you need to inspect a visible skill before activation, use `read` on `/workspace/.skills/<skill-name>/SKILL.md` or other files under that path.
For prompt-only skills or skills that mainly consist of instructions, use `create_skill` to create them directly in the managed skills store.
Use `list_skills` or `get_skill` before editing when you need to inspect what already exists.
Use `update_skill` to modify an existing managed skill's metadata or instructions without relying on `/workspace`, box, or skill activation.
Use `delete_skill` when the user explicitly wants to remove a managed skill.
Pure prompt skills should not depend on box just to be created or modified later.
When creating a new skill package with extra files, scripts, or assets, first prepare it under `/workspace` with the standard `exec`, `read`, `write`, and `edit` tools.
Then use `import_skill_from_directory` to import that prepared directory into the managed skills store.
Use `reload_skills` when you need LangBot to rescan managed skills after filesystem changes.
If no skill matches, respond normally without activation.
"""

    def detect_skill_activations(self, response: str) -> list[str]:
        if self.SKILL_ACTIVATION_MARKER not in response:
            return []

        activated: list[str] = []
        for skill_name in re.findall(r'\[ACTIVATE_SKILL:\s*(\S+?)\s*\]', response):
            if skill_name in self.skills and skill_name not in activated:
                activated.append(skill_name)
        return activated

    def detect_skill_activation(self, response: str) -> str | None:
        activations = self.detect_skill_activations(response)
        return activations[0] if activations else None

    def get_skill_runtime_data(self, skill_name: str) -> dict | None:
        skill = self.skills.get(skill_name)
        if not skill:
            return None
        return {'skill': skill, 'instructions': skill.get('instructions', '')}

    def build_activation_prompt(self, skill_name: str) -> str:
        resolved = self.get_skill_runtime_data(skill_name)
        if not resolved:
            return ''

        instructions = resolved['instructions']
        return f"""
<activated_skill name=\"{skill_name}\">

## Instructions
{instructions}

## Runtime Context
The activated skill package is available through the standard runtime tools under `/workspace/.skills/{skill_name}`.
Use `read` to inspect files there. Use `exec` with `workdir` set to `/workspace/.skills/{skill_name}` to run commands in that package.
Use `write` and `edit` on that path when the instructions require updating files.
Do not create a new skill by writing directly into `/workspace/.skills/...`; use `create_skill` for prompt-only skills, `update_skill` to change an existing managed skill, `list_skills` or `get_skill` to inspect managed skills, or prepare the new skill under `/workspace` and import it with `import_skill_from_directory`.

</activated_skill>

Now execute the above skill instructions step by step to complete the user's request.
Use the standard `exec`, `read`, `write`, and `edit` tools against `/workspace/.skills/{skill_name}` when you need to inspect or modify the skill package.
Respond to the user based on the skill's guidance.
"""

    def build_activation_prompt_for_skills(self, skill_names: list[str]) -> str:
        if not skill_names:
            return ''

        activated_skill_names: list[str] = []
        for skill_name in skill_names:
            if skill_name in self.skills and skill_name not in activated_skill_names:
                activated_skill_names.append(skill_name)
        if not activated_skill_names:
            return ''

        blocks: list[str] = []
        for skill_name in activated_skill_names:
            resolved = self.get_skill_runtime_data(skill_name)
            if not resolved:
                continue
            instructions = resolved['instructions']
            role = 'primary' if skill_name == activated_skill_names[0] else 'auxiliary'
            blocks.append(
                f"""
<activated_skill name=\"{skill_name}\" role=\"{role}\">\n\n## Instructions\n{instructions}\n\n## Runtime Context\nUse the standard `exec`, `read`, `write`, and `edit` tools for activated skills.\nEach activated skill package is available under `/workspace/.skills/<skill-name>`.\nFor a given skill, set `exec.workdir` to `/workspace/.skills/<skill-name>` and use that prefix in file tool paths.\nDo not create a new skill under `/workspace/.skills/...`; use `create_skill` for prompt-only skills, `list_skills` or `get_skill` to inspect managed skills, `update_skill` to change an existing managed skill, or prepare new skill directories under `/workspace` and import them with `import_skill_from_directory`.\n\n</activated_skill>
""".strip()
            )
        if not blocks:
            return ''

        activated_list = ', '.join(activated_skill_names)
        return f"""
Activated skills: {activated_list}

{chr(10).join(blocks)}

Now execute the activated skills to complete the user's request.
Treat the first activated skill as the primary skill.
Treat additional activated skills as supporting guidance when they do not conflict with the primary skill.
If guidance conflicts, prefer: primary skill > auxiliary skills.
Use the standard `exec`, `read`, `write`, and `edit` tools against the corresponding `/workspace/.skills/<skill-name>` path whenever you need to inspect or modify an activated skill package.
Respond to the user with one coherent answer that integrates the activated skills.
"""

    @staticmethod
    def remove_activation_marker(response: str) -> str:
        return re.sub(r'\[ACTIVATE_SKILL:\s*\S+?\s*\]\s*', '', response).lstrip()
