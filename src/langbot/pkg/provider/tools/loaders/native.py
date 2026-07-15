from __future__ import annotations

import base64
import json
import os

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
from langbot_plugin.api.entities.events import pipeline_query

from .. import loader
from ..errors import ToolNotFoundError
from .availability import is_box_backend_available
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

_DEFAULT_READ_MAX_LINES = 2000
_MAX_READ_MAX_LINES = 10000
_DEFAULT_TOOL_RESULT_MAX_BYTES = 50 * 1024
_BOX_FILE_SCRIPT_MAX_BYTES = 2048
_GLOB_MAX_MATCHES = 100
_GREP_MAX_MATCHES = 200
_GREP_MAX_FILES = 5000
_GREP_MAX_LINE_CHARS = 500


class NativeToolLoader(loader.ToolLoader):
    def __init__(self, ap):
        super().__init__(ap)
        self._tools: list[resource_tool.LLMTool] | None = None
        self._backend_available: bool | None = None

    async def initialize(self):
        """Check if backend is truly available at startup."""
        self._backend_available = await self._check_backend_available()
        if self._backend_available:
            self.ap.logger.info('Native sandbox tools (exec/read/write/edit/glob/grep) are available.')
        else:
            self.ap.logger.warning(
                'Native sandbox tools (exec/read/write/edit/glob/grep) are NOT available. '
                'No sandbox backend (Docker/nsjail/E2B) is ready. '
                'The LLM will not have access to code execution or file operation tools.'
            )

    async def _check_backend_available(self) -> bool:
        """Check if the box backend is truly available (not just the runtime)."""
        return await is_box_backend_available(self.ap)

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
        raise ToolNotFoundError(name)

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
        result = self._normalize_exec_result(result)

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

    def _resolve_skill_relative_path(
        self,
        query: pipeline_query.Query,
        sandbox_path: str,
        *,
        include_visible: bool,
        include_activated: bool,
    ) -> tuple[dict, str] | None:
        selected_skill, rewritten_path = skill_loader.resolve_virtual_skill_path(
            self.ap,
            query,
            sandbox_path,
            include_visible=include_visible,
            include_activated=include_activated,
        )
        if selected_skill is None:
            return None

        mount_path = '/workspace'
        if not rewritten_path.startswith(mount_path):
            raise ValueError(f'Path must be under {mount_path}.')
        relative = rewritten_path[len(mount_path) :].lstrip('/') or '.'
        return selected_skill, relative

    def _should_use_box_workspace_files(self, selected_skill: dict | None) -> bool:
        if selected_skill is not None:
            return False
        box_service = getattr(self.ap, 'box_service', None)
        if box_service is None or not hasattr(box_service, 'execute_tool'):
            return False
        default_workspace = getattr(box_service, 'default_workspace', None)
        return bool(default_workspace and not os.path.isdir(os.path.realpath(default_workspace)))

    async def _run_workspace_file_script(self, script: str, query: pipeline_query.Query) -> dict:
        result = await self.ap.box_service.execute_tool(
            {
                'command': f"python - <<'PY'\n{script}\nPY",
                'timeout_sec': 30,
            },
            query,
        )
        if not result.get('ok'):
            return {'ok': False, 'error': result.get('stderr') or result.get('stdout') or 'Box execution failed'}
        stdout = str(result.get('stdout') or '').strip()
        try:
            return json.loads(stdout.splitlines()[-1])
        except Exception:
            return {'ok': False, 'error': stdout or 'Box file operation returned no result'}

    async def _read_workspace_via_box(self, path: str, parameters: dict, query: pipeline_query.Query) -> dict:
        offset = self._positive_int(parameters.get('offset'), default=1)
        byte_offset = self._non_negative_int(parameters.get('byte_offset'), default=0)
        max_lines = self._positive_int(
            parameters.get('limit'),
            default=_DEFAULT_READ_MAX_LINES,
            max_value=_MAX_READ_MAX_LINES,
        )
        # Box file fallback returns through exec stdout, which is already capped
        # by BoxService. Keep this payload small enough to remain valid JSON.
        max_bytes = min(
            self._positive_int(parameters.get('max_bytes'), default=_DEFAULT_TOOL_RESULT_MAX_BYTES),
            _BOX_FILE_SCRIPT_MAX_BYTES,
        )
        encoding = self._read_encoding(parameters)
        script = f"""
import base64, json, os
path = {json.dumps(path)}
offset = {offset}
byte_offset = {byte_offset}
max_lines = {max_lines}
max_bytes = {max_bytes}
encoding = {json.dumps(encoding)}
if not path.startswith('/workspace'):
    print(json.dumps({{'ok': False, 'error': 'Path must be under /workspace.'}}))
elif not os.path.exists(path):
    print(json.dumps({{'ok': False, 'error': f'File not found: {{path}}'}}))
elif os.path.isdir(path):
    entries = sorted(os.listdir(path))
    content = '\\n'.join(entries)
    print(json.dumps({{'ok': True, 'content': content, 'is_directory': True, 'total': len(entries), 'truncated': False}}))
elif encoding == 'base64':
    size_bytes = os.path.getsize(path)
    with open(path, 'rb') as f:
        f.seek(byte_offset)
        data = f.read(max_bytes + 1)
    chunk = data[:max_bytes]
    has_more = len(data) > max_bytes
    print(json.dumps({{
        'ok': True,
        'content': base64.b64encode(chunk).decode('ascii'),
        'encoding': 'base64',
        'byte_offset': byte_offset,
        'length': len(chunk),
        'size_bytes': size_bytes,
        'has_more': has_more,
        'next_byte_offset': byte_offset + len(chunk) if has_more else None,
        'max_bytes': max_bytes,
    }}))
else:
    lines = []
    output_bytes = 0
    end_line = offset - 1
    truncated = False
    next_offset = None
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line_number, line in enumerate(f, 1):
            if line_number < offset:
                continue
            if len(lines) >= max_lines:
                truncated = True
                next_offset = line_number
                break
            line_bytes = len(line.encode('utf-8'))
            if output_bytes + line_bytes > max_bytes:
                truncated = True
                next_offset = line_number
                break
            lines.append(line.rstrip('\\n'))
            output_bytes += line_bytes
            end_line = line_number
    print(json.dumps({{
        'ok': True,
        'content': '\\n'.join(lines),
        'truncated': truncated,
        'start_line': offset,
        'end_line': end_line,
        'next_offset': next_offset,
        'max_lines': max_lines,
        'max_bytes': max_bytes,
    }}))
""".strip()
        return await self._run_workspace_file_script(script, query)

    async def _write_workspace_via_box(
        self,
        path: str,
        content: str,
        parameters: dict,
        query: pipeline_query.Query,
    ) -> dict:
        encoding, mode = self._write_options(parameters)
        script = f"""
import base64, json, os
path = {json.dumps(path)}
content = {json.dumps(content)}
encoding = {json.dumps(encoding)}
mode = {json.dumps(mode)}
if not path.startswith('/workspace'):
    print(json.dumps({{'ok': False, 'error': 'Path must be under /workspace.'}}))
else:
    os.makedirs(os.path.dirname(path) or '/workspace', exist_ok=True)
    if encoding == 'base64':
        try:
            data = base64.b64decode(content, validate=True)
        except Exception as exc:
            print(json.dumps({{'ok': False, 'error': f'invalid base64 content: {{exc}}'}}))
        else:
            with open(path, 'ab' if mode == 'append' else 'wb') as f:
                f.write(data)
            print(json.dumps({{'ok': True, 'path': path}}))
    else:
        with open(path, 'a' if mode == 'append' else 'w', encoding='utf-8') as f:
            f.write(content)
        print(json.dumps({{'ok': True, 'path': path}}))
""".strip()
        return await self._run_workspace_file_script(script, query)

    async def _edit_workspace_via_box(
        self,
        path: str,
        old_string: str,
        new_string: str,
        query: pipeline_query.Query,
    ) -> dict:
        script = f"""
import json, os
path = {json.dumps(path)}
old_string = {json.dumps(old_string)}
new_string = {json.dumps(new_string)}
if not path.startswith('/workspace'):
    print(json.dumps({{'ok': False, 'error': 'Path must be under /workspace.'}}))
elif not os.path.isfile(path):
    print(json.dumps({{'ok': False, 'error': f'File not found: {{path}}'}}))
else:
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    count = content.count(old_string)
    if count == 0:
        print(json.dumps({{'ok': False, 'error': 'old_string not found in file.'}}))
    elif count > 1:
        print(json.dumps({{'ok': False, 'error': f'old_string matches {{count}} locations; provide a more unique string.'}}))
    else:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content.replace(old_string, new_string, 1))
        print(json.dumps({{'ok': True, 'path': path}}))
""".strip()
        return await self._run_workspace_file_script(script, query)

    async def _glob_workspace_via_box(self, path: str, pattern: str, query: pipeline_query.Query) -> dict:
        script = f"""
import json, os
from pathlib import Path
path = {json.dumps(path)}
pattern = {json.dumps(pattern)}
skip_dirs = {json.dumps(sorted(_SKIP_DIRS))}
if not path.startswith('/workspace'):
    print(json.dumps({{'ok': False, 'error': 'Path must be under /workspace.'}}))
elif not os.path.isdir(path):
    print(json.dumps({{'ok': False, 'error': f'Path is not a directory: {{path}}'}}))
else:
    base = Path(path)
    hits = [
        item for item in base.rglob(pattern)
        if not any(part in skip_dirs for part in item.parts)
    ]
    hits.sort(key=lambda item: item.stat().st_mtime if item.exists() else 0, reverse=True)
    shown = hits[:{_GLOB_MAX_MATCHES}]
    matches = []
    output_bytes = 0
    truncated_by_bytes = False
    for item in shown:
        rel = os.path.relpath(str(item), path)
        sandbox_path = os.path.join(path, rel).replace(os.sep, '/')
        entry_bytes = len(sandbox_path.encode('utf-8')) + (1 if matches else 0)
        if output_bytes + entry_bytes > {_DEFAULT_TOOL_RESULT_MAX_BYTES}:
            truncated_by_bytes = True
            break
        matches.append(sandbox_path)
        output_bytes += entry_bytes
    print(json.dumps({{
        'ok': True,
        'matches': matches,
        'preview': '\\n'.join(matches),
        'total': len(hits),
        'truncated': len(hits) > len(matches) or truncated_by_bytes,
        'truncated_by': 'bytes' if truncated_by_bytes else ('matches' if len(hits) > len(matches) else None),
    }}))
""".strip()
        return await self._run_workspace_file_script(script, query)

    async def _grep_workspace_via_box(
        self,
        path: str,
        pattern: str,
        include: str | None,
        query: pipeline_query.Query,
    ) -> dict:
        script = f"""
import json, os, re
from pathlib import Path
path = {json.dumps(path)}
pattern = {json.dumps(pattern)}
include = {json.dumps(include)}
skip_dirs = {json.dumps(sorted(_SKIP_DIRS))}
try:
    regex = re.compile(pattern)
except re.error as exc:
    print(json.dumps({{'ok': False, 'error': f'Invalid regex: {{exc}}'}}))
else:
    if not path.startswith('/workspace'):
        print(json.dumps({{'ok': False, 'error': 'Path must be under /workspace.'}}))
    elif not os.path.exists(path):
        print(json.dumps({{'ok': False, 'error': f'Path not found: {{path}}'}}))
    else:
        base = Path(path)
        if base.is_file():
            files = [base]
        else:
            files = []
            for item in base.rglob(include or '*'):
                if any(part in skip_dirs for part in item.parts):
                    continue
                if item.is_file():
                    files.append(item)
                if len(files) >= {_GREP_MAX_FILES}:
                    break

        matches = []
        output_bytes = 0
        truncated_by = None
        for fp in files:
            try:
                handle = fp.open('r', encoding='utf-8', errors='ignore')
            except OSError:
                continue
            with handle:
                for lineno, line in enumerate(handle, 1):
                    if regex.search(line):
                        if base.is_file():
                            file_path = path
                        else:
                            rel = os.path.relpath(str(fp), path)
                            file_path = os.path.join(path, rel).replace(os.sep, '/')
                        content = line.rstrip()
                        line_truncated = False
                        if len(content) > {_GREP_MAX_LINE_CHARS}:
                            content = content[:{_GREP_MAX_LINE_CHARS}] + '... [truncated]'
                            line_truncated = True
                        entry = {{'file': file_path, 'line': lineno, 'content': content}}
                        entry_bytes = len(json.dumps(entry, ensure_ascii=False).encode('utf-8')) + 1
                        if output_bytes + entry_bytes > {_DEFAULT_TOOL_RESULT_MAX_BYTES}:
                            truncated_by = 'bytes'
                            break
                        if line_truncated and truncated_by is None:
                            truncated_by = 'line'
                        matches.append(entry)
                        output_bytes += entry_bytes
                        if len(matches) >= {_GREP_MAX_MATCHES}:
                            truncated_by = truncated_by or 'matches'
                            break
                if truncated_by == 'bytes' or len(matches) >= {_GREP_MAX_MATCHES}:
                    break
            if truncated_by == 'bytes' or len(matches) >= {_GREP_MAX_MATCHES}:
                break

        print(json.dumps({{
            'ok': True,
            'matches': matches,
            'total': len(matches),
            'truncated': truncated_by is not None,
            'truncated_by': truncated_by,
        }}))
""".strip()
        return await self._run_workspace_file_script(script, query)

    async def _invoke_read(self, parameters: dict, query: pipeline_query.Query) -> dict:
        path = parameters['path']
        self.ap.logger.info(f'read tool invoked: query_id={query.query_id} path={path}')
        skill_request = self._resolve_skill_relative_path(
            query,
            path,
            include_visible=True,
            include_activated=True,
        )
        if skill_request is not None and hasattr(self.ap.box_service, 'read_skill_file'):
            selected_skill, relative = skill_request
            host_path = self._resolve_skill_host_path(selected_skill, relative)
            if host_path and os.path.exists(host_path):
                if os.path.isdir(host_path):
                    return self._build_directory_result(os.listdir(host_path))
                return self._read_text_file_preview(host_path, parameters)

            try:
                result = await self.ap.box_service.read_skill_file(selected_skill['name'], relative)
                return self._build_read_result_from_text(str(result.get('content', '')), parameters)
            except Exception:
                try:
                    result = await self.ap.box_service.list_skill_files(selected_skill['name'], relative)
                    entries = [entry['name'] for entry in result.get('entries', [])]
                    return self._build_directory_result(entries)
                except Exception as exc:
                    return {'ok': False, 'error': str(exc)}

        host_path, selected_skill = self._resolve_host_path(
            query,
            path,
            include_visible=True,
            include_activated=True,
        )
        if self._should_use_box_workspace_files(selected_skill):
            return await self._read_workspace_via_box(path, parameters, query)
        if not os.path.exists(host_path):
            return {'ok': False, 'error': f'File not found: {path}'}
        if os.path.isdir(host_path):
            entries = os.listdir(host_path)
            return self._build_directory_result(entries)
        return self._read_text_file_preview(host_path, parameters)

    async def _invoke_write(self, parameters: dict, query: pipeline_query.Query) -> dict:
        path = parameters['path']
        content = parameters['content']
        self.ap.logger.info(f'write tool invoked: query_id={query.query_id} path={path} length={len(content)}')
        encoding, _mode = self._write_options(parameters)
        skill_request = self._resolve_skill_relative_path(
            query,
            path,
            include_visible=False,
            include_activated=True,
        )
        if skill_request is not None and hasattr(self.ap.box_service, 'write_skill_file'):
            if encoding != 'text':
                return {'ok': False, 'error': 'base64 writes to skill packages are not supported.'}
            selected_skill, relative = skill_request
            await self.ap.box_service.write_skill_file(selected_skill['name'], relative, content)
            await self.ap.skill_mgr.reload_skills()
            return {'ok': True, 'path': path}

        host_path, selected_skill = self._resolve_host_path(
            query,
            path,
            include_visible=False,
            include_activated=True,
        )
        if self._should_use_box_workspace_files(selected_skill):
            return await self._write_workspace_via_box(path, content, parameters, query)
        try:
            os.makedirs(os.path.dirname(host_path), exist_ok=True)
            self._write_host_file(host_path, content, parameters)
        except PermissionError:
            if selected_skill is None and hasattr(self.ap.box_service, 'execute_tool'):
                return await self._write_workspace_via_box(path, content, parameters, query)
            raise
        except ValueError as exc:
            return {'ok': False, 'error': str(exc)}
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
        skill_request = self._resolve_skill_relative_path(
            query,
            path,
            include_visible=False,
            include_activated=True,
        )
        if (
            skill_request is not None
            and hasattr(self.ap.box_service, 'read_skill_file')
            and hasattr(self.ap.box_service, 'write_skill_file')
        ):
            selected_skill, relative = skill_request
            try:
                result = await self.ap.box_service.read_skill_file(selected_skill['name'], relative)
            except Exception:
                return {'ok': False, 'error': f'File not found: {path}'}
            content = result.get('content', '')
            count = content.count(old_string)
            if count == 0:
                return {'ok': False, 'error': 'old_string not found in file.'}
            if count > 1:
                return {'ok': False, 'error': f'old_string matches {count} locations; provide a more unique string.'}
            new_content = content.replace(old_string, new_string, 1)
            await self.ap.box_service.write_skill_file(selected_skill['name'], relative, new_content)
            await self.ap.skill_mgr.reload_skills()
            return {'ok': True, 'path': path}

        host_path, selected_skill = self._resolve_host_path(
            query,
            path,
            include_visible=False,
            include_activated=True,
        )
        if self._should_use_box_workspace_files(selected_skill):
            return await self._edit_workspace_via_box(path, old_string, new_string, query)
        try:
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
        except PermissionError:
            if selected_skill is None and hasattr(self.ap.box_service, 'execute_tool'):
                return await self._edit_workspace_via_box(path, old_string, new_string, query)
            raise
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
        """Check if sandbox backend is available.

        This checks the cached backend availability from initialization,
        not just whether the box_service process is running.
        """
        return bool(self._backend_available)

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
                    'offset': {
                        'type': 'integer',
                        'description': '1-indexed line number to start reading from. Defaults to 1.',
                        'default': 1,
                        'minimum': 1,
                    },
                    'limit': {
                        'type': 'integer',
                        'description': f'Maximum number of lines to return. Defaults to {_DEFAULT_READ_MAX_LINES}.',
                        'default': _DEFAULT_READ_MAX_LINES,
                        'minimum': 1,
                        'maximum': _MAX_READ_MAX_LINES,
                    },
                    'max_bytes': {
                        'type': 'integer',
                        'description': (
                            f'Maximum bytes of file content to return. Defaults to {_DEFAULT_TOOL_RESULT_MAX_BYTES}.'
                        ),
                        'default': _DEFAULT_TOOL_RESULT_MAX_BYTES,
                        'minimum': 1,
                        'maximum': _DEFAULT_TOOL_RESULT_MAX_BYTES,
                    },
                    'encoding': {
                        'type': 'string',
                        'description': 'Return text by default, or base64 for binary byte-range reads.',
                        'enum': ['text', 'base64'],
                        'default': 'text',
                    },
                    'byte_offset': {
                        'type': 'integer',
                        'description': '0-indexed byte offset used when encoding is base64. Defaults to 0.',
                        'default': 0,
                        'minimum': 0,
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
                        'description': 'Text content, or base64 content when encoding is base64.',
                    },
                    'encoding': {
                        'type': 'string',
                        'description': 'Write content as text by default, or decode it from base64 for binary files.',
                        'enum': ['text', 'base64'],
                        'default': 'text',
                    },
                    'mode': {
                        'type': 'string',
                        'description': 'Overwrite the file by default, or append to it.',
                        'enum': ['overwrite', 'append'],
                        'default': 'overwrite',
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

        host_path, selected_skill = self._resolve_host_path(
            query,
            path,
            include_visible=True,
            include_activated=True,
        )
        if self._should_use_box_workspace_files(selected_skill):
            return await self._glob_workspace_via_box(path, pattern, query)

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
        shown = hits[:_GLOB_MAX_MATCHES]

        # Convert back to sandbox paths
        sandbox_paths = []
        output_bytes = 0
        truncated_by_bytes = False
        for h in shown:
            rel = os.path.relpath(str(h), host_path)
            sandbox_path = os.path.join(path, rel)
            entry_bytes = len(sandbox_path.encode('utf-8')) + (1 if sandbox_paths else 0)
            if output_bytes + entry_bytes > _DEFAULT_TOOL_RESULT_MAX_BYTES:
                truncated_by_bytes = True
                break
            sandbox_paths.append(sandbox_path)
            output_bytes += entry_bytes

        return {
            'ok': True,
            'matches': sandbox_paths,
            'preview': '\n'.join(sandbox_paths),
            'total': total,
            'truncated': total > len(sandbox_paths) or truncated_by_bytes,
            'truncated_by': 'bytes' if truncated_by_bytes else ('matches' if total > len(sandbox_paths) else None),
        }

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

        host_path, selected_skill = self._resolve_host_path(
            query,
            path,
            include_visible=True,
            include_activated=True,
        )
        if self._should_use_box_workspace_files(selected_skill):
            return await self._grep_workspace_via_box(path, pattern, include, query)

        if not os.path.exists(host_path):
            return {'ok': False, 'error': f'Path not found: {path}'}

        base = Path(host_path)

        if base.is_file():
            files = [base]
        else:
            files = self._grep_walk(base, include)

        matches = []
        output_bytes = 0
        truncated_by = None
        for fp in files:
            try:
                handle = fp.open('r', encoding='utf-8', errors='ignore')
            except OSError:
                continue
            with handle:
                for lineno, line in enumerate(handle, 1):
                    if regex.search(line):
                        rel = os.path.relpath(str(fp), host_path)
                        sandbox_path = os.path.join(path, rel)
                        content, line_truncated = self._truncate_grep_line(line.rstrip())
                        entry = {
                            'file': sandbox_path,
                            'line': lineno,
                            'content': content,
                        }
                        entry_bytes = len(json.dumps(entry, ensure_ascii=False).encode('utf-8')) + 1
                        if output_bytes + entry_bytes > _DEFAULT_TOOL_RESULT_MAX_BYTES:
                            truncated_by = 'bytes'
                            break
                        if line_truncated and truncated_by is None:
                            truncated_by = 'line'
                        matches.append(entry)
                        output_bytes += entry_bytes
                        if len(matches) >= _GREP_MAX_MATCHES:
                            truncated_by = truncated_by or 'matches'
                            break
                if truncated_by == 'bytes' or len(matches) >= _GREP_MAX_MATCHES:
                    break
            if truncated_by == 'bytes' or len(matches) >= _GREP_MAX_MATCHES:
                break

        return {
            'ok': True,
            'matches': matches,
            'total': len(matches),
            'truncated': truncated_by is not None,
            'truncated_by': truncated_by,
        }

    @staticmethod
    def _grep_walk(root, include: str | None) -> list:
        """Walk dir tree for grep, skipping junk dirs."""
        results = []
        for item in root.rglob(include or '*'):
            if any(skip in item.parts for skip in _SKIP_DIRS):
                continue
            if item.is_file():
                results.append(item)
            if len(results) >= _GREP_MAX_FILES:
                break
        return results

    @staticmethod
    def _resolve_skill_host_path(selected_skill: dict, relative: str) -> str | None:
        package_root = str(selected_skill.get('package_root', '') or '').strip()
        if not package_root:
            return None

        host_root = os.path.realpath(package_root)
        host_path = os.path.realpath(os.path.join(host_root, relative))
        if not (host_path == host_root or host_path.startswith(host_root + os.sep)):
            raise ValueError('Path escapes the skill package boundary.')
        return host_path

    def _normalize_exec_result(self, result: dict) -> dict:
        normalized = dict(result)
        stdout = str(normalized.get('stdout') or '')
        stderr = str(normalized.get('stderr') or '')
        stdout, stdout_capped = self._truncate_text_to_bytes_with_flag(stdout, _DEFAULT_TOOL_RESULT_MAX_BYTES)
        stderr, stderr_capped = self._truncate_text_to_bytes_with_flag(stderr, _DEFAULT_TOOL_RESULT_MAX_BYTES)
        normalized['stdout'] = stdout
        normalized['stderr'] = stderr
        normalized['stdout_truncated'] = bool(normalized.get('stdout_truncated') or stdout_capped)
        normalized['stderr_truncated'] = bool(normalized.get('stderr_truncated') or stderr_capped)

        if stdout and stderr:
            preview_raw = f'stdout:\n{stdout}\n\nstderr:\n{stderr}'
        else:
            preview_raw = stdout or stderr
        preview, preview_capped = self._truncate_text_to_bytes_with_flag(preview_raw, _DEFAULT_TOOL_RESULT_MAX_BYTES)
        normalized['preview'] = preview
        normalized['truncated'] = bool(
            normalized['stdout_truncated'] or normalized['stderr_truncated'] or preview_capped
        )
        if preview_capped and not normalized.get('truncated_by'):
            normalized['truncated_by'] = 'bytes'
        return normalized

    def _build_directory_result(self, entries: list[str]) -> dict:
        sorted_entries = sorted(str(entry) for entry in entries)
        content = '\n'.join(sorted_entries)
        preview = self._truncate_text_to_bytes(content, _DEFAULT_TOOL_RESULT_MAX_BYTES)
        truncated = preview != content
        return {
            'ok': True,
            'content': preview,
            'is_directory': True,
            'total': len(sorted_entries),
            'truncated': truncated,
            'truncated_by': 'bytes' if truncated else None,
        }

    def _read_text_file_preview(self, host_path: str, parameters: dict) -> dict:
        if self._read_encoding(parameters) == 'base64':
            return self._read_binary_file_chunk(host_path, parameters)

        offset = self._positive_int(parameters.get('offset'), default=1)
        max_lines = self._positive_int(
            parameters.get('limit'),
            default=_DEFAULT_READ_MAX_LINES,
            max_value=_MAX_READ_MAX_LINES,
        )
        max_bytes = self._positive_int(
            parameters.get('max_bytes'),
            default=_DEFAULT_TOOL_RESULT_MAX_BYTES,
            max_value=_DEFAULT_TOOL_RESULT_MAX_BYTES,
        )
        lines: list[str] = []
        output_bytes = 0
        end_line = offset - 1
        truncated = False
        truncated_by: str | None = None
        next_offset: int | None = None

        with open(host_path, 'r', encoding='utf-8', errors='replace') as f:
            for line_number, line in enumerate(f, 1):
                if line_number < offset:
                    continue
                if len(lines) >= max_lines:
                    truncated = True
                    truncated_by = 'lines'
                    next_offset = line_number
                    break

                line_bytes = len(line.encode('utf-8'))
                if output_bytes + line_bytes > max_bytes:
                    truncated = True
                    truncated_by = 'bytes'
                    next_offset = line_number
                    break

                lines.append(line.rstrip('\n'))
                output_bytes += line_bytes
                end_line = line_number

        if not lines and truncated_by == 'bytes':
            content = (
                f'[Line {next_offset or offset} exceeds the {self._format_size(max_bytes)} read limit. '
                'Use exec with a byte-range command for this line, or read a different offset.]'
            )
        else:
            content = '\n'.join(lines)

        return {
            'ok': True,
            'content': content,
            'truncated': truncated,
            'truncated_by': truncated_by,
            'start_line': offset,
            'end_line': end_line,
            'next_offset': next_offset,
            'max_lines': max_lines,
            'max_bytes': max_bytes,
        }

    def _read_binary_file_chunk(self, host_path: str, parameters: dict) -> dict:
        byte_offset = self._non_negative_int(parameters.get('byte_offset'), default=0)
        max_bytes = self._positive_int(
            parameters.get('max_bytes'),
            default=_DEFAULT_TOOL_RESULT_MAX_BYTES,
            max_value=_DEFAULT_TOOL_RESULT_MAX_BYTES,
        )
        size_bytes = os.path.getsize(host_path)
        with open(host_path, 'rb') as f:
            f.seek(byte_offset)
            data = f.read(max_bytes + 1)
        chunk = data[:max_bytes]
        has_more = len(data) > max_bytes
        return {
            'ok': True,
            'content': base64.b64encode(chunk).decode('ascii'),
            'encoding': 'base64',
            'byte_offset': byte_offset,
            'length': len(chunk),
            'size_bytes': size_bytes,
            'has_more': has_more,
            'next_byte_offset': byte_offset + len(chunk) if has_more else None,
            'max_bytes': max_bytes,
        }

    def _write_host_file(self, host_path: str, content: str, parameters: dict) -> None:
        encoding, mode = self._write_options(parameters)
        if encoding == 'base64':
            try:
                data = base64.b64decode(content, validate=True)
            except Exception as exc:
                raise ValueError(f'invalid base64 content: {exc}') from exc
            with open(host_path, 'ab' if mode == 'append' else 'wb') as f:
                f.write(data)
            return
        with open(host_path, 'a' if mode == 'append' else 'w', encoding='utf-8') as f:
            f.write(content)

    @staticmethod
    def _read_encoding(parameters: dict) -> str:
        return 'base64' if parameters.get('encoding') == 'base64' else 'text'

    @staticmethod
    def _write_options(parameters: dict) -> tuple[str, str]:
        encoding = 'base64' if parameters.get('encoding') == 'base64' else 'text'
        mode = 'append' if parameters.get('mode') == 'append' else 'overwrite'
        return encoding, mode

    def _build_read_result_from_text(self, content: str, parameters: dict) -> dict:
        offset = self._positive_int(parameters.get('offset'), default=1)
        max_lines = self._positive_int(
            parameters.get('limit'),
            default=_DEFAULT_READ_MAX_LINES,
            max_value=_MAX_READ_MAX_LINES,
        )
        max_bytes = self._positive_int(
            parameters.get('max_bytes'),
            default=_DEFAULT_TOOL_RESULT_MAX_BYTES,
            max_value=_DEFAULT_TOOL_RESULT_MAX_BYTES,
        )
        all_lines = content.splitlines()
        start_index = offset - 1
        if start_index >= len(all_lines) and all_lines:
            return {'ok': False, 'error': f'Offset {offset} is beyond end of file ({len(all_lines)} lines total)'}
        output_lines: list[str] = []
        output_bytes = 0
        truncated = False
        truncated_by: str | None = None
        next_offset: int | None = None
        for index, line in enumerate(all_lines[start_index:], start_index + 1):
            if len(output_lines) >= max_lines:
                truncated = True
                truncated_by = 'lines'
                next_offset = index
                break
            line_bytes = len(line.encode('utf-8')) + (1 if output_lines else 0)
            if output_bytes + line_bytes > max_bytes:
                truncated = True
                truncated_by = 'bytes'
                next_offset = index
                break
            output_lines.append(line)
            output_bytes += line_bytes

        end_line = offset + len(output_lines) - 1
        return {
            'ok': True,
            'content': '\n'.join(output_lines),
            'truncated': truncated,
            'truncated_by': truncated_by,
            'start_line': offset,
            'end_line': end_line,
            'next_offset': next_offset,
            'max_lines': max_lines,
            'max_bytes': max_bytes,
        }

    @staticmethod
    def _positive_int(value, *, default: int, max_value: int | None = None) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        if parsed <= 0:
            parsed = default
        if max_value is not None:
            parsed = min(parsed, max_value)
        return parsed

    @staticmethod
    def _non_negative_int(value, *, default: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        return parsed if parsed >= 0 else default

    @staticmethod
    def _truncate_grep_line(line: str) -> tuple[str, bool]:
        if len(line) <= _GREP_MAX_LINE_CHARS:
            return line, False
        return f'{line[:_GREP_MAX_LINE_CHARS]}... [truncated]', True

    @staticmethod
    def _truncate_text_to_bytes(text: str, max_bytes: int) -> str:
        return NativeToolLoader._truncate_text_to_bytes_with_flag(text, max_bytes)[0]

    @staticmethod
    def _truncate_text_to_bytes_with_flag(text: str, max_bytes: int) -> tuple[str, bool]:
        data = text.encode('utf-8')
        if len(data) <= max_bytes:
            return text, False
        truncated = data[:max_bytes]
        while truncated and (truncated[-1] & 0xC0) == 0x80:
            truncated = truncated[:-1]
        return truncated.decode('utf-8', errors='ignore'), True

    @staticmethod
    def _format_size(bytes_count: int) -> str:
        if bytes_count < 1024:
            return f'{bytes_count}B'
        return f'{bytes_count / 1024:.1f}KB'

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
