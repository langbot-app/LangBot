from __future__ import annotations

import datetime as dt
import os
import typing

from ..core import app
from .utils import parse_frontmatter
from ..utils import paths

if typing.TYPE_CHECKING:
    pass


class SkillManager:
    """Skill manager backed by filesystem packages.

    Skills are loaded from data/skills/ and managed by users.

    Skills are activated through the `activate` tool (Tool Call mechanism),
    aligned with Claude Code's design. This protects KV Cache and follows
    industry standard.
    """

    ap: app.Application
    skills: dict[str, dict]

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.skills = {}

    async def initialize(self):
        await self.reload_skills()

    async def reload_skills(self):
        """Reload all skills.

        All skills are loaded from data/skills/.

        NOTE: This performs a full scan. For registering a single new skill,
        consider adding it directly to self.skills instead of reloading all.
        Current implementation is acceptable for typical skill counts (<50).
        """
        self.skills = {}

        # Ensure data/skills/ exists
        managed_root = self.get_managed_skills_root()
        os.makedirs(managed_root, exist_ok=True)

        # Load all skills from data/skills/
        if os.path.isdir(managed_root):
            for package_root, entry_file in self._discover_skill_directories(managed_root):
                skill_data = {
                    'package_root': package_root,
                    'entry_file': entry_file,
                }
                if not self._load_skill_file(skill_data):
                    continue

                skill_name = skill_data['name']
                self.skills[skill_name] = skill_data

        self.ap.logger.info(f'Loaded {len(self.skills)} skills')

    def refresh_skill_from_disk(self, skill_name: str) -> bool:
        """Refresh a single skill from disk."""
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
        """Get the root directory for managed user skills."""
        return paths.get_data_path('skills')

    def _discover_skill_directories(self, root_path: str, max_depth: int = 6) -> list[tuple[str, str]]:
        """Discover all skill directories under root_path."""
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
        """Find SKILL.md entry file in a directory."""
        for candidate in ('SKILL.md', 'skill.md'):
            if os.path.isfile(os.path.join(path, candidate)):
                return path, candidate
        return None

    def _load_skill_file(self, skill_data: dict) -> bool:
        """Load skill data from SKILL.md file."""
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
        """Get skill data by name."""
        return self.skills.get(name)
