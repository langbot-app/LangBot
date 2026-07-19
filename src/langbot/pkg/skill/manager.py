from __future__ import annotations

import os

from ..api.http.context import ExecutionContext
from ..api.http.service.tenant import TenantContext, require_workspace_uuid
from ..core import app


class SkillManager:
    """Workspace-scoped in-memory view of Box-managed skill packages."""

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap
        self._skills_by_scope: dict[tuple[str, str, int], dict[str, dict]] = {}

    @staticmethod
    def _execution_context(context: TenantContext) -> ExecutionContext:
        workspace_uuid = require_workspace_uuid(context)
        instance_uuid = str(getattr(context, 'instance_uuid', '') or '').strip()
        generation = getattr(context, 'placement_generation', None)
        if not instance_uuid or isinstance(generation, bool) or not isinstance(generation, int) or generation <= 0:
            raise ValueError('Skill cache requires an explicit fenced execution context')
        return ExecutionContext(
            instance_uuid=instance_uuid,
            workspace_uuid=workspace_uuid,
            placement_generation=generation,
            bot_uuid=getattr(context, 'bot_uuid', None),
            pipeline_uuid=getattr(context, 'pipeline_uuid', None),
            query_uuid=getattr(context, 'query_uuid', None),
        )

    @classmethod
    def _scope_key(cls, context: TenantContext) -> tuple[str, str, int]:
        execution_context = cls._execution_context(context)
        return (
            execution_context.instance_uuid,
            execution_context.workspace_uuid,
            execution_context.placement_generation,
        )

    async def initialize(self):
        try:
            binding = await self.ap.workspace_service.get_execution_binding()
        except Exception:
            self.ap.logger.info('No unambiguous Workspace binding; skill caches will load on demand.')
            return
        await self.reload_skills(
            ExecutionContext(
                instance_uuid=binding.instance_uuid,
                workspace_uuid=binding.workspace_uuid,
                placement_generation=binding.placement_generation,
            )
        )

    async def reload_skills(self, context: TenantContext) -> None:
        execution_context = self._execution_context(context)
        key = self._scope_key(execution_context)
        self._skills_by_scope[key] = {}

        box_service = getattr(self.ap, 'box_service', None)
        if box_service is None or not getattr(box_service, 'available', False):
            self.ap.logger.info(
                f'Box runtime unavailable; skill cache is empty for Workspace {execution_context.workspace_uuid}.'
            )
            return

        validate_locally = bool(getattr(box_service, 'shares_filesystem_with_box', False))
        try:
            dropped = 0
            skills: dict[str, dict] = {}
            for skill_data in await box_service.list_skills(execution_context):
                skill_name = skill_data.get('name')
                if not skill_name:
                    continue
                package_root = str(skill_data.get('package_root', '') or '').strip()
                if validate_locally and package_root and not os.path.isdir(package_root):
                    self.ap.logger.warning(
                        f'Skill "{skill_name}" reported by Box runtime but package_root '
                        f'missing on LangBot filesystem ({package_root}); dropping from cache.'
                    )
                    dropped += 1
                    continue
                skills[skill_name] = skill_data
            self._skills_by_scope[key] = skills
            suffix = f' ({dropped} dropped due to missing package_root)' if dropped else ''
            self.ap.logger.info(f'Loaded {len(skills)} skills for Workspace {execution_context.workspace_uuid}{suffix}')
        except Exception as exc:
            self.ap.logger.warning(f'Failed to load skills for Workspace {execution_context.workspace_uuid}: {exc}')

    async def ensure_loaded(self, context: TenantContext) -> None:
        key = self._scope_key(context)
        if key not in self._skills_by_scope:
            await self.reload_skills(context)

    def get_skills(self, context: TenantContext) -> dict[str, dict]:
        return self._skills_by_scope.get(self._scope_key(context), {})

    def refresh_skill_from_disk(self, context: TenantContext, skill_name: str) -> bool:
        return bool(skill_name) and skill_name in self.get_skills(context)

    def get_skill_by_name(self, context: TenantContext, name: str) -> dict | None:
        return self.get_skills(context).get(name)

    def get_skill_index(self, context: TenantContext, bound_skills: list[str] | None = None) -> str:
        lines: list[str] = []
        for skill in self.get_skills(context).values():
            name = skill.get('name')
            if not name or (bound_skills is not None and name not in bound_skills):
                continue
            display = skill.get('display_name') or name
            description = (skill.get('description') or '').strip().replace('\n', ' ')
            lines.append(f'- {name} ({display}): {description}')
        return 'Available Skills:\n' + '\n'.join(lines) if lines else ''

    def build_skill_aware_prompt_addition(
        self,
        context: TenantContext,
        bound_skills: list[str] | None = None,
    ) -> str:
        skill_index = self.get_skill_index(context, bound_skills)
        if not skill_index:
            return ''
        return (
            '\n\n'
            f'{skill_index}\n\n'
            "When the user's request clearly matches one or more skills "
            'based on their descriptions above, call the `activate` tool with '
            'the skill name to load its full instructions. Only the name and '
            'description are visible here; the actual instructions arrive as '
            'the tool result. If no skill is a clear match, respond normally '
            'without activating any skill.'
        )

    def total_cached_skill_count(self) -> int:
        return sum(len(skills) for skills in self._skills_by_scope.values())
