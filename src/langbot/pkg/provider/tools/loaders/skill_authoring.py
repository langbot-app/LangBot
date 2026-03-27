from __future__ import annotations

import os
import typing

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool

from .. import loader

IMPORT_SKILL_FROM_DIRECTORY_TOOL_NAME = 'import_skill_from_directory'
RELOAD_SKILLS_TOOL_NAME = 'reload_skills'

AUTHORING_TOOL_NAMES = {
    IMPORT_SKILL_FROM_DIRECTORY_TOOL_NAME,
    RELOAD_SKILLS_TOOL_NAME,
}


class SkillAuthoringToolLoader(loader.ToolLoader):
    """Minimal system actions for filesystem-backed skills."""

    def __init__(self, ap):
        super().__init__(ap)
        self._tools: list[resource_tool.LLMTool] = []

    async def initialize(self):
        self._tools = [
            self._build_import_skill_from_directory_tool(),
            self._build_reload_skills_tool(),
        ]

    async def get_tools(self, bound_plugins: list[str] | None = None) -> list[resource_tool.LLMTool]:
        if not self._has_authoring_services():
            return []
        return list(self._tools)

    async def has_tool(self, name: str) -> bool:
        return self._has_authoring_services() and name in AUTHORING_TOOL_NAMES

    async def invoke_tool(self, name: str, parameters: dict, query) -> typing.Any:
        if name == IMPORT_SKILL_FROM_DIRECTORY_TOOL_NAME:
            return await self._invoke_import_skill_from_directory(parameters)
        if name == RELOAD_SKILLS_TOOL_NAME:
            return await self._invoke_reload_skills()
        raise ValueError(f'Unknown skill authoring tool: {name}')

    async def shutdown(self):
        pass

    def _has_authoring_services(self) -> bool:
        return getattr(self.ap, 'skill_service', None) is not None

    async def _invoke_reload_skills(self) -> typing.Any:
        await self.ap.skill_service.reload_skills()
        skills = await self.ap.skill_service.list_skills()
        return {
            'reloaded': True,
            'skill_names': [skill['name'] for skill in skills],
            'count': len(skills),
        }

    async def _invoke_import_skill_from_directory(self, parameters: dict) -> typing.Any:
        sandbox_path = str(parameters.get('path', '') or '').strip()
        if not sandbox_path:
            raise ValueError('path is required')

        host_path = self._resolve_workspace_directory(sandbox_path)
        scanned = self.ap.skill_service.scan_directory(host_path)
        created = await self.ap.skill_service.create_skill(
            {
                'name': str(parameters.get('name') or scanned['name']).strip(),
                'display_name': str(parameters.get('display_name') or scanned.get('display_name', '')).strip(),
                'description': str(parameters.get('description') or scanned.get('description', '')).strip(),
                'instructions': str(parameters.get('instructions') or scanned.get('instructions', '')),
                'package_root': host_path,
                'auto_activate': parameters.get('auto_activate', scanned.get('auto_activate', True)),
            }
        )
        return {
            'imported': True,
            'source_path': sandbox_path,
            'skill': created,
        }

    def _resolve_workspace_directory(self, sandbox_path: str) -> str:
        box_service = getattr(self.ap, 'box_service', None)
        workspace_root = getattr(box_service, 'default_host_workspace', None)
        if not workspace_root:
            raise ValueError('No default host workspace configured for importing skills')

        normalized_path = str(sandbox_path).strip() or '/workspace'
        if not normalized_path.startswith('/workspace'):
            raise ValueError('path must be under /workspace')

        relative = normalized_path[len('/workspace') :].lstrip('/')
        host_root = os.path.realpath(workspace_root)
        host_path = os.path.realpath(os.path.join(host_root, relative))
        if not (host_path == host_root or host_path.startswith(host_root + os.sep)):
            raise ValueError('path escapes the workspace boundary')
        if not os.path.isdir(host_path):
            raise ValueError(f'Directory does not exist: {sandbox_path}')
        return host_path

    def _build_import_skill_from_directory_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=IMPORT_SKILL_FROM_DIRECTORY_TOOL_NAME,
            human_desc='Import skill from workspace directory',
            description=(
                'Import a skill package from a directory under /workspace into the managed skills store. '
                'Use this after cloning or preparing a skill repository in the default workspace. '
                'If the source directory is already under the managed skills root, it will be registered in place instead of copied again.'
            ),
            parameters={
                'type': 'object',
                'properties': {
                    'path': {
                        'type': 'string',
                        'description': 'Directory path under /workspace that contains a skill package or a nested SKILL.md.',
                    },
                    'name': {
                        'type': 'string',
                        'description': 'Optional skill name override. Defaults to the scanned skill name.',
                    },
                    'display_name': {
                        'type': 'string',
                        'description': 'Optional display name override.',
                    },
                    'description': {
                        'type': 'string',
                        'description': 'Optional description override.',
                    },
                    'instructions': {
                        'type': 'string',
                        'description': 'Optional instructions override.',
                    },
                    'auto_activate': {
                        'type': 'boolean',
                        'description': 'Optional auto_activate override.',
                    },
                },
                'required': ['path'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_reload_skills_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=RELOAD_SKILLS_TOOL_NAME,
            human_desc='Reload filesystem skills',
            description=(
                'Reload skills from the filesystem after using the standard exec/read/write/edit tools '
                'to create, rename, or modify skill packages under the managed skills directory.'
            ),
            parameters={
                'type': 'object',
                'properties': {},
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )
