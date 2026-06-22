from __future__ import annotations

import os
import typing

from ..core import app

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

        # LangBot may only validate Box-reported paths against its own
        # filesystem when the two share one (local stdio mode). In separated
        # deployments (Docker Compose, k8s sidecar, --standalone-box, remote
        # endpoint) the package_root lives on the Box runtime's filesystem and
        # is not resolvable here, so we trust what Box reports.
        validate_locally = bool(getattr(box_service, 'shares_filesystem_with_box', False))

        try:
            dropped = 0
            for skill_data in await box_service.list_skills():
                skill_name = skill_data.get('name')
                if not skill_name:
                    continue
                package_root = str(skill_data.get('package_root', '') or '').strip()
                if validate_locally and package_root and not os.path.isdir(package_root):
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

    def get_skill_by_name(self, name: str) -> dict | None:
        """Get skill data by name."""
        return self.skills.get(name)
