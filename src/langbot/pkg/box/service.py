from __future__ import annotations

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

    async def initialize(self):
        await self.runtime.initialize()

    async def execute_sandbox_tool(self, parameters: dict, query: 'pipeline_query.Query') -> dict:
        spec_payload = dict(parameters)
        spec_payload.setdefault('session_id', str(query.query_id))
        spec_payload.setdefault('env', {})

        try:
            spec = BoxSpec.model_validate(spec_payload)
        except pydantic.ValidationError as exc:
            first_error = exc.errors()[0]
            raise BoxValidationError(first_error.get('msg', 'invalid sandbox_exec arguments')) from exc

        result = await self.runtime.execute(spec)
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
