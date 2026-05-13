from __future__ import annotations

import json
import os

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
from langbot_plugin.api.entities.events import pipeline_query

from .. import loader
from . import skill as skill_loader

EXEC_TOOL_NAME = 'exec'
READ_TOOL_NAME = 'read'
WRITE_TOOL_NAME = 'write'
EDIT_TOOL_NAME = 'edit'
GLOB_TOOL_NAME = 'glob'
GREP_TOOL_NAME = 'grep'

_ALL_TOOL_NAMES = {EXEC_TOOL_NAME, READ_TOOL_NAME, WRITE_TOOL_NAME, EDIT_TOOL_NAME, GLOB_TOOL_NAME, GREP_TOOL_NAME}

# Skip these dirs during grep walk to avoid noise
_SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', '.tox', 'dist', 'build'}


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
                self._build_glob_tool(),
                self._build_grep_tool(),
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
        if name == GLOB_TOOL_NAME:
            return await self._invoke_glob(parameters, query)
        if name == GREP_TOOL_NAME:
            return await self._invoke_grep(parameters, query)
        raise ValueError(f'未找到工具: {name}')

    async def shutdown(self):
        pass

    async def _invoke_exec(self, parameters: dict, query: pipeline_query.Query) -> dict:
        command = str(parameters['command'])
        workdir = str(parameters.get('workdir', '/workspace') or '/workspace')

        # Validate that skill references target activated skills.
        selected_skill, _ = skill_loader.resolve_virtual_skill_path(
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

        if selected_skill is not None:
            selected_skill_name = str(selected_skill.get('name', '') or '')
            if referenced_skill_names and any(name != selected_skill_name for name in referenced_skill_names):
                raise ValueError('exec can reference files from only one activated skill package per call.')

            package_root = str(selected_skill.get('package_root', '') or '').strip()
            if not package_root:
                raise ValueError(f'Activated skill "{selected_skill_name}" has no package_root.')

            # Wrap command with Python venv bootstrap if the skill has a Python project.
            # The venv is created inside the skill's mount path.
            skill_mount = f'/workspace/.skills/{selected_skill_name}'
            if skill_loader.should_prepare_skill_python_env(package_root):
                parameters = dict(parameters)
                parameters['command'] = skill_loader.wrap_skill_command_with_python_env(command, mount_path=skill_mount)

        # All exec calls (with or without skills) go through the same container
        # via execute_tool. Skills are mounted at /workspace/.skills/{name}/
        # via extra_mounts built by BoxService.
        result = await self.ap.box_service.execute_tool(parameters, query)

        if selected_skill is not None:
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
        host_root = selected_skill.get('package_root') if selected_skill is not None else box_service.default_workspace
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
                'To create a new skill package, prepare it under /workspace first, then use register_skill.'
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
                'For new skills, write files under /workspace and then call register_skill.'
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
                'For new skills, edit files under /workspace and then call register_skill.'
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

    def _build_glob_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=GLOB_TOOL_NAME,
            human_desc='Find files matching a glob pattern',
            description=(
                'Find files matching a glob pattern under /workspace. '
                'Supports ** for recursive matching (e.g. **/*.py). '
                'Results are sorted by modification time (newest first). '
                'Visible and activated skill packages can be searched through /workspace/.skills/<skill-name>/...'
            ),
            parameters={
                'type': 'object',
                'properties': {
                    'pattern': {
                        'type': 'string',
                        'description': 'Glob pattern, e.g. **/*.py or src/**/*.ts',
                    },
                    'path': {
                        'type': 'string',
                        'description': 'Directory to search in (must be under /workspace, default: /workspace)',
                        'default': '/workspace',
                    },
                },
                'required': ['pattern'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_grep_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=GREP_TOOL_NAME,
            human_desc='Search file contents with regex',
            description=(
                'Search file contents with regex pattern under /workspace. '
                'Returns matching lines with file path and line number. '
                'Visible and activated skill packages can be searched through /workspace/.skills/<skill-name>/...'
            ),
            parameters={
                'type': 'object',
                'properties': {
                    'pattern': {
                        'type': 'string',
                        'description': 'Regex pattern to search for',
                    },
                    'path': {
                        'type': 'string',
                        'description': 'File or directory to search (must be under /workspace, default: /workspace)',
                        'default': '/workspace',
                    },
                    'include': {
                        'type': 'string',
                        'description': 'Only search files matching this glob (e.g. *.py)',
                    },
                },
                'required': ['pattern'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    async def _invoke_glob(self, parameters: dict, query: pipeline_query.Query) -> dict:
        pattern = parameters['pattern']
        path = str(parameters.get('path', '/workspace') or '/workspace')
        self.ap.logger.info(f'glob tool invoked: query_id={query.query_id} pattern={pattern} path={path}')

        host_path, _selected_skill = self._resolve_host_path(
            query,
            path,
            include_visible=True,
            include_activated=True,
        )

        if not os.path.isdir(host_path):
            return {'ok': False, 'error': f'Path is not a directory: {path}'}

        from pathlib import Path

        base = Path(host_path)
        hits = list(base.rglob(pattern))

        # Filter out skipped directories
        hits = [h for h in hits if not any(skip in h.parts for skip in _SKIP_DIRS)]

        # Sort by mtime, newest first
        hits.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

        total = len(hits)
        shown = hits[:100]

        # Convert back to sandbox paths
        sandbox_paths = []
        for h in shown:
            rel = os.path.relpath(str(h), host_path)
            sandbox_path = os.path.join(path, rel)
            sandbox_paths.append(sandbox_path)

        result_lines = sandbox_paths
        result = '\n'.join(result_lines)

        if total > 100:
            result += f'\n... ({total} matches, showing first 100)'

        return {'ok': True, 'matches': result_lines, 'total': total, 'truncated': total > 100}

    async def _invoke_grep(self, parameters: dict, query: pipeline_query.Query) -> dict:
        pattern = parameters['pattern']
        path = str(parameters.get('path', '/workspace') or '/workspace')
        include = parameters.get('include')
        self.ap.logger.info(f'grep tool invoked: query_id={query.query_id} pattern={pattern} path={path}')

        import re
        from pathlib import Path

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return {'ok': False, 'error': f'Invalid regex: {e}'}

        host_path, _selected_skill = self._resolve_host_path(
            query,
            path,
            include_visible=True,
            include_activated=True,
        )

        if not os.path.exists(host_path):
            return {'ok': False, 'error': f'Path not found: {path}'}

        base = Path(host_path)

        if base.is_file():
            files = [base]
        else:
            files = self._grep_walk(base, include)

        matches = []
        for fp in files:
            try:
                text = fp.read_text(errors='ignore')
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    rel = os.path.relpath(str(fp), host_path)
                    sandbox_path = os.path.join(path, rel)
                    matches.append({
                        'file': sandbox_path,
                        'line': lineno,
                        'content': line.rstrip(),
                    })
                    if len(matches) >= 200:
                        break
            if len(matches) >= 200:
                break

        return {
            'ok': True,
            'matches': matches,
            'total': len(matches),
            'truncated': len(matches) >= 200,
        }

    @staticmethod
    def _grep_walk(root, include: str | None) -> list:
        """Walk dir tree for grep, skipping junk dirs."""
        from pathlib import Path
        results = []
        for item in root.rglob(include or '*'):
            if any(skip in item.parts for skip in _SKIP_DIRS):
                continue
            if item.is_file():
                results.append(item)
            if len(results) >= 5000:
                break
        return results

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
