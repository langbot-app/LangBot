from __future__ import annotations

import base64
import contextlib
import errno
import json
import os
import posixpath
import stat
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import PurePosixPath

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
from langbot_plugin.api.entities.events import pipeline_query

from .. import loader
from ..errors import ToolNotFoundError
from .availability import is_box_backend_available
from . import skill as skill_loader
from ....api.http.context import ExecutionContext

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

_DIRECTORY_OPEN_FLAGS = (
    os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
)
_FILE_OPEN_FLAGS = getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_NONBLOCK', 0)
_SECURE_HOST_FILE_OPS_AVAILABLE = bool(
    getattr(os, 'O_NOFOLLOW', 0)
    and os.open in os.supports_dir_fd
    and os.stat in os.supports_dir_fd
    and os.mkdir in os.supports_dir_fd
    and os.listdir in os.supports_fd
    and os.scandir in os.supports_fd
)


@dataclass(frozen=True)
class _HostLocation:
    root: str
    relative_parts: tuple[str, ...]
    selected_skill: dict | None
    workspace_anchor: str | None = None


def _unsafe_host_path(path: str, exc: BaseException | None = None) -> ValueError:
    error = ValueError(f'Path escapes the workspace boundary or contains a symbolic link: {path}')
    if exc is not None:
        error.__cause__ = exc
    return error


def _relative_workspace_parts(path: str) -> tuple[str, ...]:
    normalized = posixpath.normpath(str(path or '/workspace').strip() or '/workspace')
    if normalized == '/workspace':
        return ()
    if not normalized.startswith('/workspace/'):
        raise ValueError('Path escapes the workspace boundary.')

    parts = tuple(part for part in normalized.removeprefix('/workspace/').split('/') if part)
    if any(part in {'.', '..'} or '\x00' in part for part in parts):
        raise ValueError('Path escapes the workspace boundary.')
    return parts


def _is_symlink_at(parent_fd: int, name: str) -> bool:
    try:
        return stat.S_ISLNK(os.stat(name, dir_fd=parent_fd, follow_symlinks=False).st_mode)
    except FileNotFoundError:
        return False


def _open_directory_at(parent_fd: int, name: str, *, create: bool) -> int:
    if create:
        try:
            os.mkdir(name, mode=0o777, dir_fd=parent_fd)
        except FileExistsError:
            pass

    try:
        directory_fd = os.open(name, _DIRECTORY_OPEN_FLAGS, dir_fd=parent_fd)
    except OSError as exc:
        if exc.errno == errno.ELOOP or _is_symlink_at(parent_fd, name):
            raise _unsafe_host_path(name, exc)
        raise
    if not stat.S_ISDIR(os.fstat(directory_fd).st_mode):
        os.close(directory_fd)
        raise NotADirectoryError(name)
    return directory_fd


def _open_directory_parts(root_fd: int, parts: tuple[str, ...], *, create: bool) -> int:
    current_fd = os.dup(root_fd)
    try:
        for part in parts:
            next_fd = _open_directory_at(current_fd, part, create=create)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


@contextlib.contextmanager
def _open_host_root(location: _HostLocation, *, create: bool) -> Iterator[int]:
    """Open and pin the tenant root before resolving tenant-controlled names."""

    if location.workspace_anchor is None:
        root_path = os.path.realpath(location.root)
        try:
            root_fd = os.open(root_path, _DIRECTORY_OPEN_FLAGS)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise _unsafe_host_path(location.root, exc)
            raise
    else:
        anchor_path = os.path.abspath(location.workspace_anchor)
        root_path = os.path.abspath(location.root)
        try:
            if os.path.commonpath((anchor_path, root_path)) != anchor_path:
                raise _unsafe_host_path(location.root)
        except ValueError as exc:
            raise _unsafe_host_path(location.root, exc)

        anchor_real_path = os.path.realpath(anchor_path)
        try:
            anchor_fd = os.open(anchor_real_path, _DIRECTORY_OPEN_FLAGS)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise _unsafe_host_path(location.workspace_anchor, exc)
            raise
        try:
            root_relative = os.path.relpath(root_path, anchor_path)
            root_parts = () if root_relative == '.' else tuple(root_relative.split(os.sep))
            root_fd = _open_directory_parts(anchor_fd, root_parts, create=create)
        finally:
            os.close(anchor_fd)

    try:
        if not stat.S_ISDIR(os.fstat(root_fd).st_mode):
            raise _unsafe_host_path(location.root)
        yield root_fd
    finally:
        os.close(root_fd)


@contextlib.contextmanager
def _open_location_fd(
    root_fd: int,
    relative_parts: tuple[str, ...],
    flags: int,
    *,
    create_parents: bool = False,
    mode: int = 0o666,
) -> Iterator[int]:
    if not relative_parts:
        target_fd = os.dup(root_fd)
    else:
        parent_fd = _open_directory_parts(root_fd, relative_parts[:-1], create=create_parents)
        try:
            try:
                target_fd = os.open(relative_parts[-1], flags | _FILE_OPEN_FLAGS, mode, dir_fd=parent_fd)
            except OSError as exc:
                if exc.errno == errno.ELOOP or _is_symlink_at(parent_fd, relative_parts[-1]):
                    raise _unsafe_host_path(relative_parts[-1], exc)
                raise
        finally:
            os.close(parent_fd)

    try:
        yield target_fd
    finally:
        os.close(target_fd)


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

    @staticmethod
    def _execution_context(query: pipeline_query.Query) -> ExecutionContext:
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
        require_sandbox = getattr(
            getattr(self.ap, 'box_service', None),
            'require_workspace_sandbox',
            None,
        )
        if callable(require_sandbox):
            await require_sandbox(self._execution_context(query))
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
        selected_skill_name: str | None = None

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

            # Pass only the logical name across the authenticated Core→Runtime
            # boundary. In Cloud mode the shared Box Runtime resolves the
            # Workspace-scoped package root and constructs the read-only mount;
            # Core host paths are never accepted as mount authority.
            # Wrap command with Python venv bootstrap if the skill has a Python project.
            # The venv is created inside the skill's mount path.
            skill_mount = f'/workspace/.skills/{selected_skill_name}'
            python_project = selected_skill.get('python_project') is True
            if 'python_project' not in selected_skill and bool(
                getattr(self.ap.box_service, 'shares_filesystem_with_box', False)
            ):
                # Backward compatibility for a same-process OSS Runtime that
                # predates trusted Box metadata. Never probe a path reported by
                # an external Runtime from the Core filesystem.
                python_project = skill_loader.should_prepare_skill_python_env(package_root)
            if python_project:
                parameters = dict(parameters)
                parameters['command'] = skill_loader.wrap_skill_command_with_python_env(
                    command,
                    mount_path=skill_mount,
                    state_path=f'/workspace/.skill-envs/{selected_skill_name}',
                )

        # All exec calls (with or without skills) go through the same container
        # via execute_tool. Skills are mounted at /workspace/.skills/{name}/
        # via extra_mounts built by BoxService.
        result = await self.ap.box_service.execute_tool(
            parameters,
            query,
            skill_name=selected_skill_name,
        )
        result = self._normalize_exec_result(result)

        if selected_skill is not None:
            self._refresh_skill_from_disk(query, selected_skill)
        return result

    def _resolve_host_location(
        self,
        query: pipeline_query.Query,
        sandbox_path: str,
        *,
        include_visible: bool,
        include_activated: bool,
    ) -> _HostLocation:
        selected_skill, rewritten_path = skill_loader.resolve_virtual_skill_path(
            self.ap,
            query,
            sandbox_path,
            include_visible=include_visible,
            include_activated=include_activated,
        )

        box_service = self.ap.box_service
        if selected_skill is not None:
            if not self._can_interpret_skill_host_paths():
                raise ValueError(
                    'Skill package paths are owned by the Box Runtime; '
                    'this operation requires a Runtime skill-file API.'
                )
            host_root = selected_skill.get('package_root')
            workspace_anchor = None
        else:
            host_root = box_service._tenant_workspace(self._execution_context(query))
            workspace_anchor = getattr(box_service, 'default_workspace', None)
        if not host_root:
            raise ValueError('No host workspace configured for file operations.')

        return _HostLocation(
            root=str(host_root),
            relative_parts=_relative_workspace_parts(rewritten_path),
            selected_skill=selected_skill,
            workspace_anchor=str(workspace_anchor) if workspace_anchor else None,
        )

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

        relative = '/'.join(_relative_workspace_parts(rewritten_path)) or '.'
        return selected_skill, relative

    def _can_interpret_skill_host_paths(self) -> bool:
        """Require an explicitly proven shared Core/Runtime filesystem view."""

        return _SECURE_HOST_FILE_OPS_AVAILABLE and bool(
            getattr(self.ap.box_service, 'shares_filesystem_with_box', False)
        )

    def _should_use_box_workspace_files(self, selected_skill: dict | None) -> bool:
        if selected_skill is not None:
            return False
        box_service = getattr(self.ap, 'box_service', None)
        if box_service is None or not hasattr(box_service, 'execute_tool'):
            return False
        if not _SECURE_HOST_FILE_OPS_AVAILABLE:
            # Preserve the OSS API on platforms without openat/O_NOFOLLOW by
            # running inside the tenant-scoped Box mount, never via a racy
            # host-path fallback.
            return True
        default_workspace = getattr(box_service, 'default_workspace', None)
        return bool(default_workspace and not os.path.isdir(os.path.realpath(default_workspace)))

    def _read_host_location(self, location: _HostLocation, parameters: dict) -> dict:
        with _open_host_root(location, create=False) as root_fd:
            with _open_location_fd(root_fd, location.relative_parts, os.O_RDONLY) as target_fd:
                metadata = os.fstat(target_fd)
                if stat.S_ISDIR(metadata.st_mode):
                    return self._build_directory_result(os.listdir(target_fd))
                if not stat.S_ISREG(metadata.st_mode):
                    raise ValueError('Path must reference a regular file or directory.')
                return self._read_text_file_preview(target_fd, parameters, metadata=metadata)

    def _write_host_location(self, location: _HostLocation, content: str, parameters: dict) -> None:
        if not location.relative_parts:
            raise ValueError('Path must reference a file under /workspace.')

        encoding, mode = self._write_options(parameters)
        if encoding == 'base64':
            try:
                payload = base64.b64decode(content, validate=True)
            except Exception as exc:
                raise ValueError(f'invalid base64 content: {exc}') from exc
        else:
            payload = content.encode('utf-8')

        flags = os.O_WRONLY | os.O_CREAT
        if mode == 'append':
            flags |= os.O_APPEND
        with _open_host_root(location, create=True) as root_fd:
            with _open_location_fd(
                root_fd,
                location.relative_parts,
                flags,
                create_parents=True,
            ) as target_fd:
                if not stat.S_ISREG(os.fstat(target_fd).st_mode):
                    raise ValueError('Path must reference a regular file.')
                if mode != 'append':
                    os.ftruncate(target_fd, 0)
                    os.lseek(target_fd, 0, os.SEEK_SET)
                self._write_all(target_fd, payload)

    def _edit_host_location(
        self,
        location: _HostLocation,
        old_string: str,
        new_string: str,
    ) -> tuple[bool, str | None]:
        if not location.relative_parts:
            raise ValueError('Path must reference a file under /workspace.')

        with _open_host_root(location, create=False) as root_fd:
            with _open_location_fd(root_fd, location.relative_parts, os.O_RDWR) as target_fd:
                if not stat.S_ISREG(os.fstat(target_fd).st_mode):
                    return False, 'File not found.'
                with os.fdopen(os.dup(target_fd), 'r', encoding='utf-8', errors='replace') as file_obj:
                    content = file_obj.read()
                count = content.count(old_string)
                if count == 0:
                    return False, 'old_string not found in file.'
                if count > 1:
                    return False, f'old_string matches {count} locations; provide a more unique string.'

                payload = content.replace(old_string, new_string, 1).encode('utf-8')
                os.ftruncate(target_fd, 0)
                os.lseek(target_fd, 0, os.SEEK_SET)
                self._write_all(target_fd, payload)
                return True, None

    @staticmethod
    def _write_all(file_fd: int, payload: bytes) -> None:
        view = memoryview(payload)
        while view:
            written = os.write(file_fd, view)
            if written <= 0:
                raise OSError('Could not write the complete workspace file.')
            view = view[written:]

    @staticmethod
    def _rglob_matches(relative_path: str, pattern: str) -> bool:
        candidates = {pattern}
        pending = [pattern]
        while pending:
            candidate = pending.pop()
            marker = candidate.find('**/')
            while marker >= 0:
                without_recursive_segment = candidate[:marker] + candidate[marker + 3 :]
                if without_recursive_segment not in candidates:
                    candidates.add(without_recursive_segment)
                    pending.append(without_recursive_segment)
                marker = candidate.find('**/', marker + 3)
        return any(candidate and PurePosixPath(relative_path).match(candidate) for candidate in candidates)

    def _glob_host_location(self, location: _HostLocation, pattern: str, sandbox_base: str) -> dict:
        hits: list[tuple[str, float]] = []

        def walk(directory_fd: int, prefix: str) -> None:
            with os.scandir(directory_fd) as entries:
                for entry in entries:
                    name = entry.name
                    if name in _SKIP_DIRS:
                        continue
                    try:
                        child_fd = os.open(name, os.O_RDONLY | _FILE_OPEN_FLAGS, dir_fd=directory_fd)
                    except OSError:
                        continue
                    try:
                        metadata = os.fstat(child_fd)
                        relative = f'{prefix}/{name}' if prefix else name
                        if self._rglob_matches(relative, pattern):
                            hits.append((relative, metadata.st_mtime))
                        if stat.S_ISDIR(metadata.st_mode):
                            walk(child_fd, relative)
                    finally:
                        os.close(child_fd)

        with _open_host_root(location, create=False) as root_fd:
            with _open_location_fd(root_fd, location.relative_parts, os.O_RDONLY) as target_fd:
                if not stat.S_ISDIR(os.fstat(target_fd).st_mode):
                    return {'ok': False, 'error': f'Path is not a directory: {sandbox_base}'}
                walk(target_fd, '')

        hits.sort(key=lambda item: item[1], reverse=True)
        total = len(hits)
        sandbox_paths: list[str] = []
        output_bytes = 0
        truncated_by_bytes = False
        for relative, _mtime in hits[:_GLOB_MAX_MATCHES]:
            sandbox_path = self._sandbox_child_path(sandbox_base, relative)
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

    def _grep_host_location(
        self,
        location: _HostLocation,
        regex,
        include: str | None,
        sandbox_base: str,
    ) -> dict:
        matches: list[dict] = []
        output_bytes = 0
        truncated_by: str | None = None
        files_seen = 0

        def grep_file(file_fd: int, sandbox_path: str) -> bool:
            nonlocal output_bytes, truncated_by
            with os.fdopen(os.dup(file_fd), 'r', encoding='utf-8', errors='ignore') as handle:
                for lineno, line in enumerate(handle, 1):
                    if not regex.search(line):
                        continue
                    content, line_truncated = self._truncate_grep_line(line.rstrip())
                    entry = {'file': sandbox_path, 'line': lineno, 'content': content}
                    entry_bytes = len(json.dumps(entry, ensure_ascii=False).encode('utf-8')) + 1
                    if output_bytes + entry_bytes > _DEFAULT_TOOL_RESULT_MAX_BYTES:
                        truncated_by = 'bytes'
                        return True
                    if line_truncated and truncated_by is None:
                        truncated_by = 'line'
                    matches.append(entry)
                    output_bytes += entry_bytes
                    if len(matches) >= _GREP_MAX_MATCHES:
                        truncated_by = truncated_by or 'matches'
                        return True
            return False

        def walk(directory_fd: int, prefix: str) -> bool:
            nonlocal files_seen
            with os.scandir(directory_fd) as entries:
                for entry in entries:
                    name = entry.name
                    if name in _SKIP_DIRS:
                        continue
                    try:
                        child_fd = os.open(name, os.O_RDONLY | _FILE_OPEN_FLAGS, dir_fd=directory_fd)
                    except OSError:
                        continue
                    try:
                        metadata = os.fstat(child_fd)
                        relative = f'{prefix}/{name}' if prefix else name
                        if stat.S_ISDIR(metadata.st_mode):
                            if walk(child_fd, relative):
                                return True
                            continue
                        if not stat.S_ISREG(metadata.st_mode):
                            continue
                        if include and not self._rglob_matches(relative, include):
                            continue
                        files_seen += 1
                        if grep_file(child_fd, self._sandbox_child_path(sandbox_base, relative)):
                            return True
                        if files_seen >= _GREP_MAX_FILES:
                            return True
                    finally:
                        os.close(child_fd)
            return False

        with _open_host_root(location, create=False) as root_fd:
            with _open_location_fd(root_fd, location.relative_parts, os.O_RDONLY) as target_fd:
                metadata = os.fstat(target_fd)
                if stat.S_ISREG(metadata.st_mode):
                    grep_file(target_fd, sandbox_base)
                elif stat.S_ISDIR(metadata.st_mode):
                    walk(target_fd, '')
                else:
                    return {'ok': False, 'error': f'Path not found: {sandbox_base}'}

        return {
            'ok': True,
            'matches': matches,
            'total': len(matches),
            'truncated': truncated_by is not None,
            'truncated_by': truncated_by,
        }

    @staticmethod
    def _sandbox_child_path(base: str, relative: str) -> str:
        return f'{str(base).rstrip("/")}/{relative}'

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
            if self._can_interpret_skill_host_paths():
                host_location = self._resolve_skill_host_location(selected_skill, relative)
            else:
                host_location = None
            if host_location is not None:
                try:
                    return self._read_host_location(host_location, parameters)
                except FileNotFoundError:
                    pass

            try:
                result = await self.ap.box_service.read_skill_file(
                    self._execution_context(query),
                    selected_skill['name'],
                    relative,
                )
                return self._build_read_result_from_text(str(result.get('content', '')), parameters)
            except Exception:
                try:
                    result = await self.ap.box_service.list_skill_files(
                        self._execution_context(query),
                        selected_skill['name'],
                        relative,
                    )
                    entries = [entry['name'] for entry in result.get('entries', [])]
                    return self._build_directory_result(entries)
                except Exception as exc:
                    return {'ok': False, 'error': str(exc)}

        host_location = self._resolve_host_location(
            query,
            path,
            include_visible=True,
            include_activated=True,
        )
        if self._should_use_box_workspace_files(host_location.selected_skill):
            return await self._read_workspace_via_box(path, parameters, query)
        try:
            return self._read_host_location(host_location, parameters)
        except (FileNotFoundError, NotADirectoryError):
            return {'ok': False, 'error': f'File not found: {path}'}

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
            execution_context = self._execution_context(query)
            await self.ap.box_service.write_skill_file(execution_context, selected_skill['name'], relative, content)
            await self.ap.skill_mgr.reload_skills(execution_context)
            return {'ok': True, 'path': path}

        host_location = self._resolve_host_location(
            query,
            path,
            include_visible=False,
            include_activated=True,
        )
        if self._should_use_box_workspace_files(host_location.selected_skill):
            return await self._write_workspace_via_box(path, content, parameters, query)
        try:
            self._write_host_location(host_location, content, parameters)
        except ValueError as exc:
            return {'ok': False, 'error': str(exc)}
        self._refresh_skill_from_disk(query, host_location.selected_skill)
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
                result = await self.ap.box_service.read_skill_file(
                    self._execution_context(query),
                    selected_skill['name'],
                    relative,
                )
            except Exception:
                return {'ok': False, 'error': f'File not found: {path}'}
            content = result.get('content', '')
            count = content.count(old_string)
            if count == 0:
                return {'ok': False, 'error': 'old_string not found in file.'}
            if count > 1:
                return {'ok': False, 'error': f'old_string matches {count} locations; provide a more unique string.'}
            new_content = content.replace(old_string, new_string, 1)
            execution_context = self._execution_context(query)
            await self.ap.box_service.write_skill_file(
                execution_context,
                selected_skill['name'],
                relative,
                new_content,
            )
            await self.ap.skill_mgr.reload_skills(execution_context)
            return {'ok': True, 'path': path}

        host_location = self._resolve_host_location(
            query,
            path,
            include_visible=False,
            include_activated=True,
        )
        if self._should_use_box_workspace_files(host_location.selected_skill):
            return await self._edit_workspace_via_box(path, old_string, new_string, query)
        try:
            changed, error = self._edit_host_location(host_location, old_string, new_string)
        except (FileNotFoundError, NotADirectoryError):
            return {'ok': False, 'error': f'File not found: {path}'}
        if not changed:
            return {'ok': False, 'error': error or f'File not found: {path}'}
        self._refresh_skill_from_disk(query, host_location.selected_skill)
        return {'ok': True, 'path': path}

    def _refresh_skill_from_disk(self, query: pipeline_query.Query, selected_skill: dict | None) -> None:
        if selected_skill is None:
            return

        skill_mgr = getattr(self.ap, 'skill_mgr', None)
        if skill_mgr is None:
            return

        refresh_skill = getattr(skill_mgr, 'refresh_skill_from_disk', None)
        if callable(refresh_skill):
            refresh_skill(self._execution_context(query), selected_skill.get('name', ''))

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

        host_location = self._resolve_host_location(
            query,
            path,
            include_visible=True,
            include_activated=True,
        )
        if self._should_use_box_workspace_files(host_location.selected_skill):
            return await self._glob_workspace_via_box(path, pattern, query)
        try:
            return self._glob_host_location(host_location, pattern, path)
        except (FileNotFoundError, NotADirectoryError):
            return {'ok': False, 'error': f'Path is not a directory: {path}'}

    async def _invoke_grep(self, parameters: dict, query: pipeline_query.Query) -> dict:
        pattern = parameters['pattern']
        path = str(parameters.get('path', '/workspace') or '/workspace')
        include = parameters.get('include')
        self.ap.logger.info(f'grep tool invoked: query_id={query.query_id} pattern={pattern} path={path}')

        import re

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return {'ok': False, 'error': f'Invalid regex: {e}'}

        host_location = self._resolve_host_location(
            query,
            path,
            include_visible=True,
            include_activated=True,
        )
        if self._should_use_box_workspace_files(host_location.selected_skill):
            return await self._grep_workspace_via_box(path, pattern, include, query)
        try:
            return self._grep_host_location(host_location, regex, include, path)
        except (FileNotFoundError, NotADirectoryError):
            return {'ok': False, 'error': f'Path not found: {path}'}

    @staticmethod
    def _resolve_skill_host_location(selected_skill: dict, relative: str) -> _HostLocation | None:
        package_root = str(selected_skill.get('package_root', '') or '').strip()
        if not package_root:
            return None
        relative_path = '/workspace' if relative in {'', '.'} else f'/workspace/{relative}'
        return _HostLocation(
            root=package_root,
            relative_parts=_relative_workspace_parts(relative_path),
            selected_skill=selected_skill,
        )

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

    def _read_text_file_preview(self, file_fd: int, parameters: dict, *, metadata: os.stat_result) -> dict:
        if self._read_encoding(parameters) == 'base64':
            return self._read_binary_file_chunk(file_fd, parameters, metadata=metadata)

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

        with os.fdopen(os.dup(file_fd), 'r', encoding='utf-8', errors='replace') as f:
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

    def _read_binary_file_chunk(self, file_fd: int, parameters: dict, *, metadata: os.stat_result) -> dict:
        byte_offset = self._non_negative_int(parameters.get('byte_offset'), default=0)
        max_bytes = self._positive_int(
            parameters.get('max_bytes'),
            default=_DEFAULT_TOOL_RESULT_MAX_BYTES,
            max_value=_DEFAULT_TOOL_RESULT_MAX_BYTES,
        )
        size_bytes = metadata.st_size
        with os.fdopen(os.dup(file_fd), 'rb') as f:
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
