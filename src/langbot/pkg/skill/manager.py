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
    """Skill manager backed by Box-managed or local filesystem packages.

    In sandbox deployments, skills are loaded from the Box runtime. Local
    data/skills remains as the fallback for non-Box development.

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
        """Reload all skills from the Box runtime.

        Box is the only source of truth for skills. When Box is unavailable
        (disabled in config or unreachable) the cache is emptied — there is
        no local filesystem fallback. Skills whose ``package_root`` is no
        longer visible on the LangBot-side filesystem are dropped so they
        don't surface as stale ``extra_mounts``.
        """
        self.skills = {}

        box_service = getattr(self.ap, 'box_service', None)
        if box_service is None or not getattr(box_service, 'available', False):
            self.ap.logger.info('Box runtime unavailable; skill cache is empty.')
            return

        try:
            dropped = 0
            for skill_data in await box_service.list_skills():
                skill_name = skill_data.get('name')
                if not skill_name:
                    continue
                package_root = str(skill_data.get('package_root', '') or '').strip()
                if package_root and not os.path.isdir(package_root):
                    self.ap.logger.warning(
                        f'Skill "{skill_name}" reported by Box runtime but '
                        f'package_root missing on LangBot filesystem '
                        f'({package_root}); dropping from in-memory cache.'
                    )
                    dropped += 1
                    continue
                self.skills[skill_name] = skill_data
            if dropped:
                self.ap.logger.warning(
                    f'Loaded {len(self.skills)} skills from Box runtime '
                    f'({dropped} dropped due to missing package_root).'
                )
            else:
                self.ap.logger.info(f'Loaded {len(self.skills)} skills from Box runtime')
        except Exception as exc:
            self.ap.logger.warning(f'Failed to load skills from Box runtime: {exc}')

    def refresh_skill_from_disk(self, skill_name: str) -> bool:
        """Confirm a single skill is present in the cache.

        With Box as the only source of truth, the actual reload is driven by
        SkillService callers awaiting ``reload_skills``; this method only
        reports whether the cache still has the skill.
        """
        if not skill_name:
            return False
        return skill_name in self.skills
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
