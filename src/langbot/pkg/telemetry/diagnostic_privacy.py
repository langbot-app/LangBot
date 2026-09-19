"""Closed, content-free projection for Beta diagnostics; never serialize payloads."""

from __future__ import annotations

import builtins
import hashlib
import math
import re
from uuid import UUID

KINDS = frozenset('lifecycle event route run api delivery interaction capability transport summary'.split())
SOURCES = frozenset(
    'platform pipeline agent event_processor webui_debug http websocket mcp plugin runtime startup internal synthetic'.split()
)
OUTCOMES = frozenset('started succeeded failed cancelled timeout skipped rejected waiting partial unknown'.split())
PROCESSORS = frozenset(('', 'pipeline', 'agent', 'event_processor'))
# These sets are populated ONLY by source-code decorators / packaged manifests,
# never by requests, installed third-party plugin declarations or configuration.
VOCABULARY: dict[str, set[str]] = {
    'operation': {'diagnostics.transport', 'startup', 'route.primary', 'route.subscription', 'runner.run'},
    'stage': {'execute', 'prepare', 'convert', 'dispatch', 'accepted', 'ack', 'resume', 'shutdown', 'snapshot'},
    'adapter': set(),
    'platform_event_type': set(),
    'reason_code': set(
        'runner_failed response_error route_not_found processor_incompatible processor_not_found discarded not_matched matched delivered waiting interaction_rejected generator_closed transport_loss'.split()
    ),
    'capability_type': {'event', 'api', 'processor'},
    'tool_category': {'native', 'plugin', 'mcp', 'skill', 'platform', 'unknown'},
    'transport': {'stdio', 'websocket', 'http', 'unknown'},
    'runner_usage': {'agent', 'event'},
    'os': {'linux', 'darwin', 'windows'},
    'arch': {'x86_64', 'aarch64', 'arm64', 'amd64'},
    'database': {'sqlite', 'postgresql'},
    'edition': {'community', 'cloud', 'enterprise'},
    'chat_type': {'person', 'group', 'unknown'},
    'content_type': {'text', 'image', 'audio', 'video', 'file', 'mixed', 'other', 'unknown'},
}
BOOLS = frozenset(
    'stream synthetic configured available previous_session_unclean recovered supported adapter_evidence listener_registered'.split()
)
NUMBERS = frozenset(
    'attempts successes failures cancellations timeouts partial unknown generated queued acked dropped retried failed queue_size capacity result_count input_tokens output_tokens'.split()
)
VERSIONS = frozenset('sdk_version plugin_version runner_version python_version'.split())


def code_value(field: str, value: str) -> str:
    """Register a literal from trusted Core source, not a runtime string."""
    VOCABULARY.setdefault(field, set()).add(value)
    return value


def category(field: str, value) -> str:
    return value if type(value) is str and value in VOCABULARY.get(field, ()) else ''


def opaque(value) -> str:
    if not isinstance(value, str):
        return ''
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        return ''


def version_string(value) -> str:
    # Public package versions only; do not permit arbitrary PEP440 local labels.
    return value if isinstance(value, str) and re.fullmatch(r'[0-9][0-9.abrcdevpost-]{0,47}', value) else ''


def attributes(values) -> dict:
    if not isinstance(values, dict):
        return {}
    result = {}
    for key, value in values.items():
        if key in BOOLS and type(value) is bool:
            result[key] = value
        elif key in NUMBERS and type(value) is int and math.isfinite(value) and 0 <= value <= 1_000_000:
            result[key] = value
        elif key in VERSIONS and version_string(value):
            result[key] = value
        elif key in VOCABULARY and key not in {'operation', 'stage', 'adapter', 'platform_event_type', 'reason_code'}:
            if category(key, value):
                result[key] = value
        elif key == 'capability_name' and any(category(f, value) for f in ('operation', 'platform_event_type')):
            result[key] = value
        elif key == 'capability_name' and value in PROCESSORS - {''}:
            result[key] = value
        elif key in ('event_types', 'api_operations', 'processor_types') and isinstance(value, (tuple, list)):
            allowed = (
                VOCABULARY['platform_event_type']
                if key == 'event_types'
                else VOCABULARY['operation']
                if key == 'api_operations'
                else PROCESSORS
            )
            result[key] = [v for v in value[:128] if type(v) is str and v in allowed]
        elif (
            key in ('source_revision', 'target_revision')
            and isinstance(value, str)
            and re.fullmatch('[a-f0-9]{40}', value)
        ):
            result[key] = value
        elif key == 'latency_buckets' and isinstance(value, (list, tuple)):
            result[key] = [v for v in value[:128] if type(v) is int and 0 <= v <= 1_000_000]
    return result


def error_fields(error: BaseException, operation: str, stage: str) -> dict:
    cls = type(error)
    # Third party exception names may be dynamically constructed from input.
    name = cls.__name__ if getattr(builtins, cls.__name__, None) is cls else 'Exception'
    if isinstance(error, TimeoutError):
        name = 'TimeoutError'
    # No message, traceback, filename, line number, or locals are inspected.
    fingerprint = hashlib.sha256(f'{operation}|{stage}|{cls.__module__}|{cls.__qualname__}'.encode()).hexdigest()
    return {'error_type': name, 'error_fingerprint': fingerprint}
