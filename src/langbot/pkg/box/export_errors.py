"""Bounded export diagnostics preserved by the SDK's text-only error relay."""

from __future__ import annotations

import json
import re

from langbot_plugin.api.entities.builtin.runner.errors import AgentAPIError
from langbot_plugin.box.errors import BoxValidationError


EXPORT_ERROR_PREFIX = 'LANGBOT_EXPORT_V1:'
SCRIPT_ERROR_PREFIX = 'LANGBOT_OUTBOX_LIMIT:'
SCRIPT_ERROR_EXIT_CODE = 73
LIMIT_LABELS = {
    'file_bytes': 'per-file byte',
    'collection_bytes': 'total-byte',
    'file_count': 'file-count',
    'depth': 'directory-depth',
    'entries': 'directory-entry',
    'directories': 'directory',
    'run_files': 'per-run file-count',
    'run_bytes': 'per-run byte',
}


class BoxExportError(BoxValidationError):
    def __init__(self, error: AgentAPIError):
        self.error = error
        super().__init__(EXPORT_ERROR_PREFIX + error.model_dump_json())


def export_error(
    kind: str,
    *,
    limit: int | None = None,
    actual: int | None = None,
    path: str = '',
    lower_bound: bool = False,
    remaining: int | None = None,
    absolute_path: bool = False,
) -> BoxExportError:
    if kind in LIMIT_LABELS:
        code = 'box.export.limit_exceeded'
        message = f'Attachment export failed: Sandbox outbox exceeds the {LIMIT_LABELS[kind]} limit'
        action = 'Reduce or split the requested output within the indicated limit, then retry export.'
        if kind in {'depth', 'entries', 'directories'}:
            action = 'Flatten the outbox or remove unnecessary entries, preserving the requested deliverables.'
    elif kind == 'transport_bytes':
        code = 'box.export.transport_truncated'
        message = 'Attachment export failed: the SDK explicitly reported truncated export output'
        action = 'Reduce or split attachments so their base64/JSON response fits the transport limit.'
    elif kind == 'invalid_response':
        code = 'box.export.invalid_response'
        message = 'Attachment export failed: Sandbox outbox returned invalid attachment data'
        action = 'Inspect the sandbox/runtime response; do not assume a size limit caused this failure.'
    else:
        raise ValueError(f'Unknown export failure kind: {kind}')
    return BoxExportError(
        AgentAPIError(
            code=code,
            message=message,
            retryable=kind != 'invalid_response',
            details={
                'version': 1,
                'phase': 'export',
                'limit_type': kind,
                'limit': limit,
                'actual': actual,
                'actual_is_lower_bound': lower_bound,
                'remaining': remaining,
                'relative_paths': [path] if path and not absolute_path else [],
                'sandbox_paths': [path] if path and absolute_path else [],
                'files_retained': True,
                'suggested_action': action,
            },
        )
    )


def script_export_error(
    stderr: str, exit_code: int, limits: dict[str, int], *, selected_paths: list[str] | None = None
) -> BoxExportError | None:
    if exit_code != SCRIPT_ERROR_EXIT_CODE or len(stderr) > 8192:
        return None
    line = stderr.strip().splitlines()[-1] if stderr.strip() else ''
    if not line.startswith(SCRIPT_ERROR_PREFIX):
        return None
    try:
        value = json.loads(line.removeprefix(SCRIPT_ERROR_PREFIX))
        kind, limit, actual, path = (value[k] for k in ('kind', 'limit', 'actual', 'path'))
        if (
            kind not in limits
            or type(limit) is not int
            or limit != limits[kind]
            or type(actual) is not int
            or actual <= limit
            or not isinstance(path, str)
            or len(path) > 2400
            or (selected_paths is None and path.startswith('/'))
            or (selected_paths is not None and path not in selected_paths)
            or '\\' in path
            or '\x00' in path
            or '..' in path.split('/')
        ):
            return None
        return export_error(
            kind, limit=limit, actual=actual, path=path, lower_bound=True, absolute_path=selected_paths is not None
        )
    except (ValueError, TypeError, KeyError):
        return None


def transport_export_error(stdout: str) -> BoxExportError | None:
    clipped = re.search(r'\n\.\.\. \[raw output clipped at (\d+) bytes, (\d+) bytes discarded\]$', stdout)
    if clipped:
        limit, discarded = map(int, clipped.groups())
        if limit > 0 and discarded > 0:
            return export_error('transport_bytes', limit=limit, actual=limit + discarded)
    clipped = re.search(r'\n\.\.\. \[output clipped at (\d+) bytes\]$', stdout)
    if clipped and int(clipped[1]) > 0:
        return export_error('transport_bytes', limit=int(clipped[1]))
    return None
