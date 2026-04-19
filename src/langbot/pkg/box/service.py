from __future__ import annotations

import asyncio
import collections
import datetime as _dt
import enum
import json
import os
from typing import TYPE_CHECKING

import pydantic

from langbot_plugin.box.client import BoxRuntimeClient
from .connector import BoxRuntimeConnector, _get_box_config
from langbot_plugin.box.errors import BoxError, BoxValidationError
from langbot_plugin.box.models import (
    BUILTIN_PROFILES,
    BoxExecutionResult,
    BoxManagedProcessInfo,
    BoxManagedProcessSpec,
    BoxProfile,
    BoxSpec,
)

_INT_ADAPTER = pydantic.TypeAdapter(int)
_UTC = _dt.timezone.utc
_MAX_RECENT_ERRORS = 50
_MIB = 1024 * 1024


def _is_path_under(path: str, root: str) -> bool:
    """Check whether *path* equals *root* or is a child of *root*."""
    return path == root or path.startswith(f'{root}{os.sep}')


def _is_path_under(path: str, root: str) -> bool:
    """Check whether *path* equals *root* or is a child of *root*."""
    return path == root or path.startswith(f'{root}{os.sep}')


if TYPE_CHECKING:
    from ..core import app as core_app
    import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


class BoxService:
    def __init__(
        self,
        ap: core_app.Application,
        client: BoxRuntimeClient | None = None,
        output_limit_chars: int = 4000,
    ):
        self.ap = ap
        self._runtime_connector: BoxRuntimeConnector | None = None
        if client is None:
            self._runtime_connector = BoxRuntimeConnector(ap, runtime_disconnect_callback=self._on_runtime_disconnect)
            client = self._runtime_connector.client
        self.client = client
        self.output_limit_chars = output_limit_chars
        self.shared_host_root = self._load_shared_host_root()
        self.allowed_host_mount_roots = self._load_allowed_host_mount_roots()
        self.default_host_workspace = self._load_default_host_workspace()
        self.profile = self._load_profile()
        self.custom_image = self._load_custom_image()
        self.workspace_quota_mb = self._load_workspace_quota_mb()
        self._recent_errors: collections.deque[dict] = collections.deque(maxlen=_MAX_RECENT_ERRORS)
        self._shutdown_task = None
        self._available = False
        self._connector_error: str = ''

    async def initialize(self):
        self._ensure_default_host_workspace()
        try:
            if self._runtime_connector is not None:
                await self._runtime_connector.initialize()
            else:
                await self.client.initialize()
            self._available = True
            self._connector_error = ''
            self.ap.logger.info(
                f'LangBot Box runtime initialized: profile={self.profile.name} '
                f'default_workspace={self.default_host_workspace or "(none)"}'
            )
        except Exception as exc:
            self.ap.logger.warning(f'LangBot Box runtime unavailable, sandbox features disabled: {exc}')
            self._available = False
            self._connector_error = str(exc)

    async def _on_runtime_disconnect(self, connector: BoxRuntimeConnector) -> None:
        """Called by the connector when the Box runtime connection drops."""
        self._available = False
        self._connector_error = 'Disconnected from Box runtime'
        self.ap.logger.warning('Box runtime disconnected, sandbox features temporarily disabled. Reconnecting in 3s...')
        await asyncio.sleep(3)
        try:
            await connector.initialize()
            self._available = True
            self._connector_error = ''
            self.ap.logger.info('Box runtime reconnected, sandbox features restored.')
        except Exception as exc:
            self._connector_error = str(exc)
            self.ap.logger.warning(f'Box runtime reconnection failed: {exc}. Will retry on next heartbeat disconnect.')

    @property
    def available(self) -> bool:
        return self._available

    async def execute_spec_payload(
        self,
        spec_payload: dict,
        query: pipeline_query.Query,
        *,
        skip_host_mount_validation: bool = False,
    ) -> dict:
        if not self._available:
            raise BoxError('Box runtime is not available. Install and start Podman or Docker to use sandbox features.')
        try:
            spec = self.build_spec(spec_payload, skip_host_mount_validation=skip_host_mount_validation)
        except BoxError as exc:
            self._record_error(exc, query)
            raise
        self.ap.logger.info(
            'LangBot Box request: '
            f'query_id={query.query_id} '
            f'spec={json.dumps(self._summarize_spec(spec), ensure_ascii=False)}'
        )
        try:
            self._enforce_workspace_quota(spec, phase='before execution')
        except BoxError as exc:
            self._record_error(exc, query)
            raise
        try:
            result = await self.client.execute(spec)
        except BoxError as exc:
            self._record_error(exc, query)
            raise
        try:
            self._enforce_workspace_quota(spec, phase='after execution')
        except BoxError as exc:
            await self._cleanup_exceeded_session(spec)
            self._record_error(exc, query)
            raise
        self.ap.logger.info(
            'LangBot Box result: '
            f'query_id={query.query_id} '
            f'summary={json.dumps(self._summarize_result(result), ensure_ascii=False)}'
        )
        return self._serialize_result(result)

    def resolve_box_session_id(self, query: pipeline_query.Query) -> str:
        """Resolve the Box session_id from the pipeline's template and query variables."""
        template = (
            (query.pipeline_config or {})
            .get('ai', {})
            .get('local-agent', {})
            .get('box-session-id-template', '{launcher_type}_{launcher_id}')
        )
        variables = query.variables or {}
        return template.format_map(collections.defaultdict(lambda: 'unknown', variables))

    def build_skill_extra_mounts(self, query: pipeline_query.Query) -> list[dict]:
        """Build extra_mounts entries for all pipeline-bound skills.

        This ensures that when a container is first created it already has
        all skill packages mounted, regardless of which skill is currently
        activated.
        """
        skill_mgr = getattr(self.ap, 'skill_mgr', None)
        if skill_mgr is None:
            return []

        from ..provider.tools.loaders import skill as skill_loader

        visible_skills = skill_loader.get_visible_skills(self.ap, query)
        mounts: list[dict] = []
        for skill_name, skill_data in visible_skills.items():
            package_root = str(skill_data.get('package_root', '') or '').strip()
            if not package_root:
                continue
            mounts.append(
                {
                    'host_path': package_root,
                    'mount_path': f'/workspace/.skills/{skill_name}',
                    'mode': 'rw',
                }
            )
        return mounts

    async def execute_tool(self, parameters: dict, query: pipeline_query.Query) -> dict:
        """Execute an agent-facing ``exec`` tool call.

        Translates the agent-facing ``command`` field to the internal
        ``BoxSpec.cmd`` field and injects the session id from the query.
        """
        spec_payload: dict = {'cmd': parameters['command']}

        # Pass through allowed agent-facing fields
        for key in ('workdir', 'timeout_sec', 'env'):
            if key in parameters:
                spec_payload[key] = parameters[key]

        # Inject context the agent must not control
        spec_payload.setdefault('session_id', self.resolve_box_session_id(query))

        # Mount all pipeline-bound skills so they are available in the container
        if 'extra_mounts' not in spec_payload:
            spec_payload['extra_mounts'] = self.build_skill_extra_mounts(query)

        return await self.execute_spec_payload(spec_payload, query)

    async def shutdown(self):
        await self.client.shutdown()

    def dispose(self):
        if self._runtime_connector is not None:
            self._runtime_connector.dispose()
        loop = getattr(self.ap, 'event_loop', None)
        if loop is not None and not loop.is_closed() and (self._shutdown_task is None or self._shutdown_task.done()):
            self._shutdown_task = loop.create_task(self.shutdown())

    async def get_sessions(self) -> list[dict]:
        return await self.client.get_sessions()

    def build_spec(self, spec_payload: dict, skip_host_mount_validation: bool = False) -> BoxSpec:
        spec_payload = dict(spec_payload)
        spec_payload.setdefault('env', {})
        if spec_payload.get('host_path') in (None, '') and self.default_host_workspace is not None:
            spec_payload['host_path'] = self.default_host_workspace
        if spec_payload.get('workspace_quota_mb') in (None, '') and self.workspace_quota_mb is not None:
            spec_payload['workspace_quota_mb'] = self.workspace_quota_mb

        # Global custom image overrides profile default (but not caller-specified image)
        if self.custom_image and 'image' not in spec_payload:
            spec_payload['image'] = self.custom_image

        self._apply_profile(spec_payload)

        try:
            spec = BoxSpec.model_validate(spec_payload)
        except pydantic.ValidationError as exc:
            first_error = exc.errors()[0]
            raise BoxValidationError(first_error.get('msg', 'invalid box arguments')) from exc

        if not skip_host_mount_validation:
            self._validate_host_mount(spec)
        return spec

    async def create_session(self, spec_payload: dict, *, skip_host_mount_validation: bool = False) -> dict:
        spec = self.build_spec(spec_payload, skip_host_mount_validation=skip_host_mount_validation)
        return await self.client.create_session(spec)

    async def start_managed_process(self, session_id: str, process_payload: dict) -> BoxManagedProcessInfo:
        process_spec = BoxManagedProcessSpec.model_validate(process_payload)
        return await self.client.start_managed_process(session_id, process_spec)

    async def get_managed_process(self, session_id: str) -> BoxManagedProcessInfo:
        return await self.client.get_managed_process(session_id)

    def get_managed_process_websocket_url(self, session_id: str) -> str:
        getter = getattr(self.client, 'get_managed_process_websocket_url', None)
        if getter is None:
            raise BoxValidationError('box runtime client does not support managed process websocket attach')
        ws_relay_base_url = (
            self._runtime_connector.ws_relay_base_url
            if self._runtime_connector is not None
            else 'http://127.0.0.1:5410'
        )
        return getter(session_id, ws_relay_base_url)

    def _serialize_result(self, result: BoxExecutionResult) -> dict:
        stdout, stdout_truncated = self._truncate(result.stdout)
        stderr, stderr_truncated = self._truncate(result.stderr)

        return {
            'session_id': result.session_id,
            'backend': result.backend_name,
            'status': result.status.value,
            'ok': result.ok,
            'exit_code': result.exit_code,
            'stdout': stdout,
            'stderr': stderr,
            'stdout_truncated': stdout_truncated,
            'stderr_truncated': stderr_truncated,
            'duration_ms': result.duration_ms,
        }

    def _truncate(self, text: str) -> tuple[str, bool]:
        if len(text) <= self.output_limit_chars:
            return text, False
        if self.output_limit_chars <= 0:
            return '', True

        head_size = 0
        tail_size = 0
        notice = ''
        # Recompute once the omitted count is known so the final payload
        # stays within output_limit_chars even after adding the notice.
        for _ in range(4):
            omitted = max(len(text) - head_size - tail_size, 0)
            notice = f'\n\n... [{omitted} characters truncated] ...\n\n'
            available = self.output_limit_chars - len(notice)
            if available <= 0:
                return notice[: self.output_limit_chars], True

            new_head_size = int(available * 0.6)
            new_tail_size = available - new_head_size
            if new_head_size == head_size and new_tail_size == tail_size:
                break
            head_size = new_head_size
            tail_size = new_tail_size

        head = text[:head_size]
        tail = text[-tail_size:] if tail_size else ''
        truncated = f'{head}{notice}{tail}'
        return truncated[: self.output_limit_chars], True

    def _summarize_spec(self, spec: BoxSpec) -> dict:
        cmd = spec.cmd.strip()
        if len(cmd) > 400:
            cmd = f'{cmd[:397]}...'

        return {
            'session_id': spec.session_id,
            'workdir': spec.workdir,
            'mount_path': spec.mount_path,
            'timeout_sec': spec.timeout_sec,
            'network': spec.network.value,
            'image': spec.image,
            'host_path': spec.host_path,
            'host_path_mode': spec.host_path_mode.value,
            'cpus': spec.cpus,
            'memory_mb': spec.memory_mb,
            'pids_limit': spec.pids_limit,
            'read_only_rootfs': spec.read_only_rootfs,
            'workspace_quota_mb': spec.workspace_quota_mb,
            'env_keys': sorted(spec.env.keys()),
            'cmd': cmd,
        }

    def _summarize_result(self, result: BoxExecutionResult) -> dict:
        stdout_preview = result.stdout[:200]
        stderr_preview = result.stderr[:200]
        if len(result.stdout) > 200:
            stdout_preview = f'{stdout_preview}...'
        if len(result.stderr) > 200:
            stderr_preview = f'{stderr_preview}...'

        return {
            'session_id': result.session_id,
            'backend': result.backend_name,
            'status': result.status.value,
            'exit_code': result.exit_code,
            'duration_ms': result.duration_ms,
            'stdout_preview': stdout_preview,
            'stderr_preview': stderr_preview,
        }

    def _load_allowed_host_mount_roots(self) -> list[str]:
        configured_roots = _get_box_config(self.ap).get('allowed_host_mount_roots', [])

        normalized_roots: list[str] = []
        for root in configured_roots:
            root_value = str(root).strip()
            if not root_value:
                continue
            normalized_roots.append(os.path.realpath(os.path.abspath(root_value)))

        if not normalized_roots and self.shared_host_root is not None:
            normalized_roots.append(self.shared_host_root)

        return normalized_roots

    def _load_shared_host_root(self) -> str | None:
        shared_host_root = str(_get_box_config(self.ap).get('shared_host_root', '')).strip()
        if not shared_host_root:
            return None
        return os.path.realpath(os.path.abspath(shared_host_root))

    def _load_default_host_workspace(self) -> str | None:
        default_host_workspace = str(_get_box_config(self.ap).get('default_host_workspace', '')).strip()
        if not default_host_workspace:
            if self.shared_host_root is None:
                return None
            default_host_workspace = os.path.join(self.shared_host_root, 'default')
        return os.path.realpath(os.path.abspath(default_host_workspace))

    def _load_custom_image(self) -> str | None:
        raw = str(_get_box_config(self.ap).get('image', '') or '').strip()
        return raw or None

    def _load_workspace_quota_mb(self) -> int | None:
        raw_value = _get_box_config(self.ap).get('workspace_quota_mb')
        if raw_value in (None, ''):
            return None
        try:
            value = _INT_ADAPTER.validate_python(raw_value)
        except pydantic.ValidationError as exc:
            raise BoxValidationError('workspace_quota_mb must be an integer greater than or equal to 0') from exc
        if value < 0:
            raise BoxValidationError('workspace_quota_mb must be greater than or equal to 0')
        return value

    def _ensure_default_host_workspace(self):
        if self.default_host_workspace is None:
            return

        if os.path.isdir(self.default_host_workspace):
            return

        if os.path.exists(self.default_host_workspace):
            raise BoxValidationError('default_host_workspace must point to a directory on the host')

        if not self.allowed_host_mount_roots:
            raise BoxValidationError(
                'default_host_workspace cannot be created because no allowed_host_mount_roots are configured'
            )

        for allowed_root in self.allowed_host_mount_roots:
            if _is_path_under(self.default_host_workspace, allowed_root):
                os.makedirs(self.default_host_workspace, exist_ok=True)
                return

        allowed_roots = ', '.join(self.allowed_host_mount_roots)
        raise BoxValidationError(f'default_host_workspace is outside allowed_host_mount_roots: {allowed_roots}')

    def _validate_host_mount(self, spec: BoxSpec):
        if spec.host_path is None:
            return

        host_path = os.path.realpath(spec.host_path)
        if not os.path.isdir(host_path):
            raise BoxValidationError('host_path must point to an existing directory on the host')

        if not self.allowed_host_mount_roots:
            raise BoxValidationError(
                'host_path mounting is disabled because no allowed_host_mount_roots are configured'
            )

        for allowed_root in self.allowed_host_mount_roots:
            if _is_path_under(host_path, allowed_root):
                return

        allowed_roots = ', '.join(self.allowed_host_mount_roots)
        raise BoxValidationError(f'host_path is outside allowed_host_mount_roots: {allowed_roots}')

    def _load_profile(self) -> BoxProfile:
        profile_name = str(_get_box_config(self.ap).get('profile', 'default')).strip() or 'default'

        profile = BUILTIN_PROFILES.get(profile_name)
        if profile is None:
            available = ', '.join(sorted(BUILTIN_PROFILES))
            raise BoxValidationError(f"unknown box profile '{profile_name}', available profiles: {available}")
        return profile

    def _apply_profile(self, params: dict):
        """Merge profile defaults into *params* in-place, enforce locked fields and clamp timeout."""
        profile = self.profile
        _PROFILE_FIELDS = (
            'image',
            'network',
            'timeout_sec',
            'host_path_mode',
            'cpus',
            'memory_mb',
            'pids_limit',
            'read_only_rootfs',
            'workspace_quota_mb',
        )

        for field in _PROFILE_FIELDS:
            profile_value = getattr(profile, field)
            raw_value = profile_value.value if isinstance(profile_value, enum.Enum) else profile_value

            if field in profile.locked:
                params[field] = raw_value
            elif field not in params:
                params[field] = raw_value

        timeout = params.get('timeout_sec')
        try:
            normalized_timeout = _INT_ADAPTER.validate_python(timeout)
        except pydantic.ValidationError:
            return

        if normalized_timeout > profile.max_timeout_sec:
            params['timeout_sec'] = profile.max_timeout_sec

    def _get_workspace_size_bytes(self, root: str) -> int:
        total = 0

        def _walk(path: str):
            nonlocal total
            try:
                with os.scandir(path) as entries:
                    for entry in entries:
                        try:
                            if entry.is_symlink():
                                total += entry.stat(follow_symlinks=False).st_size
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                _walk(entry.path)
                                continue
                            total += entry.stat(follow_symlinks=False).st_size
                        except FileNotFoundError:
                            continue
            except FileNotFoundError:
                return

        _walk(root)
        return total

    def _enforce_workspace_quota(self, spec: BoxSpec, *, phase: str) -> None:
        if spec.host_path is None or spec.workspace_quota_mb <= 0:
            return

        host_path = os.path.realpath(spec.host_path)
        if not os.path.isdir(host_path):
            return

        used_bytes = self._get_workspace_size_bytes(host_path)
        limit_bytes = spec.workspace_quota_mb * _MIB
        if used_bytes <= limit_bytes:
            return

        raise BoxValidationError(
            f'workspace quota exceeded {phase}: '
            f'used={used_bytes} bytes limit={limit_bytes} bytes '
            f'host_path={host_path} session_id={spec.session_id}'
        )

    async def _cleanup_exceeded_session(self, spec: BoxSpec) -> None:
        try:
            await self.client.delete_session(spec.session_id)
        except Exception as exc:
            self.ap.logger.warning(
                'Failed to clean up Box session after workspace quota was exceeded: '
                f'session_id={spec.session_id} error={exc}'
            )

    # ── Observability ─────────────────────────────────────────────────

    def _record_error(self, exc: Exception, query: pipeline_query.Query):
        self._recent_errors.append(
            {
                'timestamp': _dt.datetime.now(_UTC).isoformat(),
                'type': type(exc).__name__,
                'message': str(exc),
                'query_id': str(query.query_id),
            }
        )

    def get_recent_errors(self) -> list[dict]:
        return list(self._recent_errors)

    def get_system_guidance(self) -> str:
        """Return LLM system-prompt guidance for the exec tool.

        All execution-specific prompt text is kept here so that callers
        (e.g. LocalAgentRunner) stay free of box domain knowledge.
        """
        guidance = (
            'When the exec tool is available, use it for exact calculations, statistics, structured data parsing, '
            'and code execution instead of estimating mentally. If the user provides numbers, tables, CSV-like text, '
            'JSON, or other data and asks for a computed answer, prefer running a short Python script via exec '
            'and then answer from the tool result. Unless the user explicitly asks for the script, code, or implementation '
            'details, do not include the generated script in the final answer; return the result and a brief explanation only.'
        )
        if self.default_host_workspace:
            guidance += (
                ' A default workspace is mounted at /workspace for file tasks. When the user asks to read, create, or '
                'modify local files in the working directory, use exec with /workspace paths directly; do not ask the '
                'user for directory parameters unless they explicitly need a different directory.'
            )
        return guidance

    async def get_status(self) -> dict:
        if not self._available:
            return {
                'available': False,
                'profile': self.profile.name,
                'recent_error_count': len(self._recent_errors),
                'connector_error': self._connector_error,
            }
        runtime_status = await self.client.get_status()
        return {
            **runtime_status,
            'available': True,
            'profile': self.profile.name,
            'recent_error_count': len(self._recent_errors),
        }
