from __future__ import annotations

import os
import typing

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool

from .. import loader
from ....api.http.context import ExecutionContext

# Align with Claude Code's Skill tool design:
# - activate: Activate a skill via Tool Call, returns SKILL.md content
# - register_skill: Register a skill from sandbox directory to data/skills/
# - This protects KV Cache and follows industry standard

ACTIVATE_SKILL_TOOL_NAME = 'activate'
LIST_SKILL_RESOURCES_TOOL_NAME = 'list_skill_resources'
READ_SKILL_RESOURCE_TOOL_NAME = 'read_skill_resource'
REGISTER_SKILL_TOOL_NAME = 'register_skill'

READ_ONLY_SKILL_TOOL_NAMES = {
    ACTIVATE_SKILL_TOOL_NAME,
    LIST_SKILL_RESOURCES_TOOL_NAME,
    READ_SKILL_RESOURCE_TOOL_NAME,
}
SANDBOX_SKILL_TOOL_NAMES = {
    REGISTER_SKILL_TOOL_NAME,
}
SKILL_TOOL_NAMES = READ_ONLY_SKILL_TOOL_NAMES | SANDBOX_SKILL_TOOL_NAMES
_SKILL_EXECUTION_AVAILABLE_KEY = '_skill_execution_available'
_SKILL_RESOURCE_BYTES_READ_KEY = '_skill_resource_bytes_read'
_MAX_SKILL_RESOURCE_FILE_BYTES = 256 * 1024
_MAX_SKILL_RESOURCE_RUN_BYTES = 1024 * 1024


class SkillToolLoader(loader.ToolLoader):
    """Skill tools aligned with Claude Code's design."""

    def __init__(self, ap):
        super().__init__(ap)
        self._read_only_tools: list[resource_tool.LLMTool] = []
        self._sandbox_tools: list[resource_tool.LLMTool] = []

    async def initialize(self):
        if self._is_available():
            self._read_only_tools = [
                self._build_activate_skill_tool(),
                self._build_list_skill_resources_tool(),
                self._build_read_skill_resource_tool(),
            ]
            self._sandbox_tools = [self._build_register_skill_tool()]
        else:
            self.ap.logger.info('Skill tools are unavailable because the Core SkillRepository is not initialized.')

    async def get_tools(
        self,
        bound_plugins: list[str] | None = None,
        *,
        sandbox_available: bool | None = None,
    ) -> list[resource_tool.LLMTool]:
        if not self._is_available():
            return []
        if not self._read_only_tools:
            await self.initialize()
        tools = list(self._read_only_tools)
        if sandbox_available:
            tools.extend(self._sandbox_tools)
        return tools

    async def get_tool(self, name: str, *, sandbox_available: bool | None = None):
        for tool in await self.get_tools(sandbox_available=sandbox_available):
            if tool.name == name:
                return tool
        return None

    async def has_tool(self, name: str, *, sandbox_available: bool | None = None) -> bool:
        if not self._is_available() or name not in SKILL_TOOL_NAMES:
            return False
        return name in READ_ONLY_SKILL_TOOL_NAMES or bool(sandbox_available)

    @staticmethod
    def is_sandbox_tool(name: str) -> bool:
        return name in SANDBOX_SKILL_TOOL_NAMES

    @staticmethod
    def recognizes_tool(name: str) -> bool:
        return name in SKILL_TOOL_NAMES

    def _is_available(self) -> bool:
        return self._has_skill_manager() and getattr(self.ap, 'skill_repository', None) is not None

    async def invoke_tool(self, name: str, parameters: dict, query) -> typing.Any:
        if name == ACTIVATE_SKILL_TOOL_NAME:
            return await self._invoke_activate_skill(parameters, query)
        if name == LIST_SKILL_RESOURCES_TOOL_NAME:
            return await self._invoke_list_skill_resources(parameters, query)
        if name == READ_SKILL_RESOURCE_TOOL_NAME:
            return await self._invoke_read_skill_resource(parameters, query)
        if name == REGISTER_SKILL_TOOL_NAME:
            require_sandbox = getattr(
                getattr(self.ap, 'box_service', None),
                'require_workspace_sandbox',
                None,
            )
            if not callable(require_sandbox):
                return self._sandbox_unavailable_result(name)
            await require_sandbox(self._execution_context(query))
            return await self._invoke_register_skill(parameters, query)
        raise ValueError(f'Unknown skill tool: {name}')

    @staticmethod
    def _execution_context(query) -> ExecutionContext:
        attached_context = getattr(query, '_execution_context', None)
        if isinstance(attached_context, ExecutionContext):
            return attached_context
        return ExecutionContext(
            instance_uuid=str(getattr(query, 'instance_uuid', '') or ''),
            workspace_uuid=str(getattr(query, 'workspace_uuid', '') or ''),
            placement_generation=getattr(query, 'placement_generation', 0) or 0,
            bot_uuid=getattr(query, 'bot_uuid', None),
            pipeline_uuid=getattr(query, 'pipeline_uuid', None),
            query_uuid=getattr(query, 'query_uuid', None),
            entitlement_revision=getattr(query, 'entitlement_revision', 0),
        )

    async def shutdown(self):
        pass

    def _has_skill_manager(self) -> bool:
        return getattr(self.ap, 'skill_mgr', None) is not None

    @staticmethod
    def _sandbox_unavailable_result(name: str) -> dict:
        return {
            'ok': False,
            'code': 'sandbox_unavailable',
            'tool': name,
            'message': 'This operation requires Box execution, but Box is not configured or available.',
        }

    async def _execution_available(self, query) -> bool:
        variables = getattr(query, 'variables', None)
        if isinstance(variables, dict) and _SKILL_EXECUTION_AVAILABLE_KEY in variables:
            return bool(variables[_SKILL_EXECUTION_AVAILABLE_KEY])
        checker = getattr(getattr(self.ap, 'box_service', None), 'is_workspace_sandbox_available', None)
        if not callable(checker):
            return False
        try:
            return bool(await checker(self._execution_context(query)))
        except Exception:
            return False

    async def _invoke_activate_skill(self, parameters: dict, query) -> typing.Any:
        """Activate a skill and return SKILL.md content via Tool Result."""
        skill_name = str(parameters.get('skill_name', '') or '').strip()
        if not skill_name:
            raise ValueError('skill_name is required')

        from . import skill as skill_loader

        visible_skill = skill_loader.get_visible_skill(self.ap, query, skill_name)
        if visible_skill is None:
            visible_skills = skill_loader.get_visible_skills(self.ap, query)
            available_names = ', '.join(sorted(visible_skills.keys())) or 'none'
            raise ValueError(f'Skill "{skill_name}" not found. Available skills: {available_names}')

        skill_data = await self.ap.skill_repository.get_skill(
            self._execution_context(query),
            skill_name,
            snapshot=True,
        )
        if skill_data is None:
            raise ValueError(f'Skill "{skill_name}" is no longer available; reload the skill catalog.')

        skill_loader.register_activated_skill(query, skill_data)

        instructions = skill_data.get('instructions', '')
        revision = str(skill_data.get('revision', '') or '')
        execution_available = await self._execution_available(query)
        mount_path = skill_loader.get_virtual_skill_mount_path(skill_name) if execution_available else None

        result_content = f'<command-message>The "{skill_name}" skill is activated</command-message>\n'
        result_content += '<skill-activation>\n'
        result_content += f'<skill-name>{skill_name}</skill-name>\n'
        result_content += f'<revision>{revision}</revision>\n'
        result_content += '<resources-readable>true</resources-readable>\n'
        result_content += f'<execution-available>{str(execution_available).lower()}</execution-available>\n'
        result_content += f'\n## Instructions\n{instructions}\n'
        result_content += '\n## Runtime Context\n'
        result_content += '- Use `list_skill_resources` and `read_skill_resource` for read-only package resources.\n'
        if execution_available:
            result_content += (
                f'- Box execution is available; executable package files will be mounted at {mount_path}.\n'
            )
        else:
            result_content += (
                '- Box execution is unavailable. Do not attempt to run scripts or modify Workspace files.\n'
            )
        result_content += '</skill-activation>\n'

        return {
            'activated': True,
            'skill_name': skill_name,
            'mount_path': mount_path,
            'revision': revision,
            'capabilities': {
                'instructions_readable': True,
                'resources_readable': True,
                'execution_available': execution_available,
            },
            'activated_skill_names': skill_loader.get_activated_skill_names(query),
            'content': result_content,
        }

    @staticmethod
    def _activated_skill(parameters: dict, query) -> dict:
        from . import skill as skill_loader

        skill_name = str(parameters.get('skill_name', '') or '').strip()
        if not skill_name:
            raise ValueError('skill_name is required')
        skill_data = skill_loader.get_activated_skill(query, skill_name)
        if skill_data is None:
            raise ValueError(f'Skill "{skill_name}" must be activated before its resources can be read.')
        requested_revision = str(parameters.get('revision', '') or '').strip()
        activated_revision = str(skill_data.get('revision', '') or '').strip()
        if requested_revision and requested_revision != activated_revision:
            raise ValueError('revision must match the activated skill revision')
        return skill_data

    async def _invoke_list_skill_resources(self, parameters: dict, query) -> dict:
        skill_data = self._activated_skill(parameters, query)
        return await self.ap.skill_repository.list_skill_resources(
            self._execution_context(query),
            skill_data['name'],
            str(parameters.get('path', '.') or '.'),
            expected_revision=skill_data.get('revision'),
        )

    async def _invoke_read_skill_resource(self, parameters: dict, query) -> dict:
        skill_data = self._activated_skill(parameters, query)
        path = str(parameters.get('path', '') or '').strip()
        if not path:
            raise ValueError('path is required')
        result = await self.ap.skill_repository.read_skill_resource(
            self._execution_context(query),
            skill_data['name'],
            path,
            expected_revision=skill_data.get('revision'),
        )
        content = str(result.get('content', ''))
        size = len(content.encode('utf-8'))
        if size > _MAX_SKILL_RESOURCE_FILE_BYTES:
            raise ValueError('Skill resource exceeds the per-file read limit')
        variables = getattr(query, 'variables', None)
        if not isinstance(variables, dict):
            variables = {}
            query.variables = variables
        total = int(variables.get(_SKILL_RESOURCE_BYTES_READ_KEY, 0) or 0) + size
        if total > _MAX_SKILL_RESOURCE_RUN_BYTES:
            raise ValueError('Skill resource reads exceed the per-run limit')
        variables[_SKILL_RESOURCE_BYTES_READ_KEY] = total
        result['size'] = size
        return result

    async def _invoke_register_skill(self, parameters: dict, query) -> typing.Any:
        """Register a skill from sandbox directory to data/skills/."""
        sandbox_path = str(parameters.get('path', '') or '').strip()
        if not sandbox_path:
            raise ValueError('path is required')

        # Resolve sandbox path to host path
        execution_context = self._execution_context(query)
        host_path = self._resolve_workspace_directory(sandbox_path, execution_context)

        # Get or create skill service
        skill_service = getattr(self.ap, 'skill_service', None)
        if skill_service is None:
            raise ValueError('Skill service not available')

        # Scan and register the skill
        scanned = await skill_service.scan_directory_async(execution_context, host_path)

        # Override name if provided
        skill_name = str(parameters.get('name') or scanned['name']).strip()
        if not skill_name:
            raise ValueError('skill name is required')

        # Create the skill
        created = await skill_service.import_skill_directory(
            execution_context,
            host_path,
            {
                'name': skill_name,
                'display_name': str(parameters.get('display_name') or scanned.get('display_name', '')).strip(),
                'description': str(parameters.get('description') or scanned.get('description', '')).strip(),
                'instructions': str(parameters.get('instructions') or scanned.get('instructions', '')),
            },
        )

        return {
            'registered': True,
            'skill_name': skill_name,
            'source_path': sandbox_path,
            'skill': created,
        }

    def _resolve_workspace_directory(
        self,
        sandbox_path: str,
        execution_context: ExecutionContext,
    ) -> str:
        """Resolve sandbox path to host filesystem path."""
        box_service = getattr(self.ap, 'box_service', None)
        tenant_workspace = getattr(box_service, '_tenant_workspace', None)
        workspace_root = (
            tenant_workspace(execution_context)
            if callable(tenant_workspace)
            else getattr(box_service, 'default_workspace', None)
        )
        if not workspace_root:
            raise ValueError('No default workspace configured')

        normalized_path = str(sandbox_path).strip() or '/workspace'
        if not normalized_path.startswith('/workspace'):
            raise ValueError('path must be under /workspace')

        relative = normalized_path[len('/workspace') :].lstrip('/')
        host_root = os.path.realpath(workspace_root)
        host_path = os.path.realpath(os.path.join(host_root, relative))

        # Security check: ensure path doesn't escape workspace
        if not (host_path == host_root or host_path.startswith(host_root + os.sep)):
            raise ValueError('path escapes the workspace boundary')

        if getattr(box_service, 'available', False):
            return host_path

        if not os.path.isdir(host_path):
            raise ValueError(f'Directory does not exist: {sandbox_path}')

        return host_path

    def _build_activate_skill_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=ACTIVATE_SKILL_TOOL_NAME,
            human_desc='Activate a skill',
            description='Activate a pipeline-visible skill by name and return its instructions as a tool result.',
            parameters={
                'type': 'object',
                'properties': {
                    'skill_name': {
                        'type': 'string',
                        'description': 'The skill name to activate.',
                    },
                },
                'required': ['skill_name'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_list_skill_resources_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=LIST_SKILL_RESOURCES_TOOL_NAME,
            human_desc='List activated skill resources',
            description='List read-only files in an activated skill package without starting a sandbox.',
            parameters={
                'type': 'object',
                'properties': {
                    'skill_name': {'type': 'string', 'description': 'The activated skill name.'},
                    'path': {'type': 'string', 'description': 'Relative directory path. Defaults to the package root.'},
                    'revision': {'type': 'string', 'description': 'Optional revision returned by activate.'},
                },
                'required': ['skill_name'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_read_skill_resource_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=READ_SKILL_RESOURCE_TOOL_NAME,
            human_desc='Read an activated skill resource',
            description='Read a UTF-8 text resource from an activated skill package without starting a sandbox.',
            parameters={
                'type': 'object',
                'properties': {
                    'skill_name': {'type': 'string', 'description': 'The activated skill name.'},
                    'path': {'type': 'string', 'description': 'File path relative to the skill package root.'},
                    'revision': {'type': 'string', 'description': 'Optional revision returned by activate.'},
                },
                'required': ['skill_name', 'path'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_register_skill_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=REGISTER_SKILL_TOOL_NAME,
            human_desc='Register a skill from sandbox',
            description=(
                "Register a skill package from a directory under /workspace into LangBot's skill store. "
                'Use this after creating or preparing a skill in the sandbox with exec/read/write/edit. '
                'The directory must contain a SKILL.md file. '
                'After registration, the skill can be activated with the activate tool.'
            ),
            parameters={
                'type': 'object',
                'properties': {
                    'path': {
                        'type': 'string',
                        'description': 'Directory path under /workspace containing the skill package (must have SKILL.md)',
                    },
                    'name': {
                        'type': 'string',
                        'description': 'Optional skill name override. Defaults to the name in SKILL.md or directory name.',
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
