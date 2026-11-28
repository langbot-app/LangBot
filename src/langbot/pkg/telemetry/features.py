from __future__ import annotations

from . import trace

MAX_COUNTER = 65535
MAX_MODEL_BYTES = 128
COUNTERS = frozenset(
    {
        ('tool_calls', 'native'),
        ('tool_calls', 'plugin'),
        ('tool_calls', 'mcp'),
        ('tool_calls', 'skill'),
        ('sandbox', 'execs'),
        ('sandbox', 'errors'),
        ('kb', 'retrievals'),
        ('activated_skills', None),
        ('llm_calls', None),
    }
)


def bounded_model_name(value: str) -> str:
    return value.encode('utf-8')[:MAX_MODEL_BYTES].decode('utf-8', errors='ignore')


def _state(ap, query=None, execution_id: str = ''):
    from .execution import _execution_counters, current_execution_id

    counters = _execution_counters(ap)
    if counters is None or not counters._enabled() or trace.reporting_suppressed():
        return None
    state = trace.current()
    if state is None:
        session = getattr(query, '_agent_run_session', None)
        run_id = session.get('run_id', '') if isinstance(session, dict) else ''
        lookup = execution_id or run_id or current_execution_id() or getattr(query, 'query_uuid', '')
        if isinstance(lookup, str) and lookup:
            state = counters._resolve(lookup)
    if state is None or state.closed or not state.reportable:
        return None
    counters.configure(state)
    return state if state.mode != 'off' else None


def _increment(state, group: str, key: str | None) -> None:
    target = state.features if key is None else state.features.setdefault(group, {})
    name = group if key is None else key
    target[name] = min(target.get(name, 0) + 1, MAX_COUNTER)


def increment(ap, group: str, key: str | None = None, *, query=None, execution_id: str = '') -> None:
    try:
        if (group, key) not in COUNTERS:
            return
        state = _state(ap, query, execution_id)
        if state is not None:
            _increment(state, group, key)
    except Exception:
        pass


def note_llm(ap, model, query=None) -> None:
    try:
        state = _state(ap, query)
        if state is None:
            return
        if not state.model_name:
            state.model_name = bounded_model_name(model.model_entity.name or '')
        _increment(state, 'llm_calls', None)
    except Exception:
        pass
