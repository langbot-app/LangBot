"""Workflow step catalog, template substitution and draft validation."""

from collections import defaultdict

import regex
from jinja2 import TemplateError

from .templates import references, render as render


def _step(category, outputs='', config='', branches='none', terminal=False):
    return dict(
        category=category, outputs=outputs.split(), config_keys=config.split(), branches=branches, terminal=terminal
    )


CATALOG = {
    'start': _step(
        'logic',
        'trigger text sender_id sender_name is_group group_id platform bot_uuid images voice args event payload target',
    ),
    'llm': _step('ai', 'text error', 'model_uuid prompt use_history use_images temperature max_tokens on_error'),
    'classify': _step('ai', 'category', 'model_uuid instruction categories', 'categories'),
    'extract': _step('ai', 'ok', 'model_uuid fields'),
    'knowledge': _step('ai', 'text chunks', 'kb_uuid query top_k'),
    'random': _step('logic', 'value', 'mode items weights min max seed'),
    'code': _step('logic', '', 'language code inputs outputs'),
    'history': _step('logic', 'messages text', 'scope limit since_hours'),
    'condition': _step('logic', 'matched error', 'cases', 'cases'),
    'remember': _step('logic', 'value', 'scope items'),
    'reply': _step('action', 'sent', 'content'),
    'send': _step('action', 'sent', 'bot_uuid target_type target_id content'),
    'http': _step('action', 'status body json error', 'method url headers body timeout on_error'),
    'handoff': _step('action', config='target_type target_uuid text', terminal=True),
}


def _strings(value, path='config'):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, (list, dict)):
        for key, item in enumerate(value) if isinstance(value, list) else value.items():
            yield from _strings(item, f'{path}.{key}')


def validate(graph, *, models=None, targets=None):
    """Validate a draft; resource catalogs, when supplied, must be workspace scoped."""
    issues = []

    def issue(code, node=None, field=None, severity='error'):
        entry = {'code': code, 'severity': severity}
        if node:
            entry['node_id'] = node
        if field:
            entry['field'] = field
        if entry not in issues:
            issues.append(entry)

    if not isinstance(graph, dict) or not all(isinstance(graph.get(key), list) for key in ('nodes', 'edges')):
        issue('not_tree')
        return issues
    nodes = {}
    outputs = {}
    branches = {}
    starts = []
    for node in graph['nodes']:
        if not isinstance(node, dict) or not isinstance(node.get('id'), str) or not node['id']:
            issue('required_missing', field='id')
            continue
        ident = node['id']
        kind = node.get('type')
        if ident in nodes or ident in ('memory', 'now', '_render_budget'):
            issue('not_tree', ident)
            continue
        if not isinstance(kind, str) or kind not in CATALOG or not isinstance(node.get('config'), dict):
            issue('required_missing', ident, 'type' if not isinstance(kind, str) or kind not in CATALOG else 'config')
            continue
        nodes[ident] = node
        config = node['config']
        outputs[ident] = set(CATALOG[kind]['outputs'])
        if kind == 'code':
            declared = config.get('outputs', [])
            if not isinstance(declared, list) or not all(isinstance(key, str) and key for key in declared):
                issue('required_missing', ident, 'outputs')
            else:
                outputs[ident].update(declared)
            if config.get('language', 'python') != 'python':
                issue('unsupported_type', ident, 'language')
        if kind == 'start':
            starts.append(ident)
        required = {
            'llm': ('model_uuid', 'prompt'),
            'extract': ('model_uuid', 'fields'),
            'classify': ('model_uuid',),
            'http': ('url',),
            'knowledge': ('kb_uuid', 'query'),
            'code': ('code',),
            'random': ('mode',) if config.get('mode') == 'number' else ('mode', 'items'),
            'reply': () if config.get('text') else ('content',),
            'send': ('target_type', 'target_id') if config.get('text') else ('target_type', 'target_id', 'content'),
            'handoff': ('target_type', 'target_uuid'),
            'remember': ('items',),
            'condition': ('cases',),
        }
        for key in required.get(kind, ()):
            if not config.get(key):
                issue('required_missing', ident, key)
        model = config.get('model_uuid')
        if models is not None and isinstance(model, str) and model and '{{' not in model and model not in models:
            issue('model_not_found', ident, 'model_uuid')
        target = config.get('target_uuid')
        if (
            targets is not None
            and isinstance(target, str)
            and target
            and '{{' not in target
            and (config.get('target_type'), target) not in targets
        ):
            issue('target_not_found', ident, 'target_uuid')
        group = CATALOG[kind]['branches']
        if group != 'none':
            branches[ident] = {'else'}
            rows = config.get(group)
            if not isinstance(rows, list) or not rows:
                issue('empty_category' if kind == 'classify' else 'required_missing', ident, group)
            else:
                for row_index, row in enumerate(rows):
                    key = row.get('id') if isinstance(row, dict) else None
                    if kind == 'condition' and isinstance(row, dict) and isinstance(row.get('rules'), list):
                        for index, rule in enumerate(row['rules']):
                            if not isinstance(rule, dict) or rule.get('op') != 'regex':
                                continue
                            pattern = rule.get('right', '')
                            if isinstance(pattern, str) and any(mark in pattern for mark in ('{{', '{%', '{#')):
                                continue
                            try:
                                regex.compile(pattern)
                            except (TypeError, regex.error):
                                issue('invalid_regex', ident, f'cases.{row_index}.rules.{index}.right')
                    if (
                        not isinstance(key, str)
                        or not key
                        or key in branches[ident]
                        or (kind == 'classify' and not row.get('label'))
                    ):
                        issue('empty_category' if kind == 'classify' else 'branch_unknown', ident, group)
                    else:
                        branches[ident].add(key)
        if kind in ('extract', 'remember'):
            key = 'fields' if kind == 'extract' else 'items'
            rows = config.get(key)
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict) and isinstance(row.get('key'), str) and row['key']:
                        outputs[ident].add(row['key'])
                    else:
                        issue('required_missing', ident, key)
    if len(starts) != 1:
        issue('not_tree' if starts else 'start_missing')
    parents = {}
    outgoing = defaultdict(dict)
    for edge in graph['edges']:
        if not isinstance(edge, dict) or not all(
            isinstance(edge.get(key), str) and edge[key] in nodes for key in ('from', 'to')
        ):
            issue('not_tree')
            continue
        source, dest, branch = edge['from'], edge['to'], edge.get('branch')
        if nodes[source]['type'] == 'handoff':
            issue('handoff_has_next', source)
        if branch is not None and not isinstance(branch, str):
            issue('branch_unknown', source)
            continue
        if branch not in branches.get(source, {None}):
            issue('branch_unknown', source)
        if branch in outgoing[source] or dest in parents or dest in starts:
            issue('not_tree', dest)
        outgoing[source][branch] = dest
        parents[dest] = source
    for ident, node in nodes.items():
        ancestors = set()
        current = ident
        while current in parents:
            current = parents[current]
            if current in ancestors:
                issue('not_tree', ident)
                break
            ancestors.add(current)
        if ident not in starts and not ancestors.intersection(starts):
            issue('unreachable', ident, severity='warning')
            if ident not in parents:
                issue('not_tree', ident)
        for path, text in _strings(node['config']):
            if node['type'] == 'code' and path == 'config.code':
                continue
            if not any(mark in text for mark in ('{{', '{%', '{#')):
                continue
            try:
                names, refs = references(text)
            except TemplateError:
                issue('template_invalid', ident, path)
                continue
            for source in names:
                if source not in ancestors:
                    issue('ref_not_upstream', ident, path)
            for source, key in refs:
                if source in ancestors and key not in outputs[source]:
                    issue('ref_unknown_key', ident, path, severity='warning' if key is None else 'error')
    return issues
