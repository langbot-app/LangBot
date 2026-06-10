from __future__ import annotations

import re
import typing

from ....box import workspace as box_workspace

if typing.TYPE_CHECKING:
    from ....core import app
    from langbot_plugin.api.entities.events import pipeline_query

ACTIVATED_SKILLS_KEY = '_activated_skills'
PIPELINE_BOUND_SKILLS_KEY = '_pipeline_bound_skills'
SKILL_MOUNT_PREFIX = '/workspace/.skills'
_SKILL_MOUNT_PATTERN = re.compile(r'/workspace/\.skills/([A-Za-z0-9_-]+)')


def get_virtual_skill_mount_path(skill_name: str) -> str:
    return f'{SKILL_MOUNT_PREFIX}/{skill_name}'


def get_bound_skill_names(query: pipeline_query.Query) -> list[str] | None:
    if query.variables is None:
        return None

    bound_skills = query.variables.get(PIPELINE_BOUND_SKILLS_KEY)
    if bound_skills is None:
        return None
    if isinstance(bound_skills, list):
        return [str(item) for item in bound_skills]
    return None


def get_visible_skills(ap: app.Application, query: pipeline_query.Query) -> dict[str, dict]:
    skill_mgr = getattr(ap, 'skill_mgr', None)
    if skill_mgr is None:
        return {}

    visible_skills = getattr(skill_mgr, 'skills', {})
    bound_skills = get_bound_skill_names(query)
    if bound_skills is None:
        return visible_skills

    return {skill_name: skill_data for skill_name, skill_data in visible_skills.items() if skill_name in bound_skills}


def get_visible_skill(ap: app.Application, query: pipeline_query.Query, skill_name: str) -> dict | None:
    return get_visible_skills(ap, query).get(skill_name)


def get_activated_skills(query: pipeline_query.Query) -> dict[str, dict]:
    if query.variables is None:
        return {}

    activated = query.variables.get(ACTIVATED_SKILLS_KEY, {})
    if not isinstance(activated, dict):
        return {}
    return activated


def get_activated_skill(query: pipeline_query.Query, skill_name: str) -> dict | None:
    return get_activated_skills(query).get(skill_name)


def register_activated_skill(query: pipeline_query.Query, skill_data: dict) -> None:
    if query.variables is None:
        query.variables = {}

    activated = query.variables.setdefault(ACTIVATED_SKILLS_KEY, {})
    skill_name = str(skill_data.get('name', '') or '').strip()
    if skill_name and skill_name not in activated:
        activated[skill_name] = skill_data


def parse_skill_mount_path(sandbox_path: str) -> tuple[str | None, str]:
    normalized_path = str(sandbox_path or '/workspace').strip() or '/workspace'
    if normalized_path == SKILL_MOUNT_PREFIX:
        raise ValueError(f'Path must include a skill name under {SKILL_MOUNT_PREFIX}/<skill-name>.')
    prefix = f'{SKILL_MOUNT_PREFIX}/'
    if not normalized_path.startswith(prefix):
        return None, normalized_path

    remainder = normalized_path[len(prefix) :]
    skill_name, separator, tail = remainder.partition('/')
    if not skill_name:
        raise ValueError(f'Path must include a skill name under {SKILL_MOUNT_PREFIX}/<skill-name>.')

    rewritten_path = '/workspace'
    if separator:
        rewritten_path = f'/workspace/{tail}'
    return skill_name, rewritten_path


def resolve_virtual_skill_path(
    ap: app.Application,
    query: pipeline_query.Query,
    sandbox_path: str,
    *,
    include_visible: bool,
    include_activated: bool,
) -> tuple[dict | None, str]:
    skill_name, rewritten_path = parse_skill_mount_path(sandbox_path)
    if skill_name is None:
        return None, rewritten_path

    if include_activated:
        activated_skill = get_activated_skill(query, skill_name)
        if activated_skill is not None:
            return activated_skill, rewritten_path

    if include_visible:
        visible_skill = get_visible_skill(ap, query, skill_name)
        if visible_skill is not None:
            return visible_skill, rewritten_path

    activated_names = ', '.join(sorted(get_activated_skills(query).keys())) or 'none'
    visible_names = ', '.join(sorted(get_visible_skills(ap, query).keys())) or 'none'
    raise ValueError(
        f'Skill "{skill_name}" is not available at this path. '
        f'Activated skills: {activated_names}. Visible skills: {visible_names}.'
    )


def find_referenced_skill_names(text: str) -> list[str]:
    if not text:
        return []

    seen: list[str] = []
    for match in _SKILL_MOUNT_PATTERN.findall(text):
        if match not in seen:
            seen.append(match)
    return seen


def rewrite_command_for_skill_mount(command: str, skill_name: str) -> str:
    virtual_root = get_virtual_skill_mount_path(skill_name)
    rewritten = command.replace(f'{virtual_root}/', '/workspace/')
    return rewritten.replace(virtual_root, '/workspace')


def build_skill_session_id(skill_data: dict, query: pipeline_query.Query) -> str:
    skill_identifier = str(skill_data.get('name', 'unknown') or 'unknown')
    launcher_type = getattr(query, 'launcher_type', None)
    launcher_id = getattr(query, 'launcher_id', None)
    query_id = getattr(query, 'query_id', 'unknown')

    if launcher_type is not None and launcher_id is not None:
        return f'skill-{launcher_type}_{launcher_id}-{skill_identifier}'
    return f'skill-{query_id}-{skill_identifier}'


def should_prepare_skill_python_env(package_root: str | None) -> bool:
    return box_workspace.should_prepare_python_env(package_root)


def wrap_skill_command_with_python_env(command: str, *, mount_path: str = '/workspace') -> str:
    return box_workspace.wrap_python_command_with_env(command, mount_path=mount_path).rstrip()
