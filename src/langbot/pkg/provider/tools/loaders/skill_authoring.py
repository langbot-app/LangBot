from __future__ import annotations

import typing

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
from langbot_plugin.api.entities.events import pipeline_query

from .. import loader

LIST_SKILLS_TOOL_NAME = 'list_skills'
GET_SKILL_TOOL_NAME = 'get_skill'
CREATE_SKILL_TOOL_NAME = 'create_skill'
UPDATE_SKILL_TOOL_NAME = 'update_skill'
PREVIEW_SKILL_TOOL_NAME = 'preview_skill'
SKILL_LIST_FILES_TOOL_NAME = 'skill_list_files'
SKILL_READ_FILE_TOOL_NAME = 'skill_read_file'
SKILL_WRITE_FILE_TOOL_NAME = 'skill_write_file'
GET_PIPELINE_SKILLS_TOOL_NAME = 'get_pipeline_skills'
UPDATE_PIPELINE_SKILLS_TOOL_NAME = 'update_pipeline_skills'

AUTHORING_TOOL_NAMES = {
    LIST_SKILLS_TOOL_NAME,
    GET_SKILL_TOOL_NAME,
    CREATE_SKILL_TOOL_NAME,
    UPDATE_SKILL_TOOL_NAME,
    PREVIEW_SKILL_TOOL_NAME,
    SKILL_LIST_FILES_TOOL_NAME,
    SKILL_READ_FILE_TOOL_NAME,
    SKILL_WRITE_FILE_TOOL_NAME,
    GET_PIPELINE_SKILLS_TOOL_NAME,
    UPDATE_PIPELINE_SKILLS_TOOL_NAME,
}

SKILL_SUMMARY_FIELDS = (
    'name',
    'display_name',
    'description',
    'auto_activate',
    'updated_at',
)

SKILL_DETAIL_FIELDS = (
    'name',
    'display_name',
    'description',
    'instructions',
    'package_root',
    'entry_file',
    'auto_activate',
    'created_at',
    'updated_at',
)


class SkillAuthoringToolLoader(loader.ToolLoader):
    """Built-in tools for creating, updating, and binding skills."""

    def __init__(self, ap):
        super().__init__(ap)
        self._tools: list[resource_tool.LLMTool] = []

    async def initialize(self):
        self._tools = [
            self._build_list_skills_tool(),
            self._build_get_skill_tool(),
            self._build_create_skill_tool(),
            self._build_update_skill_tool(),
            self._build_preview_skill_tool(),
            self._build_skill_list_files_tool(),
            self._build_skill_read_file_tool(),
            self._build_skill_write_file_tool(),
            self._build_get_pipeline_skills_tool(),
            self._build_update_pipeline_skills_tool(),
        ]

    async def get_tools(self, bound_plugins: list[str] | None = None) -> list[resource_tool.LLMTool]:
        if not self._has_authoring_services():
            return []
        return self._tools

    async def has_tool(self, name: str) -> bool:
        return self._has_authoring_services() and name in AUTHORING_TOOL_NAMES

    async def invoke_tool(self, name: str, parameters: dict, query: pipeline_query.Query) -> typing.Any:
        if name == LIST_SKILLS_TOOL_NAME:
            return await self._invoke_list_skills(parameters)
        if name == GET_SKILL_TOOL_NAME:
            return await self._invoke_get_skill(parameters)
        if name == CREATE_SKILL_TOOL_NAME:
            return await self._invoke_create_skill(parameters)
        if name == UPDATE_SKILL_TOOL_NAME:
            return await self._invoke_update_skill(parameters)
        if name == PREVIEW_SKILL_TOOL_NAME:
            return await self._invoke_preview_skill(parameters)
        if name == SKILL_LIST_FILES_TOOL_NAME:
            return await self._invoke_skill_list_files(parameters)
        if name == SKILL_READ_FILE_TOOL_NAME:
            return await self._invoke_skill_read_file(parameters)
        if name == SKILL_WRITE_FILE_TOOL_NAME:
            return await self._invoke_skill_write_file(parameters)
        if name == GET_PIPELINE_SKILLS_TOOL_NAME:
            return await self._invoke_get_pipeline_skills(parameters, query)
        if name == UPDATE_PIPELINE_SKILLS_TOOL_NAME:
            return await self._invoke_update_pipeline_skills(parameters, query)
        raise ValueError(f'Unknown skill authoring tool: {name}')

    async def shutdown(self):
        pass

    def _has_authoring_services(self) -> bool:
        return (
            getattr(self.ap, 'skill_service', None) is not None
            and getattr(self.ap, 'pipeline_service', None) is not None
        )

    def _serialize_skill_summary(self, skill_data: dict) -> dict:
        return {field: skill_data.get(field) for field in SKILL_SUMMARY_FIELDS if field in skill_data}

    def _serialize_skill_detail(self, skill_data: dict) -> dict:
        return {field: skill_data.get(field) for field in SKILL_DETAIL_FIELDS if field in skill_data}

    async def _resolve_skill(self, parameters: dict) -> dict:
        skill_name = str(parameters.get('skill_name', '')).strip()
        if not skill_name:
            raise ValueError('skill_name is required')

        skill = await self.ap.skill_service.get_skill(skill_name)
        if skill:
            return skill
        raise ValueError(f'Skill "{skill_name}" not found')

    async def _resolve_pipeline(self, parameters: dict, query: pipeline_query.Query) -> dict:
        pipeline_uuid = (
            str(parameters.get('pipeline_uuid', '')).strip() or str(getattr(query, 'pipeline_uuid', '') or '').strip()
        )
        if not pipeline_uuid:
            raise ValueError('pipeline_uuid is required')

        pipeline = await self.ap.pipeline_service.get_pipeline(pipeline_uuid)
        if not pipeline:
            raise ValueError(f'Pipeline {pipeline_uuid} not found')
        return pipeline

    async def _invoke_list_skills(self, parameters: dict) -> typing.Any:
        include_instructions = bool(parameters.get('include_instructions', False))
        skills = await self.ap.skill_service.list_skills()
        serializer = self._serialize_skill_detail if include_instructions else self._serialize_skill_summary
        return {'skills': [serializer(skill) for skill in skills]}

    async def _invoke_get_skill(self, parameters: dict) -> typing.Any:
        skill = await self._resolve_skill(parameters)
        return {'skill': self._serialize_skill_detail(skill)}

    async def _invoke_create_skill(self, parameters: dict) -> typing.Any:
        skill_data = {
            'name': parameters.get('name'),
            'display_name': parameters.get('display_name', ''),
            'description': parameters.get('description'),
            'instructions': parameters.get('instructions'),
            'package_root': parameters.get('package_root', ''),
            'auto_activate': parameters.get('auto_activate', True),
        }
        created = await self.ap.skill_service.create_skill(skill_data)
        return {'skill': self._serialize_skill_detail(created)}

    async def _invoke_update_skill(self, parameters: dict) -> typing.Any:
        skill = await self._resolve_skill(parameters)
        updates = parameters.get('updates')
        if not isinstance(updates, dict) or not updates:
            raise ValueError('updates is required')

        updated = await self.ap.skill_service.update_skill(skill['name'], updates)
        return {'skill': self._serialize_skill_detail(updated)}

    async def _invoke_preview_skill(self, parameters: dict) -> typing.Any:
        skill = await self._resolve_skill(parameters)
        runtime_data = self.ap.skill_mgr.get_skill_runtime_data(skill['name'])
        if not runtime_data:
            raise ValueError(f'Skill "{skill["name"]}" not found in manager')
        return {'instructions': runtime_data['instructions']}

    async def _invoke_skill_list_files(self, parameters: dict) -> typing.Any:
        skill = await self._resolve_skill(parameters)
        return await self.ap.skill_service.list_skill_files(
            skill['name'],
            path=str(parameters.get('path', '.') or '.'),
            include_hidden=bool(parameters.get('include_hidden', False)),
            max_entries=int(parameters.get('max_entries', 200)),
        )

    async def _invoke_skill_read_file(self, parameters: dict) -> typing.Any:
        skill = await self._resolve_skill(parameters)
        path = str(parameters.get('path', '')).strip()
        if not path:
            raise ValueError('path is required')
        return await self.ap.skill_service.read_skill_file(skill['name'], path)

    async def _invoke_skill_write_file(self, parameters: dict) -> typing.Any:
        skill = await self._resolve_skill(parameters)
        path = str(parameters.get('path', '')).strip()
        if not path:
            raise ValueError('path is required')
        return await self.ap.skill_service.write_skill_file(
            skill['name'],
            path,
            str(parameters.get('content', '')),
        )

    async def _invoke_get_pipeline_skills(self, parameters: dict, query: pipeline_query.Query) -> typing.Any:
        pipeline = await self._resolve_pipeline(parameters, query)
        extensions_prefs = pipeline.get('extensions_preferences', {})
        available_skills = await self.ap.skill_service.list_skills()
        bound_skill_names = list(extensions_prefs.get('skills', []))
        return {
            'pipeline_uuid': pipeline['uuid'],
            'enable_all_skills': extensions_prefs.get('enable_all_skills', True),
            'bound_skill_names': bound_skill_names,
            'available_skills': [self._serialize_skill_summary(skill) for skill in available_skills],
        }

    async def _invoke_update_pipeline_skills(self, parameters: dict, query: pipeline_query.Query) -> typing.Any:
        pipeline = await self._resolve_pipeline(parameters, query)
        extensions_prefs = pipeline.get('extensions_preferences', {})

        explicit_enable_all = parameters.get('enable_all_skills')
        enable_all_skills = (
            explicit_enable_all
            if isinstance(explicit_enable_all, bool)
            else extensions_prefs.get('enable_all_skills', True)
        )

        resolved_skill_names: list[str] | None = None
        provided_skill_names = parameters.get('bound_skill_names')

        if provided_skill_names is not None:
            if not isinstance(provided_skill_names, list):
                raise ValueError('bound_skill_names must be a list')
            resolved_skill_names = []
            for skill_name in provided_skill_names:
                skill = await self.ap.skill_service.get_skill(str(skill_name))
                if not skill:
                    raise ValueError(f'Skill "{skill_name}" not found')
                if skill['name'] not in resolved_skill_names:
                    resolved_skill_names.append(skill['name'])

        await self.ap.pipeline_service.update_pipeline_extensions(
            pipeline_uuid=pipeline['uuid'],
            bound_plugins=list(extensions_prefs.get('plugins', [])),
            bound_mcp_servers=list(extensions_prefs.get('mcp_servers', [])),
            enable_all_plugins=extensions_prefs.get('enable_all_plugins', True),
            enable_all_mcp_servers=extensions_prefs.get('enable_all_mcp_servers', True),
            bound_skills=resolved_skill_names,
            enable_all_skills=enable_all_skills,
        )

        return await self._invoke_get_pipeline_skills({'pipeline_uuid': pipeline['uuid']}, query)

    def _build_list_skills_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=LIST_SKILLS_TOOL_NAME,
            human_desc='List registered skills',
            description='List registered skills. Prefer include_instructions=false unless you need full skill content.',
            parameters={
                'type': 'object',
                'properties': {
                    'include_instructions': {
                        'type': 'boolean',
                        'description': 'Whether to include full instructions for each skill.',
                        'default': False,
                    },
                },
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_get_skill_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=GET_SKILL_TOOL_NAME,
            human_desc='Get one skill',
            description='Get one skill by name, including its current instructions and metadata.',
            parameters={
                'type': 'object',
                'properties': {
                    'skill_name': {
                        'type': 'string',
                        'description': 'Skill name.',
                    },
                },
                'required': ['skill_name'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_create_skill_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=CREATE_SKILL_TOOL_NAME,
            human_desc='Create a skill',
            description='Create a new skill package under data/skills.',
            parameters={
                'type': 'object',
                'properties': {
                    'name': {'type': 'string', 'description': 'Stable skill slug.'},
                    'display_name': {'type': 'string', 'description': 'Human-readable skill title.'},
                    'description': {'type': 'string', 'description': 'Short description used for skill selection.'},
                    'instructions': {'type': 'string', 'description': 'Full SKILL.md body content.'},
                    'package_root': {'type': 'string', 'description': 'Optional existing skill directory to import.'},
                    'auto_activate': {'type': 'boolean', 'default': True},
                },
                'required': ['name', 'description', 'instructions'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_update_skill_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=UPDATE_SKILL_TOOL_NAME,
            human_desc='Update a skill',
            description='Update an existing skill by name. The updates object is a partial patch.',
            parameters={
                'type': 'object',
                'properties': {
                    'skill_name': {'type': 'string', 'description': 'Skill name.'},
                    'updates': {
                        'type': 'object',
                        'properties': {
                            'display_name': {'type': 'string'},
                            'description': {'type': 'string'},
                            'instructions': {'type': 'string'},
                            'package_root': {'type': 'string'},
                            'auto_activate': {'type': 'boolean'},
                        },
                        'additionalProperties': False,
                    },
                },
                'required': ['skill_name', 'updates'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_preview_skill_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=PREVIEW_SKILL_TOOL_NAME,
            human_desc='Preview skill instructions',
            description='Preview the current instructions for a skill by name.',
            parameters={
                'type': 'object',
                'properties': {
                    'skill_name': {'type': 'string', 'description': 'Skill name.'},
                },
                'required': ['skill_name'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_skill_list_files_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=SKILL_LIST_FILES_TOOL_NAME,
            human_desc='List skill package files',
            description='List files and directories under a registered skill package root or a relative subdirectory.',
            parameters={
                'type': 'object',
                'properties': {
                    'skill_name': {'type': 'string', 'description': 'Skill name.'},
                    'path': {
                        'type': 'string',
                        'description': 'Relative directory path under the skill package root.',
                        'default': '.',
                    },
                    'include_hidden': {
                        'type': 'boolean',
                        'description': 'Whether to include dotfiles and dot-directories.',
                        'default': False,
                    },
                    'max_entries': {
                        'type': 'integer',
                        'description': 'Maximum number of entries to return.',
                        'minimum': 1,
                        'maximum': 1000,
                        'default': 200,
                    },
                },
                'required': ['skill_name'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_skill_read_file_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=SKILL_READ_FILE_TOOL_NAME,
            human_desc='Read a skill file',
            description='Read a UTF-8 text file from a registered skill package by relative path.',
            parameters={
                'type': 'object',
                'properties': {
                    'skill_name': {'type': 'string', 'description': 'Skill name.'},
                    'path': {'type': 'string', 'description': 'Relative file path under the skill package root.'},
                },
                'required': ['skill_name', 'path'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_skill_write_file_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=SKILL_WRITE_FILE_TOOL_NAME,
            human_desc='Write a skill file',
            description='Create or replace a UTF-8 text file under a registered skill package by relative path.',
            parameters={
                'type': 'object',
                'properties': {
                    'skill_name': {'type': 'string', 'description': 'Skill name.'},
                    'path': {'type': 'string', 'description': 'Relative file path under the skill package root.'},
                    'content': {'type': 'string', 'description': 'Full file content to write.'},
                },
                'required': ['skill_name', 'path', 'content'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_get_pipeline_skills_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=GET_PIPELINE_SKILLS_TOOL_NAME,
            human_desc='Get pipeline skill bindings',
            description='Get the current pipeline skill visibility settings. Defaults to the active pipeline when pipeline_uuid is omitted.',
            parameters={
                'type': 'object',
                'properties': {
                    'pipeline_uuid': {'type': 'string', 'description': 'Optional pipeline UUID.'},
                },
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_update_pipeline_skills_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=UPDATE_PIPELINE_SKILLS_TOOL_NAME,
            human_desc='Update pipeline skill bindings',
            description=(
                'Update the current pipeline skill visibility settings. '
                'Provided bound_skill_names replace the bound skill list; omit them to keep the existing list.'
            ),
            parameters={
                'type': 'object',
                'properties': {
                    'pipeline_uuid': {'type': 'string', 'description': 'Optional pipeline UUID.'},
                    'enable_all_skills': {
                        'type': 'boolean',
                        'description': 'Whether the pipeline can see all enabled skills.',
                    },
                    'bound_skill_names': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Replacement bound skill name list.',
                    },
                },
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )
