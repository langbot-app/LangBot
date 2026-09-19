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

PLANNER_VERSION = '3'

_TARGETS = {
    'local-agent': ('LocalAgent', '0.1.7'),
    'dify-service-api': ('DifyAgent', '0.1.7'),
    'coze-api': ('CozeAgent', '0.1.7'),
    'dashscope-app-api': ('DashScopeAgent', '0.1.7'),
    'n8n-service-api': ('N8nAgent', '0.1.7'),
    'langflow-api': ('LangflowAgent', '0.1.7'),
    'deerflow-api': ('DeerFlowAgent', '0.1.7'),
    'tbox-app-api': ('TboxAgent', '0.1.5'),
    'weknora-api': ('WeKnoraAgent', '0.1.7'),
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


def _validate_preferences(result, preferences, name):
    if preferences is None:
        return
    if type(preferences) is not dict or not _strict_json(preferences):
        _block(result, 'invalid_extension_preferences', 'extensions_preferences')
        return
    for field in (
        'enable_all_plugins',
        'enable_all_mcp_servers',
        'enable_all_skills',
        'mcp_resource_agent_read_enabled',
    ):
        if field in preferences and type(preferences[field]) is not bool:
            _block(result, 'invalid_extension_preferences', f'extensions_preferences.{field}')
    for field in ('mcp_servers', 'skills'):
        if field in preferences and not _names(preferences[field]):
            _block(result, 'invalid_extension_preferences', f'extensions_preferences.{field}')
    if 'mcp_resources' in preferences and not _attachments(preferences['mcp_resources']):
        _block(result, 'invalid_extension_preferences', 'extensions_preferences.mcp_resources')
    plugins = preferences.get('plugins', [])
    if type(plugins) is not list or not all(
        type(item) is dict and all(type(item.get(k)) is str and item[k] for k in ('author', 'name')) for item in plugins
    ):
        _block(result, 'invalid_extension_preferences', 'extensions_preferences.plugins')
    elif preferences.get('enable_all_plugins', True) is False and not any(
        item['author'] == 'langbot-team' and item['name'] == name for item in plugins
    ):
        # The immutable result contract contains no extension-preference patch.
        # Require explicit binding instead of silently flipping allow-all.
        _block(result, 'extensions.runner_excluded', 'extensions_preferences.plugins')


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


def _validate_local(result, section):
    prefix = 'ai.local-agent'
    model = section.get('model')
    if type(model) is dict:
        if set(model) - {'primary', 'fallbacks', 'reasoning'}:
            _block(result, 'unknown_field', f'{prefix}.model')
        if type(model.get('primary')) is not str or not model['primary'] or not _names(model.get('fallbacks', [])):
            _block(result, 'invalid_type', f'{prefix}.model')
        reasoning = model.get('reasoning', {})
        if type(reasoning) is not dict or not all(type(v) is str for v in reasoning.values()):
            _block(result, 'invalid_type', f'{prefix}.model.reasoning')
        elif any(value not in _REASONING_LEVELS for value in reasoning.values()):
            _block(result, 'local.reasoning_value', f'{prefix}.model')
        elif reasoning:
            _warn(result, 'local.model_reasoning', f'{prefix}.model.reasoning')
    elif type(model) is not str or not model:
        _block(result, 'invalid_type', f'{prefix}.model')
    if not _valid_prompt(section.get('prompt')):
        _block(result, 'local.prompt_shape', f'{prefix}.prompt')
    _warn(result, 'local.context_defaults', f'{prefix}.max-round')
    _warn(result, 'local.serial_tools_preserved', f'{prefix}.tools')
    _warn(result, 'local.retrieval_defaults', f'{prefix}.knowledge-bases')
    template = section.get('box-session-id-template', '{launcher_type}_{launcher_id}')
    if type(template) is not str or not template.strip():
        _block(result, 'local.box_template_invalid', f'{prefix}.box-session-id-template')
    else:
        try:
            fields = list(Formatter().parse(template))
            if any(
                name is not None
                and (not name or name.isdecimal() or re.search(r'[.\[\]{}]', name) or spec or conversion)
                for _, name, spec, conversion in fields
            ):
                raise ValueError('Only named interpolation variables are supported')
        except ValueError:
            _block(result, 'local.box_template_invalid', f'{prefix}.box-session-id-template')
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


def _validate_external(result, legacy, section):
    prefix = f'ai.{legacy}'
    app_types = {
        'dify-service-api': ('chat', 'agent', 'workflow', 'chatflow'),
        'dashscope-app-api': ('agent', 'workflow'),
        'weknora-api': ('chat', 'agent'),
    }
    required_strings = {
        'dify-service-api': ('api-key', 'base-url'),
        'coze-api': ('api-key', 'bot-id'),
        'dashscope-app-api': ('api-key', 'app-id'),
        'n8n-service-api': ('webhook-url',),
        'langflow-api': ('base-url', 'api-key', 'flow-id'),
        'tbox-app-api': ('api-key', 'app-id'),
        'weknora-api': ('api-key', 'base-url'),
    }
    for field in required_strings.get(legacy, ()):
        value = section.get(field)
        if type(value) is str and (not value or (legacy == 'weknora-api' and not value.strip())):
            _block(result, 'invalid_value', f'{prefix}.{field}')
    if legacy in app_types and 'app-type' in section and section['app-type'] not in app_types[legacy]:
        _block(result, 'invalid_value', f'{prefix}.app-type')
    if legacy == 'coze-api':
        actual, alias = section.get('auto_save_history'), section.get('auto-save-history')
        if type(actual) is bool and type(alias) is bool and actual != alias:
            _block(result, 'coze.history_alias', f'{prefix}.auto_save_history')
        if 'auto_save_history' in section or 'auto-save-history' in section:
            _warn(result, 'migration.alias_repaired', f'{prefix}.auto_save_history')
        if actual is None and alias is None:
            _warn(result, 'migration.null_default', f'{prefix}.auto_save_history')
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
    elif legacy == 'dashscope-app-api':
        if 'references-quote' in section:
            if 'references_quote' in section and section['references_quote'] != section['references-quote']:
                _block(result, 'dashscope.references_alias', f'{prefix}.references_quote')
            else:
                _warn(result, 'migration.alias_repaired', f'{prefix}.references-quote')
    elif legacy == 'langflow-api':
        for axis in ('input', 'output'):
            actual, ui = f'{axis}_type', f'{axis}-type'
            if ui in section and section[ui] != section.get(actual, 'chat'):
                _block(result, 'langflow.io_alias', f'{prefix}.{actual}')
            if actual in section:
                _warn(result, 'migration.alias_repaired', f'{prefix}.{actual}')
        try:
            _parse_tweaks(section.get('tweaks'))
        except (ValueError, RecursionError):
            _block(result, 'langflow.invalid_tweaks', f'{prefix}.tweaks')
        if section.get('tweaks') is None or (
            type(section.get('tweaks')) is str
            and (not section['tweaks'].strip() or section['tweaks'].strip() == 'null')
        ):
            _warn(result, 'langflow.tweaks_default', f'{prefix}.tweaks')
        _warn(result, 'langflow.persistent_history', prefix)
    elif legacy == 'dify-service-api':
        _warn(result, 'dify.timeout_default', f'{prefix}.timeout')
    elif legacy == 'n8n-service-api':
        mode = section.get('auth-type', 'none')
        auth_fields = {
            'none': (),
            'basic': ('basic-username', 'basic-password'),
            'jwt': ('jwt-secret',),
            'header': ('header-name', 'header-value'),
        }
        if type(mode) is not str or mode not in auth_fields:
            _block(result, 'invalid_value', f'{prefix}.auth-type')
        else:
            for field in auth_fields[mode]:
                if field not in section:
                    _block(result, 'missing_field', f'{prefix}.{field}')
        response = section.get('response-handling', 'reply')
        if response not in ('reply', 'ignore'):
            _block(result, 'invalid_value', f'{prefix}.response-handling')
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
            if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", section['header-name']):
                _block(result, 'n8n.header_name', f'{prefix}.header-name')
        _warn(result, 'n8n.session_ids_reset', prefix)
    elif legacy == 'weknora-api':
        knowledge = section.get('knowledge-base-ids')
        if type(knowledge) is list and any(type(v) is str and not v.strip() for v in knowledge):
            _block(result, 'invalid_value', f'{prefix}.knowledge-base-ids')
    if legacy in ('coze-api', 'n8n-service-api', 'weknora-api'):
        timeout = section.get('timeout', 120)
        if type(timeout) in (int, float) and timeout <= 0:
            _block(result, 'invalid_value', f'{prefix}.timeout')


def _validate_section(result, legacy, section):
    prefix = f'ai.{legacy}'
    if set(section) - _FIELDS[legacy]:
        _block(result, 'unknown_field', prefix)
    for field in _REQUIRED[legacy]:
        if field not in section:
            _block(result, 'missing_field', f'{prefix}.{field}')
    # Iterate only known keys, never put an arbitrary saved key in diagnostics.
    for field in sorted(_FIELDS[legacy] & section.keys()):
        value = section[field]
        if field in ('model', 'prompt', 'tweaks') or (legacy == 'dify-service-api' and field == 'timeout'):
            continue
        if value is None and (
            (legacy == 'coze-api' and field in ('auto_save_history', 'auto-save-history'))
            or (legacy == 'weknora-api' and field in ('agent-id', 'knowledge-base-ids'))
        ):
            continue
        if field in _BOOLEANS:
            valid = type(value) is bool
        elif field in _INTEGERS or (field == 'timeout' and legacy == 'deerflow-api'):
            valid = type(value) is int
        elif field == 'timeout':
            valid = type(value) in (int, float)
        elif field in _NAME_LISTS:
            valid = _names(value)
        elif field == 'mcp-resources':
            valid = _attachments(value)
        else:
            valid = type(value) is str
        if not valid:
            _block(result, 'invalid_type', f'{prefix}.{field}')
    if legacy == 'local-agent':
        _validate_local(result, section)
    else:
        _validate_external(result, legacy, section)
    if legacy == 'deerflow-api':
        base = section.get('api-base')
        if type(base) is str and not base.strip().startswith(('http://', 'https://')):
            _block(result, 'invalid_value', f'{prefix}.api-base')


def _validate_output(result, config, legacy):
    output = config.get('output', {})
    if type(output) is not dict:
        _block(result, 'invalid_type', 'output')
        return
    misc = output.get('misc', {})
    if type(misc) is not dict:
        _block(result, 'invalid_type', 'output.misc')
        return
    value = misc.get('remove-think', False)
    if type(value) is not bool:
        _block(result, 'invalid_type', 'output.misc.remove-think')


def _assemble(result, legacy, section, config, preferences):
    selected = {**copy.deepcopy(_DEFAULTS[legacy]), **copy.deepcopy(section)}
    prefix = f'ai.{legacy}'
    if legacy in _IDENTITY_SOURCES:
        selected['user-id-source'] = _IDENTITY_SOURCES[legacy]
    if legacy == 'local-agent':
        selected.pop('max-round', None)
        singular = selected.pop('knowledge-base', '')
        if not selected['knowledge-bases'] and singular and singular != '__none__':
            selected['knowledge-bases'] = [singular]
            _warn(result, 'migration.alias_repaired', f'{prefix}.knowledge-base')
        model = selected['model']
        selected['model'] = (
            {'primary': model, 'fallbacks': [], 'reasoning': {}}
            if type(model) is str
            else {'fallbacks': [], 'reasoning': {}, **model}
        )
        preferences = preferences or {}
        for field, default in (('mcp-resources', []), ('mcp-resource-agent-read-enabled', True)):
            selected[field] = copy.deepcopy(section.get(field, preferences.get(field.replace('-', '_'), default)))
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
        selected['remove-think'] = config.get('output', {}).get('misc', {}).get('remove-think', False)
        _warn(result, 'migration.output_policy_copied', 'output.misc.remove-think')
    if legacy == 'dify-service-api':
        selected['timeout'] = 30
    elif legacy == 'coze-api':
        actual = selected.pop('auto_save_history', None)
        selected['auto-save-history'] = actual if type(actual) is bool else section.get('auto-save-history')
        if selected['auto-save-history'] is None:
            selected['auto-save-history'] = True
    elif legacy == 'dashscope-app-api':
        if 'references-quote' in selected:
            selected['references_quote'] = selected.pop('references-quote')
    elif legacy == 'langflow-api':
        for axis in ('input', 'output'):
            selected[f'{axis}-type'] = selected.pop(f'{axis}_type', selected[f'{axis}-type'])
        selected['tweaks'] = copy.deepcopy(_parse_tweaks(section.get('tweaks')))
    elif legacy == 'weknora-api':
        selected.setdefault(
            'agent-id', 'builtin-quick-answer' if selected['app-type'] == 'chat' else 'builtin-smart-reasoning'
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
    if 'id' in selection and 'runner' in selection:
        return _block(result, 'mixed_runner_selection', 'ai.runner')
    if 'id' in selection:
        current = selection['id']
        if type(current) is not str or not re.fullmatch(r'plugin:[^/\s]+/[^/\s]+/[^/\s]+', current):
            return _block(result, 'invalid_runner_id', 'ai.runner.id')
        result['state'] = 'already_current'
        return result
    if 'runner' not in selection:
        return result
    legacy = selection['runner']
    if type(legacy) is not str:
        return _block(result, 'invalid_type', 'ai.runner.runner')
    if legacy not in _TARGETS:
        return result
    name, version = _TARGETS[legacy]
    target = f'plugin:langbot-team/{name}/default'
    result.update(
        legacy_runner=legacy,
        target_runner_id=target,
        target_plugin={'author': 'langbot-team', 'name': name, 'version': version},
    )
    if 'runner_config' in ai:
        if type(ai['runner_config']) is not dict:
            return _block(result, 'invalid_type', 'ai.runner_config')
        if ai['runner_config']:
            return _block(result, 'mixed_runner_config', 'ai.runner_config')
    if 'expire-time' in selection:
        expiry = selection['expire-time']
        if type(expiry) is not int or expiry < 0:
            _block(result, 'invalid_expiry', 'ai.runner.expire-time')
    if set(ai) - set(_TARGETS) - {'runner', 'runner_config'}:
        _block(result, 'unknown_field', 'ai')
    if set(selection) - {'runner', 'expire-time'}:
        _block(result, 'unknown_field', 'ai.runner')
    if legacy not in ai:
        return _block(result, 'missing_field', f'ai.{legacy}')
    section = ai[legacy]
    if type(section) is not dict:
        return _block(result, 'invalid_type', f'ai.{legacy}')
    _validate_section(result, legacy, section)
    _validate_preferences(result, extensions_preferences, name)
    _validate_output(result, config, legacy)
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
    candidate = copy.deepcopy(config)
    candidate['ai']['runner'].pop('runner')
    candidate['ai']['runner']['id'] = target
    selected = _assemble(result, legacy, section, config, extensions_preferences)
    candidate['ai']['runner_config'] = {target: selected}
    # The durable transaction stores the full source, including inactive legacy
    # credentials. The active configuration must be canonical so the guarded
    # editor never needs to interpret mixed legacy/current containers.
    archived_paths = []
    for old_runner in _TARGETS:
        if old_runner in candidate['ai']:
            candidate['ai'].pop(old_runner)
            archived_paths.append(f'ai.{old_runner}')
    result.update(
        state='ready',
        config=candidate,
        changed_paths=['ai.runner.runner', 'ai.runner.id', 'ai.runner_config', *archived_paths],
    )
    return result
