from __future__ import annotations

import json

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
from langbot_plugin.api.entities.events import pipeline_query

from .. import loader


class NativeToolLoader(loader.ToolLoader):
    SANDBOX_EXEC_TOOL_NAME = 'sandbox_exec'

    async def get_tools(self, bound_plugins: list[str] | None = None) -> list[resource_tool.LLMTool]:
        return [self._build_sandbox_exec_tool()]

    async def has_tool(self, name: str) -> bool:
        return name == self.SANDBOX_EXEC_TOOL_NAME

    async def invoke_tool(self, name: str, parameters: dict, query: pipeline_query.Query):
        if name != self.SANDBOX_EXEC_TOOL_NAME:
            raise ValueError(f'未找到工具: {name}')
        self.ap.logger.info(
            'sandbox_exec tool invoked: '
            f'query_id={query.query_id} '
            f'parameters={json.dumps(self._summarize_parameters(parameters), ensure_ascii=False)}'
        )
        return await self.ap.box_service.execute_sandbox_tool(parameters, query)

    async def shutdown(self):
        if getattr(self.ap, 'box_service', None) is not None:
            await self.ap.box_service.shutdown()

    def _build_sandbox_exec_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=self.SANDBOX_EXEC_TOOL_NAME,
            human_desc='Execute a command inside the LangBot Box sandbox',
            description=(
                'Run shell commands only inside the isolated LangBot Box sandbox. '
                'Use this tool for local file edits, bash commands, Python execution, and exact calculations over '
                'user-provided data that must not touch the host.'
            ),
            parameters={
                'type': 'object',
                'properties': {
                    'cmd': {
                        'type': 'string',
                        'description': 'Shell command to execute inside the sandbox.',
                    },
                    'workdir': {
                        'type': 'string',
                        'description': 'Absolute working directory path inside the sandbox. Defaults to /workspace.',
                        'default': '/workspace',
                    },
                    'timeout_sec': {
                        'type': 'integer',
                        'description': 'Execution timeout in seconds. Defaults to 30.',
                        'default': 30,
                        'minimum': 1,
                    },
                    'network': {
                        'type': 'string',
                        'description': 'Network policy for the sandbox session. Prefer off unless network is required.',
                        'enum': ['off', 'on'],
                        'default': 'off',
                    },
                    'session_id': {
                        'type': 'string',
                        'description': 'Optional sandbox session id. Defaults to the current request id for reuse.',
                    },
                    'host_path': {
                        'type': 'string',
                        'description': (
                            'Optional absolute host directory path to mount into the sandbox as /workspace. '
                            'The path must be under an allowed host mount root.'
                        ),
                    },
                    'host_path_mode': {
                        'type': 'string',
                        'description': 'Mount mode for host_path. Use rw to create or modify host files.',
                        'enum': ['ro', 'rw'],
                        'default': 'rw',
                    },
                    'env': {
                        'type': 'object',
                        'description': 'Optional environment variables to expose inside the sandbox.',
                        'additionalProperties': {'type': 'string'},
                        'default': {},
                    },
                },
                'required': ['cmd'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _summarize_parameters(self, parameters: dict) -> dict:
        summary = dict(parameters)
        cmd = str(summary.get('cmd', '')).strip()
        if len(cmd) > 400:
            cmd = f'{cmd[:397]}...'
        summary['cmd'] = cmd

        env = summary.get('env')
        if isinstance(env, dict):
            summary['env_keys'] = sorted(str(key) for key in env.keys())
            del summary['env']

        return summary
