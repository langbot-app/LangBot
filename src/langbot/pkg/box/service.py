from __future__ import annotations

import collections
import datetime as _dt
import enum
import json
import os
from typing import TYPE_CHECKING

import pydantic

from .client import BoxRuntimeClient
from .connector import BoxRuntimeConnector
from .errors import BoxError, BoxValidationError
from .models import BUILTIN_PROFILES, BoxExecutionResult, BoxProfile, BoxSpec, get_box_config

_INT_ADAPTER = pydantic.TypeAdapter(int)
_UTC = _dt.timezone.utc
_MAX_RECENT_ERRORS = 50

if TYPE_CHECKING:
    from ..core import app as core_app
    import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


class BoxService:
    def __init__(
        self,
        ap: 'core_app.Application',
        client: BoxRuntimeClient | None = None,
        output_limit_chars: int = 4000,
    ):
        self.ap = ap
        self._runtime_connector: BoxRuntimeConnector | None = None
        if client is None:
            self._runtime_connector = BoxRuntimeConnector(ap)
            client = self._runtime_connector.client
        self.client = client
        self.output_limit_chars = output_limit_chars
        self.allowed_host_mount_roots = self._load_allowed_host_mount_roots()
        self.default_host_workspace = self._load_default_host_workspace()
        self.profile = self._load_profile()
        self._recent_errors: collections.deque[dict] = collections.deque(maxlen=_MAX_RECENT_ERRORS)
        self._shutdown_task = None

    async def initialize(self):
        self._ensure_default_host_workspace()
        if self._runtime_connector is not None:
            await self._runtime_connector.initialize()
            return
        await self.client.initialize()

    async def execute_sandbox_tool(self, parameters: dict, query: 'pipeline_query.Query') -> dict:
        spec_payload = dict(parameters)
        spec_payload.setdefault('session_id', str(query.query_id))
        spec_payload.setdefault('env', {})
        if spec_payload.get('host_path') in (None, '') and self.default_host_workspace is not None:
            spec_payload['host_path'] = self.default_host_workspace

        self._apply_profile(spec_payload)

        try:
            spec = BoxSpec.model_validate(spec_payload)
        except pydantic.ValidationError as exc:
            first_error = exc.errors()[0]
            err = BoxValidationError(first_error.get('msg', 'invalid sandbox_exec arguments'))
            self._record_error(err, query)
            raise err from exc

        self._validate_host_mount(spec)
        self.ap.logger.info(
            'LangBot Box request: '
            f'query_id={query.query_id} '
            f'spec={json.dumps(self._summarize_spec(spec), ensure_ascii=False)}'
        )
        try:
            result = await self.client.execute(spec)
        except BoxError as exc:
            self._record_error(exc, query)
            raise
        self.ap.logger.info(
            'LangBot Box result: '
            f'query_id={query.query_id} '
            f'summary={json.dumps(self._summarize_result(result), ensure_ascii=False)}'
        )
        return self._serialize_result(result)

    async def shutdown(self):
        await self.client.shutdown()

    def dispose(self):
        if self._runtime_connector is not None:
            self._runtime_connector.dispose()
        loop = getattr(self.ap, 'event_loop', None)
        if (
            loop is not None
            and not loop.is_closed()
            and (self._shutdown_task is None or self._shutdown_task.done())
        ):
            self._shutdown_task = loop.create_task(self.shutdown())

    async def get_sessions(self) -> list[dict]:
        return await self.client.get_sessions()

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
            'timeout_sec': spec.timeout_sec,
            'network': spec.network.value,
            'image': spec.image,
            'host_path': spec.host_path,
            'host_path_mode': spec.host_path_mode.value,
            'cpus': spec.cpus,
            'memory_mb': spec.memory_mb,
            'pids_limit': spec.pids_limit,
            'read_only_rootfs': spec.read_only_rootfs,
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
        configured_roots = get_box_config(self.ap).get('allowed_host_mount_roots', [])

        normalized_roots: list[str] = []
        for root in configured_roots:
            root_value = str(root).strip()
            if not root_value:
                continue
            normalized_roots.append(os.path.realpath(os.path.abspath(root_value)))

        return normalized_roots

    def _load_default_host_workspace(self) -> str | None:
        default_host_workspace = str(get_box_config(self.ap).get('default_host_workspace', '')).strip()
        if not default_host_workspace:
            return None
        return os.path.realpath(os.path.abspath(default_host_workspace))

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
            if self.default_host_workspace == allowed_root or self.default_host_workspace.startswith(f'{allowed_root}{os.sep}'):
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
            raise BoxValidationError('host_path mounting is disabled because no allowed_host_mount_roots are configured')

        for allowed_root in self.allowed_host_mount_roots:
            if host_path == allowed_root or host_path.startswith(f'{allowed_root}{os.sep}'):
                return

        allowed_roots = ', '.join(self.allowed_host_mount_roots)
        raise BoxValidationError(f'host_path is outside allowed_host_mount_roots: {allowed_roots}')

    def _load_profile(self) -> BoxProfile:
        profile_name = str(get_box_config(self.ap).get('profile', 'default')).strip() or 'default'

        profile = BUILTIN_PROFILES.get(profile_name)
        if profile is None:
            available = ', '.join(sorted(BUILTIN_PROFILES))
            raise BoxValidationError(f"unknown box profile '{profile_name}', available profiles: {available}")
        return profile

    def _apply_profile(self, params: dict):
        """Merge profile defaults into *params* in-place, enforce locked fields and clamp timeout."""
        profile = self.profile
        _PROFILE_FIELDS = (
            'image', 'network', 'timeout_sec', 'host_path_mode',
            'cpus', 'memory_mb', 'pids_limit', 'read_only_rootfs',
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

    # ── Observability ─────────────────────────────────────────────────

    def _record_error(self, exc: Exception, query: 'pipeline_query.Query'):
        self._recent_errors.append({
            'timestamp': _dt.datetime.now(_UTC).isoformat(),
            'type': type(exc).__name__,
            'message': str(exc),
            'query_id': str(query.query_id),
        })

    def get_recent_errors(self) -> list[dict]:
        return list(self._recent_errors)

    async def get_status(self) -> dict:
        runtime_status = await self.client.get_status()
        return {
            **runtime_status,
            'profile': self.profile.name,
            'recent_error_count': len(self._recent_errors),
        }
