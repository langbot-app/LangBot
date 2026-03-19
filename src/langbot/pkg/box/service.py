from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pydantic

from .errors import BoxValidationError
from .models import BoxExecutionResult, BoxSpec
from .runtime import BoxRuntime

if TYPE_CHECKING:
    from ..core import app as core_app
    import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


class BoxService:
    def __init__(
        self,
        ap: 'core_app.Application',
        runtime: BoxRuntime | None = None,
        output_limit_chars: int = 4000,
    ):
        self.ap = ap
        self.runtime = runtime or BoxRuntime(logger=ap.logger)
        self.output_limit_chars = output_limit_chars
        self.allowed_host_mount_roots = self._load_allowed_host_mount_roots()
        self.default_host_workspace = self._load_default_host_workspace()

    async def initialize(self):
        await self.runtime.initialize()

    async def execute_sandbox_tool(self, parameters: dict, query: 'pipeline_query.Query') -> dict:
        spec_payload = dict(parameters)
        spec_payload.setdefault('session_id', str(query.query_id))
        spec_payload.setdefault('env', {})
        if spec_payload.get('host_path') in (None, '') and self.default_host_workspace is not None:
            spec_payload['host_path'] = self.default_host_workspace

        try:
            spec = BoxSpec.model_validate(spec_payload)
        except pydantic.ValidationError as exc:
            first_error = exc.errors()[0]
            raise BoxValidationError(first_error.get('msg', 'invalid sandbox_exec arguments')) from exc

        self._validate_host_mount(spec)
        self.ap.logger.info(
            'LangBot Box request: '
            f'query_id={query.query_id} '
            f'spec={json.dumps(self._summarize_spec(spec), ensure_ascii=False)}'
        )
        result = await self.runtime.execute(spec)
        self.ap.logger.info(
            'LangBot Box result: '
            f'query_id={query.query_id} '
            f'summary={json.dumps(self._summarize_result(result), ensure_ascii=False)}'
        )
        return self._serialize_result(result)

    async def shutdown(self):
        await self.runtime.shutdown()

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
        return f'{text[: self.output_limit_chars]}...', True

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
        box_config = getattr(self.ap, 'instance_config', None)
        box_config_data = getattr(box_config, 'data', {}) if box_config is not None else {}
        configured_roots = box_config_data.get('box', {}).get('allowed_host_mount_roots', [])

        normalized_roots: list[str] = []
        for root in configured_roots:
            root_value = str(root).strip()
            if not root_value:
                continue
            normalized_roots.append(os.path.realpath(os.path.abspath(root_value)))

        return normalized_roots

    def _load_default_host_workspace(self) -> str | None:
        box_config = getattr(self.ap, 'instance_config', None)
        box_config_data = getattr(box_config, 'data', {}) if box_config is not None else {}
        default_host_workspace = str(box_config_data.get('box', {}).get('default_host_workspace', '')).strip()
        if not default_host_workspace:
            return None
        return os.path.realpath(os.path.abspath(default_host_workspace))

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
