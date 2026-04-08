from __future__ import annotations

import json
import os

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
from langbot_plugin.api.entities.events import pipeline_query

from ....box.workspace import BoxWorkspaceSession
from .. import loader
from . import skill as skill_loader

EXEC_TOOL_NAME = 'exec'
READ_TOOL_NAME = 'read'
WRITE_TOOL_NAME = 'write'
EDIT_TOOL_NAME = 'edit'

_ALL_TOOL_NAMES = {EXEC_TOOL_NAME, READ_TOOL_NAME, WRITE_TOOL_NAME, EDIT_TOOL_NAME}


class NativeToolLoader(loader.ToolLoader):
    def __init__(self, ap):
        super().__init__(ap)
        self._tools: list[resource_tool.LLMTool] | None = None

    async def get_tools(self, bound_plugins: list[str] | None = None) -> list[resource_tool.LLMTool]:
        if not self._is_sandbox_available():
            return []
        if self._tools is None:
            self._tools = [
                self._build_exec_tool(),
                self._build_read_tool(),
                self._build_write_tool(),
                self._build_edit_tool(),
            ]
        return list(self._tools)

    async def has_tool(self, name: str) -> bool:
        return name in _ALL_TOOL_NAMES and self._is_sandbox_available()

    async def invoke_tool(self, name: str, parameters: dict, query: pipeline_query.Query):
        if name == EXEC_TOOL_NAME:
            self.ap.logger.info(
                'exec tool invoked: '
                f'query_id={query.query_id} '
                f'parameters={json.dumps(self._summarize_parameters(parameters), ensure_ascii=False)}'
            )
            return await self._invoke_exec(parameters, query)
        if name == READ_TOOL_NAME:
            return await self._invoke_read(parameters, query)
        if name == WRITE_TOOL_NAME:
            return await self._invoke_write(parameters, query)
        if name == EDIT_TOOL_NAME:
            return await self._invoke_edit(parameters, query)
        raise ValueError(f'未找到工具: {name}')

    async def shutdown(self):
        pass

    async def _invoke_exec(self, parameters: dict, query: pipeline_query.Query) -> dict:
        command = str(parameters['command'])
        workdir = str(parameters.get('workdir', '/workspace') or '/workspace')

        selected_skill, rewritten_workdir = skill_loader.resolve_virtual_skill_path(
            self.ap,
            query,
            workdir,
            include_visible=False,
            include_activated=True,
        )
        referenced_skill_names = skill_loader.find_referenced_skill_names(command)

        if selected_skill is None and referenced_skill_names:
            if len(referenced_skill_names) > 1:
                raise ValueError('exec can target at most one activated skill package per call.')
            selected_skill = skill_loader.get_activated_skill(query, referenced_skill_names[0])
            if selected_skill is None:
                raise ValueError(
                    f'Skill "{referenced_skill_names[0]}" must be activated before exec can run in its package.'
                )
            rewritten_workdir = '/workspace'

        if selected_skill is None:
            return await self.ap.box_service.execute_tool(parameters, query)

        selected_skill_name = str(selected_skill.get('name', '') or '')
        if referenced_skill_names and any(name != selected_skill_name for name in referenced_skill_names):
            raise ValueError('exec can reference files from only one activated skill package per call.')

        package_root = str(selected_skill.get('package_root', '') or '').strip()
        if not package_root:
            raise ValueError(f'Activated skill "{selected_skill_name}" has no package_root.')

        rewritten_command = skill_loader.rewrite_command_for_skill_mount(command, selected_skill_name)
        if skill_loader.should_prepare_skill_python_env(package_root):
            rewritten_command = skill_loader.wrap_skill_command_with_python_env(rewritten_command)

        workspace = BoxWorkspaceSession(
            self.ap.box_service,
            skill_loader.build_skill_session_id(selected_skill, query),
            host_path=package_root,
            host_path_mode='rw',
        )
        result = await workspace.execute_for_query(
            query,
            rewritten_command,
            workdir=rewritten_workdir,
            timeout_sec=parameters.get('timeout_sec'),
            env=parameters.get('env'),
        )
        self._refresh_skill_from_disk(selected_skill)
        return result

    def _resolve_host_path(
        self,
        query: pipeline_query.Query,
        sandbox_path: str,
        *,
        include_visible: bool,
        include_activated: bool,
    ) -> tuple[str, dict | None]:
        selected_skill, rewritten_path = skill_loader.resolve_virtual_skill_path(
            self.ap,
            query,
            sandbox_path,
            include_visible=include_visible,
            include_activated=include_activated,
        )

        box_service = self.ap.box_service
        host_root = (
            selected_skill.get('package_root') if selected_skill is not None else box_service.default_host_workspace
        )
        if not host_root:
            raise ValueError('No host workspace configured for file operations.')

        mount_path = '/workspace'
        if not rewritten_path.startswith(mount_path):
            raise ValueError(f'Path must be under {mount_path}.')

        relative = rewritten_path[len(mount_path) :].lstrip('/')
        host_path = os.path.realpath(os.path.join(host_root, relative))
        host_root = os.path.realpath(host_root)

        if not (host_path == host_root or host_path.startswith(host_root + os.sep)):
            raise ValueError('Path escapes the workspace boundary.')

        return host_path, selected_skill

    async def _invoke_read(self, parameters: dict, query: pipeline_query.Query) -> dict:
        path = parameters['path']
        self.ap.logger.info(f'read tool invoked: query_id={query.query_id} path={path}')
        host_path, _selected_skill = self._resolve_host_path(
            query,
            path,
            include_visible=True,
            include_activated=True,
        )
        if not os.path.exists(host_path):
            return {'ok': False, 'error': f'File not found: {path}'}
        if os.path.isdir(host_path):
            entries = os.listdir(host_path)
            return {'ok': True, 'content': '\n'.join(sorted(entries)), 'is_directory': True}
        with open(host_path, 'r', errors='replace') as f:
            content = f.read()
        return {'ok': True, 'content': content}

    async def _invoke_write(self, parameters: dict, query: pipeline_query.Query) -> dict:
        path = parameters['path']
        content = parameters['content']
        self.ap.logger.info(f'write tool invoked: query_id={query.query_id} path={path} length={len(content)}')
        host_path, selected_skill = self._resolve_host_path(
            query,
            path,
            include_visible=False,
            include_activated=True,
        )
        os.makedirs(os.path.dirname(host_path), exist_ok=True)
        with open(host_path, 'w', encoding='utf-8') as f:
            f.write(content)
        self._refresh_skill_from_disk(selected_skill)
        return {'ok': True, 'path': path}

    async def _invoke_edit(self, parameters: dict, query: pipeline_query.Query) -> dict:
        path = parameters['path']
        old_string = parameters['old_string']
        new_string = parameters['new_string']
        self.ap.logger.info(
            f'edit tool invoked: query_id={query.query_id} path={path} '
            f'old_len={len(old_string)} new_len={len(new_string)}'
        )
        host_path, selected_skill = self._resolve_host_path(
            query,
            path,
            include_visible=False,
            include_activated=True,
        )
        if not os.path.isfile(host_path):
            return {'ok': False, 'error': f'File not found: {path}'}
        with open(host_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        count = content.count(old_string)
        if count == 0:
            return {'ok': False, 'error': 'old_string not found in file.'}
        if count > 1:
            return {'ok': False, 'error': f'old_string matches {count} locations; provide a more unique string.'}
        new_content = content.replace(old_string, new_string, 1)
        with open(host_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        self._refresh_skill_from_disk(selected_skill)
        return {'ok': True, 'path': path}

    def _refresh_skill_from_disk(self, selected_skill: dict | None) -> None:
        if selected_skill is None:
            return

        skill_mgr = getattr(self.ap, 'skill_mgr', None)
        if skill_mgr is None:
            return

        refresh_skill = getattr(skill_mgr, 'refresh_skill_from_disk', None)
        if callable(refresh_skill):
            refresh_skill(selected_skill.get('name', ''))

    def _is_sandbox_available(self) -> bool:
        box_service = getattr(self.ap, 'box_service', None)
        return bool(getattr(box_service, 'available', False))

    def _build_exec_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=EXEC_TOOL_NAME,
            human_desc='Execute a command in an isolated environment',
            description=(
                'Run shell commands in an isolated execution environment. '
                'Use this tool for bash commands, Python execution, and exact calculations over '
                'user-provided data. Activated skill packages are addressable under '
                '/workspace/.skills/<skill-name>; when running inside one, set workdir to that path. '
                'To create a new skill package, prepare it under /workspace first, then use import_skill_from_directory.'
            ),
            parameters={
                'type': 'object',
                'properties': {
                    'command': {
                        'type': 'string',
                        'description': 'Shell command to execute.',
                    },
                    'workdir': {
                        'type': 'string',
                        'description': 'Working directory for the command. Defaults to /workspace.',
                        'default': '/workspace',
                    },
                    'timeout_sec': {
                        'type': 'integer',
                        'description': 'Execution timeout in seconds. Defaults to 30.',
                        'default': 30,
                        'minimum': 1,
                    },
                    'env': {
                        'type': 'object',
                        'description': 'Optional environment variables for the execution.',
                        'additionalProperties': {'type': 'string'},
                        'default': {},
                    },
                    'description': {
                        'type': 'string',
                        'description': 'Brief description of what this command does, for logging and audit.',
                    },
                },
                'required': ['command'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_read_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=READ_TOOL_NAME,
            human_desc='Read a file from the workspace',
            description=(
                'Read the contents of a file at the given path under /workspace. '
                'Visible skill packages can be inspected through /workspace/.skills/<skill-name>/... .'
            ),
            parameters={
                'type': 'object',
                'properties': {
                    'path': {
                        'type': 'string',
                        'description': 'Absolute path to the file (must be under /workspace).',
                    },
                },
                'required': ['path'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_write_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=WRITE_TOOL_NAME,
            human_desc='Write a file to the workspace',
            description=(
                'Create or overwrite a file at the given path under /workspace with the provided content. '
                'Activated skill packages can be modified through /workspace/.skills/<skill-name>/... . '
                'For new skills, write files under /workspace and then call import_skill_from_directory.'
            ),
            parameters={
                'type': 'object',
                'properties': {
                    'path': {
                        'type': 'string',
                        'description': 'Absolute path to the file (must be under /workspace).',
                    },
                    'content': {
                        'type': 'string',
                        'description': 'Content to write to the file.',
                    },
                },
                'required': ['path', 'content'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_edit_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=EDIT_TOOL_NAME,
            human_desc='Edit a file in the workspace',
            description=(
                'Perform an exact string replacement in a file under /workspace. '
                'The old_string must appear exactly once in the file. Activated skill packages '
                'can be edited through /workspace/.skills/<skill-name>/... . '
                'For new skills, edit files under /workspace and then call import_skill_from_directory.'
            ),
            parameters={
                'type': 'object',
                'properties': {
                    'path': {
                        'type': 'string',
                        'description': 'Absolute path to the file (must be under /workspace).',
                    },
                    'old_string': {
                        'type': 'string',
                        'description': 'The exact string to find and replace.',
                    },
                    'new_string': {
                        'type': 'string',
                        'description': 'The replacement string.',
                    },
                },
                'required': ['path', 'old_string', 'new_string'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _summarize_parameters(self, parameters: dict) -> dict:
        summary = dict(parameters)
        cmd = str(summary.get('command', '')).strip()
        if len(cmd) > 400:
            cmd = f'{cmd[:397]}...'
        summary['command'] = cmd

        env = summary.get('env')
        if isinstance(env, dict):
            summary['env_keys'] = sorted(str(key) for key in env.keys())
            del summary['env']

        return summary
