"""Bound-resource reporting for one execution.

Answers "what was this execution given", never "what did it use": the ids and
names of the Plugins, MCP servers, knowledge bases, tools, skills and models
that were bound or granted to a Pipeline lane or an Agent run. Nothing here is
user content - only code-defined identifiers (uuids, plugin names, tool names)
and booleans.

Two sources feed one execution-scoped snapshot:

* the Host policy actually granted to the run (``ResourcePolicy`` /
  materialized ``AgentResources``), which is authoritative for tools, skills and
  platform APIs;
* the Runner's own configuration form (``DynamicFormItemSchema``), which is
  where knowledge bases and models are selected. Selector field types are read
  through :mod:`langbot.pkg.agent.runner.config_schema`, so a Runner that
  declares a new selector type is picked up without a change here.

The snapshot is attached to the terminal ``execution_chain`` record. It is
bounded twice - per list and in total - and it is best effort: telemetry must
never change execution behaviour, so every entry point swallows failures.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import typing

MAX_ITEMS_PER_LIST = 64
MAX_NAME_CHARS = 160
MAX_RESOURCES_BYTES = 8 * 1024

_resources: contextvars.ContextVar[dict[str, typing.Any] | None] = contextvars.ContextVar(
    'telemetry_resources', default=None
)


def begin() -> None:
    """Start collecting for one execution (called when a chain is opened)."""
    _resources.set({})


def end() -> None:
    """Stop collecting; the snapshot has already been read."""
    _resources.set(None)


def _bucket(section: str) -> dict[str, typing.Any] | None:
    root = _resources.get()
    if root is None:
        return None
    bucket = root.get(section)
    if not isinstance(bucket, dict):
        bucket = {}
        root[section] = bucket
    return bucket


def _names(values: typing.Any) -> list[str]:
    """Bound one list of code-defined identifiers, preserving source order."""
    if not isinstance(values, (list, tuple)):
        return []
    names: list[str] = []
    seen: set[str] = set()
    for value in values:
        name = ''
        if isinstance(value, str):
            name = value
        elif isinstance(value, dict):
            name = str(value.get('name') or value.get('kb_id') or value.get('tool_name') or '')
        if not name:
            continue
        name = name[:MAX_NAME_CHARS]
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
        if len(names) >= MAX_ITEMS_PER_LIST:
            break
    return names


def _tool_refs(values: typing.Any) -> list[dict[str, str]]:
    """Bound one list of tool grants, keeping their Host source."""
    if not isinstance(values, (list, tuple)):
        return []
    refs: list[dict[str, str]] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, str):
            name, source, source_id = value, '', ''
        elif isinstance(value, dict):
            name = str(value.get('tool_name') or value.get('name') or '')
            source = str(value.get('tool_type') or value.get('source') or '')
            raw_id = value.get('source_id')
            source_id = raw_id if isinstance(raw_id, str) else ''
        else:
            continue
        name = name[:MAX_NAME_CHARS]
        if not name or name in seen:
            continue
        seen.add(name)
        ref = {'name': name}
        if source:
            ref['source'] = source[:64]
        if source_id:
            ref['source_id'] = source_id[:MAX_NAME_CHARS]
        refs.append(ref)
        if len(refs) >= MAX_ITEMS_PER_LIST:
            break
    return refs


def _set(bucket: dict[str, typing.Any] | None, key: str, value: typing.Any) -> None:
    if bucket is None or value in (None, [], {}, ''):
        return
    bucket[key] = value


def note_pipeline(
    *,
    plugins: typing.Any = None,
    plugins_all: typing.Any = None,
    mcp_servers: typing.Any = None,
    mcp_all: typing.Any = None,
    knowledge_bases: typing.Any = None,
    skills: typing.Any = None,
    tools: typing.Any = None,
    tools_all: typing.Any = None,
    runner_id: str = '',
    selectors: typing.Any = None,
) -> None:
    """Record the resources one Pipeline lane is bound to.

    ``plugins``/``mcp_servers`` accept ``None`` to mean "all enabled", matching
    the binding model; the ``*_all`` flags make that explicit in the payload.
    """
    try:
        bucket = _bucket('pipeline')
        if bucket is None:
            return
        _set(bucket, 'plugins', _names(plugins))
        _set(bucket, 'mcp_servers', _names(mcp_servers))
        _set(bucket, 'knowledge_bases', _names(knowledge_bases))
        _set(bucket, 'skills', _names(skills))
        _set(bucket, 'tools', _tool_refs(tools))
        _set(bucket, 'runner_id', str(runner_id or '')[:MAX_NAME_CHARS])
        if isinstance(selectors, dict):
            cleaned = {
                str(kind)[:64]: _names(fields)
                for kind, fields in selectors.items()
                if isinstance(fields, (list, tuple)) and fields
            }
            _set(bucket, 'selectors', cleaned)
        if plugins_all is not None:
            bucket['plugins_all'] = bool(plugins_all)
        if mcp_all is not None:
            bucket['mcp_all'] = bool(mcp_all)
        if tools_all is not None:
            bucket['tools_all'] = bool(tools_all)
    except Exception:
        return


def note_agent(
    *,
    runner_id: str = '',
    resources: typing.Any = None,
    selectors: typing.Any = None,
    capabilities: typing.Any = None,
    tools_all: typing.Any = None,
) -> None:
    """Record the resources one Agent run was granted.

    ``resources`` is the materialized ``AgentResources`` mapping the Host
    actually handed to the Runner (tools carry their source), ``selectors``
    names the Runner config-form fields that selected a resource, and
    ``capabilities`` records which resource categories the Runner declared.
    """
    try:
        bucket = _bucket('agent')
        if bucket is None:
            return
        _set(bucket, 'runner_id', str(runner_id or '')[:MAX_NAME_CHARS])
        if isinstance(resources, dict):
            _set(bucket, 'knowledge_bases', _names(resources.get('knowledge_bases')))
            _set(bucket, 'skills', _names(resources.get('skills')))
            _set(bucket, 'models', _names(resources.get('models')))
            _set(bucket, 'tools', _tool_refs(resources.get('tools')))
            _set(bucket, 'platform_apis', _names(resources.get('platform_tools')))
        if isinstance(selectors, dict):
            cleaned = {
                str(kind)[:64]: _names(fields)
                for kind, fields in selectors.items()
                if isinstance(fields, (list, tuple)) and fields
            }
            _set(bucket, 'selectors', cleaned)
        if isinstance(capabilities, dict):
            declared = {key: bool(value) for key, value in capabilities.items() if value}
            _set(bucket, 'capabilities', declared)
        if tools_all is not None:
            bucket['tools_all'] = bool(tools_all)
    except Exception:
        return


def snapshot() -> dict[str, typing.Any] | None:
    """Return the bounded snapshot of this execution; None when nothing was noted."""
    try:
        root = _resources.get()
        if not isinstance(root, dict) or not root:
            return None

        def encoded_size(value: typing.Any) -> int:
            return len(json.dumps(value, ensure_ascii=False, default=str).encode('utf-8'))

        if encoded_size(root) <= MAX_RESOURCES_BYTES:
            return root
        # Over budget: shed the widest detail (per-tool grants) first, then fall
        # back to a marker, so an oversized binding can never block the chain
        # record or bloat the upload.
        reduced = json.loads(json.dumps(root, ensure_ascii=False, default=str))
        for section in ('pipeline', 'agent'):
            bucket = reduced.get(section)
            if isinstance(bucket, dict):
                bucket.pop('tools', None)
        reduced['truncated'] = True
        if encoded_size(reduced) <= MAX_RESOURCES_BYTES:
            return reduced
        return {'truncated': True}
    except Exception:
        return None


@contextlib.contextmanager
def collected() -> typing.Iterator[None]:
    """Bind a collection scope, for callers outside an execution boundary."""
    token = _resources.set({})
    try:
        yield
    finally:
        _resources.reset(token)
