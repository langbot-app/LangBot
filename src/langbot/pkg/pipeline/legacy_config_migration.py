"""Pure planning for explicitly requested legacy Pipeline migrations.

The candidate config is internal-only: never serialize it in a preview or log
it. ``ready`` means a config candidate, NOT permission to execute: installation,
resource ownership and existing conversation-state checks belong to the caller.
No IO, registry access, defaults from UI schemas, or runtime mutation occurs here.

Reviewed native source: 9b7ba0d64708496ace30a82866f6dbc185f089dc.
Reviewed official plugins: local parity patches over 678b18fd65af98230806c3b97b649514c83acea9.
Patch manifest versions below are required; version alone is not artifact proof.
"""

from __future__ import annotations

import copy
import json
import math
import re
from urllib.parse import urlsplit
from string import Formatter

PLANNER_VERSION = '5'

# Minimum reviewed plugin versions. The marketplace delists old releases, so the
# installer falls back to the latest release when a pin is gone; the Host then
# validates the emitted config against the installed runner schema.
_TARGETS = {
    'local-agent': ('LocalAgent', '0.2.1'),
    'dify-service-api': ('DifyAgent', '0.2.3'),
    'coze-api': ('CozeAgent', '0.2.0'),
    'dashscope-app-api': ('DashScopeAgent', '0.2.2'),
    'n8n-service-api': ('N8nAgent', '0.2.0'),
    'langflow-api': ('LangflowAgent', '0.2.2'),
    'deerflow-api': ('DeerFlowAgent', '0.2.1'),
    'tbox-app-api': ('TboxAgent', '0.2.1'),
    'weknora-api': ('WeKnoraAgent', '0.2.1'),
}
_DEERFLOW_FIELDS = {
    'api-base',
    'api-key',
    'auth-header',
    'assistant-id',
    'model-name',
    'thinking-enabled',
    'plan-mode',
    'subagent-enabled',
    'max-concurrent-subagents',
    'timeout',
    'recursion-limit',
}
_FIELDS = {
    'local-agent': {
        'model',
        'max-round',
        'prompt',
        'box-session-id-template',
        'rerank-model',
        'rerank-top-k',
        'enable-all-tools',
        'tools',
        'knowledge-bases',
        'knowledge-base',
        'mcp-resources',
        'mcp-resource-agent-read-enabled',
    },
    'dify-service-api': {'base-url', 'api-key', 'app-type', 'base-prompt', 'timeout'},
    'coze-api': {'api-key', 'bot-id', 'api-base', 'timeout', 'auto-save-history', 'auto_save_history'},
    'dashscope-app-api': {'app-type', 'api-key', 'app-id', 'references_quote', 'references-quote'},
    'n8n-service-api': {
        'webhook-url',
        'auth-type',
        'basic-username',
        'basic-password',
        'jwt-secret',
        'jwt-algorithm',
        'header-name',
        'header-value',
        'timeout',
        'output-key',
        'response-handling',
    },
    'langflow-api': {
        'base-url',
        'api-key',
        'flow-id',
        'input-type',
        'output-type',
        'input_type',
        'output_type',
        'tweaks',
    },
    'deerflow-api': _DEERFLOW_FIELDS,
    'tbox-app-api': {'api-key', 'app-id'},
    'weknora-api': {
        'base-url',
        'api-key',
        'app-type',
        'agent-id',
        'knowledge-base-ids',
        'web-search-enabled',
        'timeout',
        'base-prompt',
    },
}
_REQUIRED = {
    'local-agent': ('model', 'prompt'),
    'dify-service-api': ('base-url', 'api-key', 'app-type', 'base-prompt'),
    'coze-api': ('api-key', 'bot-id', 'api-base', 'timeout'),
    'dashscope-app-api': ('app-type', 'api-key', 'app-id'),
    'n8n-service-api': ('webhook-url',),
    'langflow-api': ('base-url', 'api-key', 'flow-id'),
    'deerflow-api': ('api-base',),
    'tbox-app-api': ('api-key', 'app-id'),
    'weknora-api': ('base-url', 'api-key', 'app-type'),
}
_BOOLEANS = {
    'enable-all-tools',
    'mcp-resource-agent-read-enabled',
    'auto-save-history',
    'auto_save_history',
    'thinking-enabled',
    'plan-mode',
    'subagent-enabled',
    'web-search-enabled',
}
_INTEGERS = {'max-round', 'rerank-top-k', 'max-concurrent-subagents', 'recursion-limit'}
_NAME_LISTS = {'tools', 'knowledge-bases', 'knowledge-base-ids'}
_DEERFLOW_DEFAULTS = {
    'api-key': '',
    'auth-header': '',
    'assistant-id': 'lead_agent',
    'model-name': '',
    'thinking-enabled': False,
    'plan-mode': False,
    'subagent-enabled': False,
    'max-concurrent-subagents': 3,
    'timeout': 300,
    'recursion-limit': 1000,
}
# Reviewed local patch manifests and implementations explicitly preserve native
# provider identity using trusted Host conversation fields; absent context fails
# closed in the plugin. Caller must verify the installed artifact/Host contract.
_IDENTITY_SOURCES = {
    'dify-service-api': 'legacy-session',
    'coze-api': 'legacy-session',
    'n8n-service-api': 'legacy-session',
    'tbox-app-api': 'legacy-bot',
}
_LOCAL_DEFAULTS = {
    'advanced-settings': False,
    'date-grounding': True,
    'timeout': 300,
    'retrieval-top-k': 5,
    'rerank-model': '',
    'rerank-top-k': 5,
    'max-tool-iterations': 100,
    'tool-execution-mode': 'serial',
    'max-tool-result-chars': 20000,
    'context-history-fetch-limit': 50,
    'context-window-tokens': 200000,
    'context-reserve-tokens': 16384,
    'context-keep-recent-tokens': 20000,
    'context-summary-tokens': 8000,
    'enable-all-tools': True,
    'tools': [],
    'knowledge-bases': [],
}
_DEFAULTS = {
    'local-agent': _LOCAL_DEFAULTS,
    'dify-service-api': {'timeout': 30, 'advanced-settings': False},
    'coze-api': {'auto-save-history': True, 'advanced-settings': False},
    'dashscope-app-api': {'references_quote': '参考资料来自:', 'timeout': 120, 'advanced-settings': False},
    'n8n-service-api': {
        'auth-type': 'none',
        'basic-username': '',
        'basic-password': '',
        'jwt-secret': '',
        'jwt-algorithm': 'HS256',
        'header-name': '',
        'header-value': '',
        'timeout': 120,
        'output-key': 'response',
        'response-handling': 'reply',
        'basic-encoding': 'latin1',
        'advanced-settings': False,
    },
    'langflow-api': {'input-type': 'chat', 'output-type': 'chat', 'tweaks': {}, 'advanced-settings': False},
    'deerflow-api': _DEERFLOW_DEFAULTS,
    'tbox-app-api': {'timeout': 120},
    'weknora-api': {
        'knowledge-base-ids': [],
        'web-search-enabled': False,
        'timeout': 120,
        'base-prompt': '请回答用户的问题。',
        'advanced-settings': False,
    },
}
# Missing values for these fields cannot be invented: they are credentials or
# endpoints. Everything else is repaired from reviewed 4.10 defaults.
_CRITICAL = {
    'local-agent': ('model',),
    'dify-service-api': ('base-url', 'api-key'),
    'coze-api': ('api-key', 'bot-id'),
    'dashscope-app-api': ('api-key', 'app-id'),
    'n8n-service-api': ('webhook-url',),
    'langflow-api': ('base-url', 'api-key', 'flow-id'),
    'deerflow-api': ('api-base',),
    'tbox-app-api': ('api-key', 'app-id'),
    'weknora-api': ('base-url', 'api-key'),
}
_LOCAL_PROMPT = [{'role': 'system', 'content': 'You are a helpful assistant.'}]
# 4.10 UI defaults for required, non-critical fields.
_FILL = {
    'local-agent': {'prompt': _LOCAL_PROMPT, 'box-session-id-template': '{launcher_type}_{launcher_id}'},
    'dify-service-api': {
        'app-type': 'chat',
        'base-prompt': (
            'When the file content is readable, please read the content of this file. '
            'When the file is an image, describe the content of this image.'
        ),
    },
    'coze-api': {'api-base': 'https://api.coze.cn', 'timeout': 120},
    'dashscope-app-api': {'app-type': 'agent'},
    'weknora-api': {'app-type': 'chat'},
}
_INT_TIMEOUT = {'deerflow-api', 'n8n-service-api', 'dify-service-api'}
_TIMEOUT_DEFAULT = {
    'dify-service-api': 30,
    'coze-api': 120,
    'dashscope-app-api': 120,
    'n8n-service-api': 120,
    'deerflow-api': 300,
    'tbox-app-api': 120,
    'weknora-api': 120,
    'local-agent': 300,
}
_ALIASES = {
    # legacy runner: (UI/hyphen key, alternate key, default when both missing)
    'coze-api': [('auto-save-history', 'auto_save_history')],
    'dashscope-app-api': [('references-quote', 'references_quote')],
    'langflow-api': [('input-type', 'input_type'), ('output-type', 'output_type')],
}
_ASSET_RUNNERS = {'dify-service-api', 'coze-api', 'dashscope-app-api', 'n8n-service-api', 'langflow-api'}
_REMOVE_THINK_RUNNERS = {'local-agent', 'dify-service-api', 'coze-api', 'dashscope-app-api', 'tbox-app-api'}
_REASONING_LEVELS = {'provider_default', 'disabled', 'enabled', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'}


def _strict_json(value, ancestors=None, depth=0):
    """Reject cycles, custom objects, nonfinite numbers and non-string keys."""
    if depth > 100:
        return False
    kind = type(value)
    if value is None or kind in (str, bool, int):
        return True
    if kind is float:
        return math.isfinite(value)
    if kind not in (dict, list):
        return False
    ancestors = set() if ancestors is None else ancestors
    identity = id(value)
    if identity in ancestors:
        return False
    ancestors.add(identity)
    try:
        if kind is dict:
            return all(type(k) is str and _strict_json(v, ancestors, depth + 1) for k, v in value.items())
        return all(_strict_json(v, ancestors, depth + 1) for v in value)
    finally:
        ancestors.remove(identity)


def _block(result, code, field):
    """Only developer-owned codes and paths may reach the public projection."""
    diagnostic = {'code': code, 'field': field}
    if diagnostic not in result['blockers']:
        result['blockers'].append(diagnostic)
    result['state'] = 'blocked'
    return result


def _names(value):
    return type(value) is list and all(type(item) is str and bool(item) for item in value)


def _attachments(value):
    return type(value) is list and all(
        type(item) is dict and ('enabled' not in item or type(item['enabled']) is bool) for item in value
    )


def _warn(result, code, field):
    diagnostic = {'code': code, 'field': field}
    if diagnostic not in result['warnings']:
        result['warnings'].append(diagnostic)


def _message_shape(value, shape, required=()):
    # SDK Message schemas, without importing runtime services or coercing values.
    return (
        type(value) is dict
        and not (set(value) - set(shape))
        and all(key in value for key in required)
        and all(check(value[key]) for key, check in shape.items() if key in value)
    )


def _valid_prompt(prompt):
    def string(value):
        return type(value) is str

    def optional_string(value):
        return value is None or string(value)

    def metadata(value):
        return value is None or type(value) is dict

    def content(value):
        if value is None or string(value):
            return True
        fields = {key: optional_string for key in ('text', 'image_base64', 'file_url', 'file_base64', 'file_name')}
        fields.update(type=string, image_url=lambda v: v is None or _message_shape(v, {'url': string}, ('url',)))
        return type(value) is list and all(_message_shape(v, fields, ('type',)) for v in value)

    def tools(value):
        fields = {
            'id': string,
            'type': string,
            'function': lambda v: _message_shape(v, {'name': string, 'arguments': string}, ('name', 'arguments')),
            'provider_specific_fields': metadata,
        }
        return value is None or (
            type(value) is list and all(_message_shape(v, fields, ('id', 'type', 'function')) for v in value)
        )

    fields = {key: optional_string for key in ('name', 'tool_call_id', 'resp_message_id')}
    fields.update(role=string, content=content, tool_calls=tools, provider_specific_fields=metadata)
    return type(prompt) is list and all(_message_shape(item, fields, ('role',)) for item in prompt)


_TRUE = {'true', '1', 'yes', 'on'}
_FALSE = {'false', '0', 'no', 'off'}
_CUSTOM_RUNNER_NAME = re.compile(r'[A-Za-z0-9_.\-]{1,64}')
_DEFAULT_BOX_TEMPLATE = '{launcher_type}_{launcher_id}'
_HEADER_NAME = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")


def _coerce(kind, value):
    """Best-effort, lossless coercion. Return (ok, value)."""
    if kind == 'bool':
        if type(value) is bool:
            return True, value
        if type(value) is int and value in (0, 1):
            return True, bool(value)
        if type(value) is str and value.strip().lower() in _TRUE:
            return True, True
        if type(value) is str and value.strip().lower() in _FALSE:
            return True, False
        return False, None
    if kind in ('int', 'number'):
        if type(value) is int:
            return True, value
        number = value
        if type(value) is str and value.strip():
            text = value.strip()
            try:
                return True, int(text)
            except ValueError:
                pass
            try:
                number = float(text)
            except ValueError:
                return False, None
        if type(number) is not float or not math.isfinite(number):
            return False, None
        if number.is_integer():
            return True, int(number)
        return (kind == 'number'), (number if kind == 'number' else None)
    if kind == 'names':
        if type(value) is str:
            return True, ([value.strip()] if value.strip() else [])
        if type(value) is list:
            return True, [v.strip() for v in value if type(v) is str and v.strip()]
        return False, None
    if kind == 'attachments':
        if type(value) is list:
            return True, [v for v in value if type(v) is dict and ('enabled' not in v or type(v['enabled']) is bool)]
        return False, None
    if type(value) is str:
        return True, value
    if type(value) in (int, float):
        return True, str(value)
    return False, None


def _kind(legacy, field):
    if field in _BOOLEANS:
        return 'bool'
    if field in _INTEGERS:
        return 'int'
    if field == 'timeout':
        return 'int' if legacy in _INT_TIMEOUT else 'number'
    if field in _NAME_LISTS:
        return 'names'
    if field == 'mcp-resources':
        return 'attachments'
    return 'str'


def _normalize_local(result, section):
    """Repair the LocalAgent model/prompt/template; never block on the model."""
    prefix = 'ai.local-agent'
    model = section.get('model')
    if type(model) is dict:
        if set(model) - {'primary', 'fallbacks', 'reasoning'}:
            _warn(result, 'migration.unknown_field_dropped', f'{prefix}.model')
        primary = model.get('primary')
        if type(primary) is not str:
            _warn(result, 'migration.missing_default_filled', f'{prefix}.model')
            primary = ''
        raw_fallbacks = model.get('fallbacks', [])
        ok, fallbacks = _coerce('names', raw_fallbacks)
        if not ok or fallbacks != raw_fallbacks:
            _warn(result, 'migration.value_coerced', f'{prefix}.model.fallbacks')
        reasoning = model.get('reasoning', {})
        if type(reasoning) is not dict:
            _warn(result, 'local.reasoning_dropped', f'{prefix}.model.reasoning')
            reasoning = {}
        valid = {k: v for k, v in reasoning.items() if type(v) is str and v in _REASONING_LEVELS}
        if len(valid) != len(reasoning):
            _warn(result, 'local.reasoning_dropped', f'{prefix}.model.reasoning')
        if valid:
            _warn(result, 'local.model_reasoning', f'{prefix}.model.reasoning')
        section['model'] = {'primary': primary, 'fallbacks': fallbacks or [], 'reasoning': valid}
    elif type(model) is str and model.strip():
        section['model'] = {'primary': model, 'fallbacks': [], 'reasoning': {}}
    else:
        # No usable model: migrate anyway; the user picks one after migration.
        _warn(result, 'migration.missing_default_filled', f'{prefix}.model')
        section['model'] = {'primary': '', 'fallbacks': [], 'reasoning': {}}
    prompt = section.get('prompt')
    if prompt is None:
        section['prompt'] = copy.deepcopy(_LOCAL_PROMPT)
        _warn(result, 'migration.missing_default_filled', f'{prefix}.prompt')
    elif type(prompt) is str:
        section['prompt'] = [{'role': 'system', 'content': prompt}]
        _warn(result, 'local.prompt_normalized', f'{prefix}.prompt')
    elif not _valid_prompt(prompt):
        kept = []
        if type(prompt) is list:
            for item in prompt:
                if type(item) is dict and type(item.get('role')) is str and type(item.get('content')) is str:
                    kept.append({'role': item['role'], 'content': item['content']})
        section['prompt'] = kept if kept and _valid_prompt(kept) else copy.deepcopy(_LOCAL_PROMPT)
        _warn(result, 'local.prompt_normalized', f'{prefix}.prompt')
    _warn(result, 'local.context_defaults', f'{prefix}.max-round')
    _warn(result, 'local.serial_tools_preserved', f'{prefix}.tools')
    _warn(result, 'local.retrieval_defaults', f'{prefix}.knowledge-bases')
    template = section.get('box-session-id-template', _DEFAULT_BOX_TEMPLATE)
    valid_template = type(template) is str and bool(template.strip())
    if valid_template:
        try:
            valid_template = not any(
                name is not None
                and (not name or name.isdecimal() or re.search(r'[.\[\]{}]', name) or spec or conversion)
                for _, name, spec, conversion in Formatter().parse(template)
            )
        except ValueError:
            valid_template = False
    if not valid_template:
        section['box-session-id-template'] = _DEFAULT_BOX_TEMPLATE
        _warn(result, 'local.box_template_defaulted', f'{prefix}.box-session-id-template')
    _warn(result, 'local.box_state_reset', f'{prefix}.box-session-id-template')


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate_key')
        result[key] = value
    return result


def _parse_tweaks(raw):
    if raw is None or (type(raw) is str and not raw.strip()):
        return {}
    decoded = json.loads(raw, object_pairs_hook=_unique_json_object) if type(raw) is str else raw
    if decoded is None:
        return {}
    if type(decoded) is not dict or not _strict_json(decoded):
        raise ValueError('invalid_tweaks')
    return decoded


def _default_for(legacy, field):
    for source in (_FILL.get(legacy, {}), _DEFAULTS[legacy]):
        if field in source:
            return True, copy.deepcopy(source[field])
    return False, None


def _normalize_external(result, legacy, section):
    prefix = f'ai.{legacy}'
    app_types = {
        'dify-service-api': ('chat', 'agent', 'workflow', 'chatflow'),
        'dashscope-app-api': ('agent', 'workflow'),
        'weknora-api': ('chat', 'agent'),
    }
    for field in _CRITICAL[legacy]:
        value = section.get(field)
        if type(value) is str and not value.strip():
            _block(result, 'invalid_value', f'{prefix}.{field}')
    if legacy in app_types and section.get('app-type') not in app_types[legacy]:
        section['app-type'] = _FILL[legacy]['app-type']
        _warn(result, 'migration.invalid_value_defaulted', f'{prefix}.app-type')
    if legacy == 'coze-api':
        base = section.get('api-base')
        try:
            parsed = urlsplit(base) if type(base) is str else None
            if (
                parsed is None
                or parsed.scheme not in ('http', 'https')
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
                or any(c.isspace() or ord(c) < 32 for c in base)
            ):
                raise ValueError
            _ = parsed.port
        except ValueError:
            _block(result, 'coze.custom_endpoint', f'{prefix}.api-base')
        _warn(result, 'coze.persistent_history', prefix)
    elif legacy == 'langflow-api':
        raw = section.get('tweaks')
        if raw is None or (type(raw) is str and (not raw.strip() or raw.strip() == 'null')):
            _warn(result, 'langflow.tweaks_default', f'{prefix}.tweaks')
        try:
            section['tweaks'] = copy.deepcopy(_parse_tweaks(raw))
        except (ValueError, RecursionError):
            section['tweaks'] = {}
            _warn(result, 'langflow.tweaks_invalid_defaulted', f'{prefix}.tweaks')
        _warn(result, 'langflow.persistent_history', prefix)
    elif legacy == 'dify-service-api':
        _warn(result, 'dify.timeout_default', f'{prefix}.timeout')
    elif legacy == 'n8n-service-api':
        auth_fields = {
            'none': (),
            'basic': ('basic-username', 'basic-password'),
            'jwt': ('jwt-secret',),
            'header': ('header-name', 'header-value'),
        }
        mode = section.get('auth-type', 'none')
        if mode not in auth_fields:
            mode = section['auth-type'] = 'none'
            _warn(result, 'migration.invalid_value_defaulted', f'{prefix}.auth-type')
        for field in auth_fields[mode]:
            if field not in section:
                _block(result, 'missing_field', f'{prefix}.{field}')
        if section.get('response-handling', 'reply') not in ('reply', 'ignore'):
            section['response-handling'] = 'reply'
            _warn(result, 'migration.invalid_value_defaulted', f'{prefix}.response-handling')
        if mode == 'basic':
            for field in ('basic-username', 'basic-password'):
                value = section.get(field)
                if type(value) is str:
                    try:
                        value.encode('latin1')
                        if field == 'basic-username' and ':' in value:
                            raise ValueError
                    except (UnicodeEncodeError, ValueError):
                        _block(result, 'n8n.basic_encoding', f'{prefix}.{field}')
        if mode == 'header' and type(section.get('header-name')) is str:
            if not _HEADER_NAME.fullmatch(section['header-name']):
                _block(result, 'n8n.header_name', f'{prefix}.header-name')
        _warn(result, 'n8n.session_ids_reset', prefix)
    elif legacy == 'deerflow-api':
        base = section.get('api-base')
        if type(base) is str and not base.strip().startswith(('http://', 'https://')):
            _block(result, 'invalid_value', f'{prefix}.api-base')


def _normalize_section(result, legacy, section):
    """Return a repaired copy of a legacy runner section (value-free diagnostics)."""
    prefix = f'ai.{legacy}'
    critical = _CRITICAL[legacy]
    if set(section) - _FIELDS[legacy]:
        _warn(result, 'migration.unknown_field_dropped', prefix)
    # Iterate only known keys, never put an arbitrary saved key in diagnostics.
    known = {k: copy.deepcopy(section[k]) for k in sorted(_FIELDS[legacy] & section.keys())}
    for preferred, other in _ALIASES.get(legacy, []):
        # The UI (hyphen) key wins; dashscope's plugin schema keeps the underscore.
        output = 'references_quote' if legacy == 'dashscope-app-api' else preferred
        drop = other if output == preferred else preferred
        if drop not in known:
            continue
        a, b = known.get(preferred), known.get(other)
        if a is not None and b is not None and a != b:
            _warn(result, 'migration.alias_conflict_resolved', f'{prefix}.{drop}')
        else:
            _warn(result, 'migration.alias_repaired', f'{prefix}.{drop}')
        known.pop(drop)
        known[output] = a if a is not None else b
    if legacy == 'coze-api' and known.get('auto-save-history') is None:
        known['auto-save-history'] = True
        _warn(result, 'migration.null_default', f'{prefix}.auto_save_history')
    for field in _REQUIRED[legacy]:
        if field not in known and field in critical:
            _block(result, 'missing_field', f'{prefix}.{field}')
    for field in sorted(known):
        value = known[field]
        if field in ('model', 'prompt', 'tweaks'):
            continue
        if value is None and legacy == 'weknora-api' and field in ('agent-id', 'knowledge-base-ids'):
            continue
        ok, coerced = (False, None) if value is None else _coerce(_kind(legacy, field), value)
        if ok and field == 'timeout' and coerced <= 0:
            ok = False
        if ok:
            if coerced != value or type(coerced) is not type(value):
                _warn(result, 'migration.value_coerced', f'{prefix}.{field}')
            known[field] = coerced
        elif field in critical:
            _block(result, 'invalid_type', f'{prefix}.{field}')
        else:
            known.pop(field)
            _warn(result, 'migration.invalid_value_defaulted', f'{prefix}.{field}')
    for field in _REQUIRED[legacy]:
        if field not in known and field not in critical:
            has_default, default = _default_for(legacy, field)
            if has_default:
                known[field] = default
                if field != 'prompt':
                    _warn(result, 'migration.missing_default_filled', f'{prefix}.{field}')
    if legacy == 'local-agent':
        _normalize_local(result, known)
    else:
        _normalize_external(result, legacy, known)
    return known


def _normalize_preferences(result, preferences, name):
    """Ignore malformed preference fields; return a patch only to bind the runner."""
    if preferences is None:
        return None
    if type(preferences) is not dict or not _strict_json(preferences):
        _warn(result, 'invalid_extension_preferences', 'extensions_preferences')
        return None
    for field in (
        'enable_all_plugins',
        'enable_all_mcp_servers',
        'enable_all_skills',
        'mcp_resource_agent_read_enabled',
    ):
        if field in preferences and type(preferences[field]) is not bool:
            _warn(result, 'invalid_extension_preferences', f'extensions_preferences.{field}')
    for field in ('mcp_servers', 'skills'):
        if field in preferences and not _names(preferences[field]):
            _warn(result, 'invalid_extension_preferences', f'extensions_preferences.{field}')
    if 'mcp_resources' in preferences and not _attachments(preferences['mcp_resources']):
        _warn(result, 'invalid_extension_preferences', 'extensions_preferences.mcp_resources')
    plugins = preferences.get('plugins', [])

    def valid(item):
        return type(item) is dict and all(type(item.get(k)) is str and item[k] for k in ('author', 'name'))

    kept = [item for item in plugins if valid(item)] if type(plugins) is list else []
    if type(plugins) is not list or len(kept) != len(plugins):
        _warn(result, 'invalid_extension_preferences', 'extensions_preferences.plugins')
    if preferences.get('enable_all_plugins', True) is False and not any(
        item['author'] == 'langbot-team' and item['name'] == name for item in kept
    ):
        # Bind exactly the migrated runner plugin; never flip allow-all.
        patched = copy.deepcopy(preferences)
        patched['plugins'] = [*copy.deepcopy(kept), {'author': 'langbot-team', 'name': name}]
        _warn(result, 'extensions.runner_added', 'extensions_preferences.plugins')
        return patched
    return None


def _normalize_output(result, config):
    output = config.get('output', {})
    if type(output) is not dict:
        _warn(result, 'migration.invalid_value_defaulted', 'output')
        return False
    misc = output.get('misc', {})
    if type(misc) is not dict:
        _warn(result, 'migration.invalid_value_defaulted', 'output.misc')
        return False
    value = misc.get('remove-think', False)
    ok, coerced = _coerce('bool', value)
    if not ok:
        _warn(result, 'migration.invalid_value_defaulted', 'output.misc.remove-think')
        return False
    if type(value) is not bool:
        _warn(result, 'migration.value_coerced', 'output.misc.remove-think')
    return coerced


def _assemble(result, legacy, section, remove_think, preferences):
    selected = {**copy.deepcopy(_DEFAULTS[legacy]), **copy.deepcopy(section)}
    prefix = f'ai.{legacy}'
    if legacy in _IDENTITY_SOURCES:
        selected['user-id-source'] = _IDENTITY_SOURCES[legacy]
    if legacy == 'local-agent':
        selected.pop('max-round', None)
        singular = selected.pop('knowledge-base', '')
        if not selected['knowledge-bases'] and type(singular) is str and singular and singular != '__none__':
            selected['knowledge-bases'] = [singular]
            _warn(result, 'migration.alias_repaired', f'{prefix}.knowledge-base')
        preferences = preferences if type(preferences) is dict else {}
        resources = preferences.get('mcp_resources', [])
        read = preferences.get('mcp_resource_agent_read_enabled', True)
        selected['mcp-resources'] = copy.deepcopy(
            section.get('mcp-resources', resources if _attachments(resources) else [])
        )
        selected['mcp-resource-agent-read-enabled'] = section.get(
            'mcp-resource-agent-read-enabled', read if type(read) is bool else True
        )
    else:
        selected.update(
            {
                'enable-all-tools': False,
                'tools': [],
                'knowledge-bases': [],
                'mcp-resources': [],
                'mcp-resource-agent-read-enabled': False,
            }
        )
    if legacy in _ASSET_RUNNERS:
        selected['langbot-assets-enabled'] = False
    if legacy in _REMOVE_THINK_RUNNERS:
        selected['remove-think'] = remove_think
        _warn(result, 'migration.output_policy_copied', 'output.misc.remove-think')
    if legacy == 'dify-service-api':
        selected['timeout'] = 30
    elif legacy == 'weknora-api':
        if selected.get('agent-id') is None:
            selected['agent-id'] = (
                'builtin-quick-answer' if selected['app-type'] == 'chat' else 'builtin-smart-reasoning'
            )
        if selected['knowledge-base-ids'] is None:
            selected['knowledge-base-ids'] = []
        _warn(result, 'weknora.session_title_changed', prefix)
    return selected


def plan_legacy_pipeline(config, extensions_preferences=None) -> dict:
    """Return a detached config candidate or safe, value-free diagnostics."""
    result = {
        'state': 'not_legacy',
        'legacy_runner': None,
        'target_runner_id': None,
        'target_plugin': None,
        'config': None,
        'extensions_preferences': None,
        'changed_paths': [],
        'blockers': [],
        'warnings': [],
    }
    if type(config) is not dict:
        return _block(result, 'invalid_type', 'config')
    if not _strict_json(config):
        return _block(result, 'invalid_json_value', 'config')
    ai = config.get('ai', {})
    if type(ai) is not dict:
        return _block(result, 'invalid_type', 'ai')
    selection = ai.get('runner', {})
    if type(selection) is not dict:
        return _block(result, 'invalid_type', 'ai.runner')
    legacy = selection.get('runner')
    known_legacy = type(legacy) is str and legacy in _TARGETS
    if 'id' in selection:
        current = selection['id']
        valid_id = type(current) is str and bool(re.fullmatch(r'plugin:[^/\s]+/[^/\s]+/[^/\s]+', current))
        if 'runner' in selection:
            # Prefer a valid current id; otherwise migrate the legacy selection.
            if valid_id:
                _warn(result, 'migration.mixed_runner_selection', 'ai.runner')
                result['state'] = 'already_current'
                return result
            if not known_legacy:
                return _block(result, 'mixed_runner_selection', 'ai.runner')
            _warn(result, 'migration.mixed_runner_selection', 'ai.runner')
        else:
            # A blank runner id paired with no legacy runner section means the
            # saved pipeline simply has no runner selected: nothing to migrate.
            if type(current) is str and not current.strip() and not any(name in ai for name in _TARGETS):
                return result
            if not valid_id:
                return _block(result, 'invalid_runner_id', 'ai.runner.id')
            result['state'] = 'already_current'
            return result
    if 'runner' not in selection:
        return result
    if type(legacy) is not str:
        return _block(result, 'invalid_type', 'ai.runner.runner')
    if not known_legacy:
        if not legacy.strip():
            return result
        # 4.10 allowed in-tree custom runners (@runner_class). They have no
        # plugin equivalent; report them without failing other pipelines.
        result.update(
            state='unsupported_runner',
            legacy_runner=legacy if _CUSTOM_RUNNER_NAME.fullmatch(legacy) else None,
        )
        _warn(result, 'legacy.custom_runner_unsupported', 'ai.runner.runner')
        return result
    name, version = _TARGETS[legacy]
    target = f'plugin:langbot-team/{name}/default'
    result.update(
        legacy_runner=legacy,
        target_runner_id=target,
        target_plugin={'author': 'langbot-team', 'name': name, 'version': version},
    )
    if 'runner_config' in ai and (type(ai['runner_config']) is not dict or ai['runner_config']):
        _warn(result, 'migration.runner_config_replaced', 'ai.runner_config')
    expiry = selection.get('expire-time', 0)
    ok, expiry_value = _coerce('int', expiry)
    if not ok or expiry_value < 0:
        expiry_value = 0
        _warn(result, 'migration.invalid_value_defaulted', 'ai.runner.expire-time')
    elif type(expiry) is not int:
        _warn(result, 'migration.value_coerced', 'ai.runner.expire-time')
    if set(ai) - set(_TARGETS) - {'runner', 'runner_config'}:
        _warn(result, 'migration.unknown_section_archived', 'ai')
    if set(selection) - {'runner', 'expire-time', 'id'}:
        _warn(result, 'migration.unknown_field_dropped', 'ai.runner')
    if legacy not in ai:
        return _block(result, 'missing_field', f'ai.{legacy}')
    section = ai[legacy]
    if type(section) is not dict:
        return _block(result, 'invalid_type', f'ai.{legacy}')
    section = _normalize_section(result, legacy, section)
    patched_preferences = _normalize_preferences(result, extensions_preferences, name)
    remove_think = _normalize_output(result, config)
    _warn(result, 'external.state_validation_required', 'ai.runner')
    _warn(result, 'migration.history_reset', 'ai.runner')
    _warn(result, 'migration.new_defaults', f'ai.{legacy}')
    _warn(result, 'migration.legacy_sections_archived', 'ai')
    if legacy in ('dify-service-api', 'dashscope-app-api', 'n8n-service-api'):
        _warn(result, 'migration.filtered_variables', f'ai.{legacy}')
    if legacy in _IDENTITY_SOURCES:
        _warn(result, 'migration.identity_preserved', f'ai.{legacy}')
    if result['blockers']:
        return result
    selected = _assemble(result, legacy, section, remove_think, extensions_preferences)
    candidate = copy.deepcopy(config)
    # The durable snapshot stores the full source, including inactive legacy
    # credentials and unknown leftovers. The active configuration is canonical.
    candidate['ai'] = {
        'runner': {'id': target, 'expire-time': expiry_value},
        'runner_config': {target: selected},
    }
    archived_paths = [f'ai.{old}' for old in _TARGETS if old in ai]
    changed = ['ai.runner.runner', 'ai.runner.id', 'ai.runner_config', *archived_paths]
    if patched_preferences is not None:
        changed.append('extensions_preferences.plugins')
    result.update(
        state='ready',
        config=candidate,
        extensions_preferences=patched_preferences,
        changed_paths=changed,
    )
    return result
