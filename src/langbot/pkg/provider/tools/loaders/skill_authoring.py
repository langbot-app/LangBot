from __future__ import annotations

import os
import typing

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool

from .. import loader

# Skill authoring needs a managed abstraction above the generic box tools.
# Pure prompt skills are just metadata plus SKILL.md instructions, so creating
# or updating them should not require /workspace mounts, shell access, or box
# to be enabled at all. These higher-level tools let local agents manage skills
# directly through SkillService, while import_skill_from_directory remains the
# path for file-based skills that actually need scripts or assets from box.

CREATE_SKILL_TOOL_NAME = 'create_skill'
LIST_SKILLS_TOOL_NAME = 'list_skills'
GET_SKILL_TOOL_NAME = 'get_skill'
UPDATE_SKILL_TOOL_NAME = 'update_skill'
DELETE_SKILL_TOOL_NAME = 'delete_skill'
IMPORT_SKILL_FROM_DIRECTORY_TOOL_NAME = 'import_skill_from_directory'
RELOAD_SKILLS_TOOL_NAME = 'reload_skills'

AUTHORING_TOOL_NAMES = {
    CREATE_SKILL_TOOL_NAME,
    LIST_SKILLS_TOOL_NAME,
    GET_SKILL_TOOL_NAME,
    UPDATE_SKILL_TOOL_NAME,
    DELETE_SKILL_TOOL_NAME,
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
            self._build_create_skill_tool(),
            self._build_list_skills_tool(),
            self._build_get_skill_tool(),
            self._build_update_skill_tool(),
            self._build_delete_skill_tool(),
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
        if name == CREATE_SKILL_TOOL_NAME:
            return await self._invoke_create_skill(parameters)
        if name == LIST_SKILLS_TOOL_NAME:
            return await self._invoke_list_skills()
        if name == GET_SKILL_TOOL_NAME:
            return await self._invoke_get_skill(parameters)
        if name == UPDATE_SKILL_TOOL_NAME:
            return await self._invoke_update_skill(parameters)
        if name == DELETE_SKILL_TOOL_NAME:
            return await self._invoke_delete_skill(parameters)
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

    async def _invoke_create_skill(self, parameters: dict) -> typing.Any:
        name = str(parameters.get('name', '') or '').strip()
        instructions = str(parameters.get('instructions', '') or '')
        if not name:
            raise ValueError('name is required')
        if not instructions.strip():
            raise ValueError('instructions is required')

        created = await self.ap.skill_service.create_skill(
            {
                'name': name,
                'display_name': str(parameters.get('display_name', '') or '').strip(),
                'description': str(parameters.get('description', '') or '').strip(),
                'instructions': instructions,
            }
        )
        return {
            'created': True,
            'skill': created,
        }

    async def _invoke_list_skills(self) -> typing.Any:
        skills = await self.ap.skill_service.list_skills()
        return {
            'skills': skills,
            'skill_names': [skill['name'] for skill in skills],
            'count': len(skills),
        }

    async def _invoke_get_skill(self, parameters: dict) -> typing.Any:
        name = str(parameters.get('name', '') or '').strip()
        if not name:
            raise ValueError('name is required')

        skill = await self.ap.skill_service.get_skill(name)
        if not skill:
            raise ValueError(f'Skill "{name}" not found')
        return {'skill': skill}

    async def _invoke_update_skill(self, parameters: dict) -> typing.Any:
        name = str(parameters.get('name', '') or '').strip()
        if not name:
            raise ValueError('name is required')

        data = {'name': name}
        for field in ('display_name', 'description', 'instructions'):
            if field in parameters:
                data[field] = parameters[field]

        updated = await self.ap.skill_service.update_skill(name, data)
        return {
            'updated': True,
            'skill': updated,
        }

    async def _invoke_delete_skill(self, parameters: dict) -> typing.Any:
        name = str(parameters.get('name', '') or '').strip()
        if not name:
            raise ValueError('name is required')

        await self.ap.skill_service.delete_skill(name)
        return {
            'deleted': True,
            'skill_name': name,
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

    def _build_create_skill_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=CREATE_SKILL_TOOL_NAME,
            human_desc='Create a managed skill',
            description=(
                'Create a new managed skill directly in the skills store without using /workspace. '
                'Use this for prompt-only skills or simple skills whose main content is the SKILL.md instructions. '
                'Pure prompt skills should not depend on box or a workspace directory just to be created or edited later.'
            ),
            parameters={
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'description': 'Skill name. Use lowercase letters, numbers, hyphens, or underscores.',
                    },
                    'display_name': {
                        'type': 'string',
                        'description': 'Optional human-friendly display name.',
                    },
                    'description': {
                        'type': 'string',
                        'description': 'Optional concise description of what the skill does and when to use it.',
                    },
                    'instructions': {
                        'type': 'string',
                        'description': 'The SKILL.md body instructions for the new skill.',
                    },
                },
                'required': ['name', 'instructions'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_list_skills_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=LIST_SKILLS_TOOL_NAME,
            human_desc='List managed skills',
            description='List all managed skills so you can inspect what already exists before creating, updating, or deleting one.',
            parameters={
                'type': 'object',
                'properties': {},
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_get_skill_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=GET_SKILL_TOOL_NAME,
            human_desc='Get a managed skill',
            description='Fetch one managed skill by name, including its current metadata and instructions, without relying on /workspace or skill activation.',
            parameters={
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'description': 'Existing skill name to fetch.',
                    },
                },
                'required': ['name'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_update_skill_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=UPDATE_SKILL_TOOL_NAME,
            human_desc='Update a managed skill',
            description=(
                'Update an existing managed skill directly in the skills store without using /workspace. '
                'Use this for prompt-only skills or for metadata and instruction changes to an existing skill. '
                'Pure prompt skills should remain editable through managed skill tools instead of depending on box.'
            ),
            parameters={
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'description': 'Existing skill name to update.',
                    },
                    'display_name': {
                        'type': 'string',
                        'description': 'Optional new human-friendly display name.',
                    },
                    'description': {
                        'type': 'string',
                        'description': 'Optional new concise description.',
                    },
                    'instructions': {
                        'type': 'string',
                        'description': 'Optional replacement SKILL.md body instructions.',
                    },
                },
                'required': ['name'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_delete_skill_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=DELETE_SKILL_TOOL_NAME,
            human_desc='Delete a managed skill',
            description='Delete an existing managed skill by name from the managed skills store.',
            parameters={
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'description': 'Existing skill name to delete.',
                    },
                },
                'required': ['name'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_import_skill_from_directory_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=IMPORT_SKILL_FROM_DIRECTORY_TOOL_NAME,
            human_desc='Import skill from workspace directory',
            description=(
                'Import a skill package from a directory under /workspace into the managed skills store. '
                'Use this after cloning or preparing a skill repository in the default workspace. '
                'This is for file-based skills that actually need scripts, assets, or extra files. '
                'Pure prompt skills should use create_skill or update_skill instead of depending on box. '
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
