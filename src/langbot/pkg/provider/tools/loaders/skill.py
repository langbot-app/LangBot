from __future__ import annotations

import os
import re
import typing

from ....api.http.context import ExecutionContext
from ....utils.python_workspace import (
    should_prepare_python_env,
    wrap_python_command_with_env,
)

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

    execution_context = ExecutionContext(
        instance_uuid=str(getattr(query, 'instance_uuid', '') or ''),
        workspace_uuid=str(getattr(query, 'workspace_uuid', '') or ''),
        placement_generation=getattr(query, 'placement_generation', 0) or 0,
        bot_uuid=getattr(query, 'bot_uuid', None),
        pipeline_uuid=getattr(query, 'pipeline_uuid', None),
        query_uuid=getattr(query, 'query_uuid', None),
    )
    visible_skills = skill_mgr.get_skills(execution_context)
    bound_skills = get_bound_skill_names(query)
    if bound_skills is None:
        return visible_skills

    return {skill_name: skill_data for skill_name, skill_data in visible_skills.items() if skill_name in bound_skills}


def get_visible_skill(ap: app.Application, query: pipeline_query.Query, skill_name: str) -> dict | None:
    return get_visible_skills(ap, query).get(skill_name)


def build_execution_mounts(ap: app.Application, query: pipeline_query.Query) -> list[dict]:
    """Mount only immutable revisions pinned by this run's activations."""

    mounts: list[dict] = []
    for skill_name, skill_data in get_activated_skills(query).items():
        package_root = str(skill_data.get('package_root', '') or '').strip()
        manifest_path = str(skill_data.get('manifest_path', '') or '').strip()
        revision = str(skill_data.get('revision', '') or '').strip()
        if not package_root:
            raise ValueError(f'Activated skill "{skill_name}" has no immutable package root.')
        if not revision:
            raise ValueError(f'Activated skill "{skill_name}" has no pinned revision.')
        if not os.path.isdir(package_root):
            raise ValueError(
                f'Activated skill "{skill_name}" pinned revision {revision} is unavailable; '
                'the run cannot be recovered safely.'
            )
        if not manifest_path or not os.path.isfile(manifest_path):
            raise ValueError(f'Activated skill "{skill_name}" pinned revision {revision} has no publication manifest.')
        mounts.append(
            {
                'host_path': package_root,
                'mount_path': get_virtual_skill_mount_path(skill_name),
                'mode': 'ro',
                'content_digest': revision,
                'manifest_path': manifest_path,
            }
        )
    return mounts


def get_activated_skills(query: pipeline_query.Query) -> dict[str, dict]:
    if query.variables is None:
        return {}

    activated = query.variables.get(ACTIVATED_SKILLS_KEY, {})
    if not isinstance(activated, dict):
        return {}
    return activated


def get_activated_skill(query: pipeline_query.Query, skill_name: str) -> dict | None:
    return get_activated_skills(query).get(skill_name)


def register_activated_skill(query: pipeline_query.Query, skill_data: dict) -> dict:
    if query.variables is None:
        query.variables = {}

    activated = query.variables.setdefault(ACTIVATED_SKILLS_KEY, {})
    skill_name = str(skill_data.get('name', '') or '').strip()
    revision = str(skill_data.get('revision', '') or '').strip()
    if not skill_name or not revision:
        raise ValueError('Activated Skills require a name and immutable revision.')
    if skill_name not in activated:
        activated[skill_name] = dict(skill_data)
    return activated[skill_name]


def normalize_skill_names(value: typing.Any) -> list[str]:
    """Return a de-duplicated list of non-empty skill names."""
    if not isinstance(value, list):
        return []

    names: list[str] = []
    for item in value:
        skill_name = str(item or '').strip()
        if skill_name and skill_name not in names:
            names.append(skill_name)
    return names


def get_activated_skill_names(query: pipeline_query.Query) -> list[str]:
    """Return activated skill names for callers that own persistence policy."""
    return normalize_skill_names(list(get_activated_skills(query).keys()))


def get_activated_skill_bindings(query: pipeline_query.Query) -> list[dict[str, str]]:
    """Return exact bindings suitable for persistence and restart recovery."""

    return [
        {'name': name, 'revision': str(skill.get('revision', '') or '')}
        for name, skill in get_activated_skills(query).items()
    ]


def normalize_skill_bindings(value: typing.Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError('Activated Skill recovery requires revision bindings.')
    bindings: list[dict[str, str]] = []
    seen: dict[str, str] = {}
    for item in value:
        if not isinstance(item, dict):
            raise ValueError('Activated Skill recovery cannot use names without revisions.')
        name = str(item.get('name', '') or '').strip()
        revision = str(item.get('revision', '') or '').strip()
        if not name or not revision:
            raise ValueError('Each activated Skill binding requires name and revision.')
        previous = seen.get(name)
        if previous is not None and previous != revision:
            raise ValueError(f'Conflicting pinned revisions supplied for Skill "{name}".')
        if previous is None:
            seen[name] = revision
            bindings.append({'name': name, 'revision': revision})
    return bindings


async def restore_activated_skills(
    ap: app.Application,
    query: pipeline_query.Query,
    skill_bindings: typing.Any,
) -> list[str]:
    """Restore exact revisions or fail explicitly; never resolve latest by name."""

    repository = getattr(ap, 'skill_repository', None)
    if repository is None:
        raise ValueError('Skill repository is unavailable during run recovery.')
    context = ExecutionContext(
        instance_uuid=str(getattr(query, 'instance_uuid', '') or ''),
        workspace_uuid=str(getattr(query, 'workspace_uuid', '') or ''),
        placement_generation=getattr(query, 'placement_generation', 0) or 0,
        bot_uuid=getattr(query, 'bot_uuid', None),
        pipeline_uuid=getattr(query, 'pipeline_uuid', None),
        query_uuid=getattr(query, 'query_uuid', None),
    )
    bound_names = get_bound_skill_names(query)
    restored: list[str] = []
    for binding in normalize_skill_bindings(skill_bindings):
        skill_name = binding['name']
        if bound_names is not None and skill_name not in bound_names:
            raise ValueError(f'Skill "{skill_name}" is no longer authorized for this recoverable run.')
        skill_data = await repository.get_skill(
            context,
            skill_name,
            snapshot=True,
            revision=binding['revision'],
        )
        if skill_data is None:
            raise ValueError(f'Skill "{skill_name}" pinned revision {binding["revision"]} is unavailable.')
        register_activated_skill(query, skill_data)
        restored.append(skill_name)
    return restored


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
    return should_prepare_python_env(package_root)


def wrap_skill_command_with_python_env(
    command: str,
    *,
    mount_path: str = '/workspace',
    state_path: str | None = None,
) -> str:
    return wrap_python_command_with_env(
        command,
        mount_path=mount_path,
        state_path=state_path,
    ).rstrip()
