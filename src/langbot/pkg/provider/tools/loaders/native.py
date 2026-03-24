from __future__ import annotations

import json
import os

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
from langbot_plugin.api.entities.events import pipeline_query

from .. import loader

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
            return await self.ap.box_service.execute_tool(parameters, query)
        elif name == READ_TOOL_NAME:
            return await self._invoke_read(parameters, query)
        elif name == WRITE_TOOL_NAME:
            return await self._invoke_write(parameters, query)
        elif name == EDIT_TOOL_NAME:
            return await self._invoke_edit(parameters, query)
        else:
            raise ValueError(f'未找到工具: {name}')

    async def shutdown(self):
        pass

    # ── File tool implementations ────────────────────────────────────

    def _resolve_host_path(self, sandbox_path: str) -> str:
        """Map a sandbox /workspace path to the host filesystem path."""
        box_service = self.ap.box_service
        host_root = box_service.default_host_workspace
        if host_root is None:
            raise ValueError('No default host workspace configured for file operations.')

        mount_path = '/workspace'
        if not sandbox_path.startswith(mount_path):
            raise ValueError(f'Path must be under {mount_path}.')

        relative = sandbox_path[len(mount_path):].lstrip('/')
        host_path = os.path.realpath(os.path.join(host_root, relative))

        if not (host_path == host_root or host_path.startswith(host_root + os.sep)):
            raise ValueError('Path escapes the workspace boundary.')

        return host_path

    async def _invoke_read(self, parameters: dict, query: pipeline_query.Query) -> dict:
        path = parameters['path']
        self.ap.logger.info(f'read tool invoked: query_id={query.query_id} path={path}')
        host_path = self._resolve_host_path(path)
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
        host_path = self._resolve_host_path(path)
        os.makedirs(os.path.dirname(host_path), exist_ok=True)
        with open(host_path, 'w') as f:
            f.write(content)
        return {'ok': True, 'path': path}

    async def _invoke_edit(self, parameters: dict, query: pipeline_query.Query) -> dict:
        path = parameters['path']
        old_string = parameters['old_string']
        new_string = parameters['new_string']
        self.ap.logger.info(
            f'edit tool invoked: query_id={query.query_id} path={path} '
            f'old_len={len(old_string)} new_len={len(new_string)}'
        )
        host_path = self._resolve_host_path(path)
        if not os.path.isfile(host_path):
            return {'ok': False, 'error': f'File not found: {path}'}
        with open(host_path, 'r', errors='replace') as f:
            content = f.read()
        count = content.count(old_string)
        if count == 0:
            return {'ok': False, 'error': 'old_string not found in file.'}
        if count > 1:
            return {'ok': False, 'error': f'old_string matches {count} locations; provide a more unique string.'}
        new_content = content.replace(old_string, new_string, 1)
        with open(host_path, 'w') as f:
            f.write(new_content)
        return {'ok': True, 'path': path}

    # ── Internals ────────────────────────────────────────────────────

    def _is_sandbox_available(self) -> bool:
        box_service = getattr(self.ap, 'box_service', None)
        return bool(getattr(box_service, 'available', False))

    def _build_exec_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=EXEC_TOOL_NAME,
            human_desc='Execute a command in an isolated environment',
            description=(
                'Run shell commands in an isolated execution environment. '
                'Use this tool for bash commands, Python execution, and exact calculations '
                'over user-provided data.'
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
                        'description': (
                            'Working directory for the command. Defaults to /workspace.'
                        ),
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
            description='Read the contents of a file at the given path under /workspace.',
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
            description='Create or overwrite a file at the given path under /workspace with the provided content.',
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
                'The old_string must appear exactly once in the file.'
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
