"""The workflow template namespace contains only step outputs, memory and time."""

import json
import random
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from functools import lru_cache

from jinja2 import ChainableUndefined, TemplateError, meta, nodes, pass_context
from jinja2.sandbox import ImmutableSandboxedEnvironment


class StepEnvironment(ImmutableSandboxedEnvironment):
    def getattr(self, obj, attribute):
        if isinstance(obj, Mapping):
            return obj.get(attribute, self.undefined(name=attribute))
        return super().getattr(obj, attribute)

    def is_safe_callable(self, obj):
        return False


def plain(value):
    if isinstance(value, (dict, list, bool)) or value is None:
        return json.dumps(value, ensure_ascii=False)
    return value


environment = StepEnvironment(undefined=ChainableUndefined, finalize=plain)
environment.globals.clear()


@pass_context
def bounded_items(context, values):
    for item in values:
        budget = context['_render_budget']
        budget[0] -= 1
        if budget[0] < 0 or time.monotonic() > budget[1]:
            raise TemplateError('Template exceeded its render limit')
        yield item


environment.filters = {
    '_bounded_items': bounded_items,
    'json': lambda value: json.dumps(value, ensure_ascii=False),
    'date': lambda value, fmt: value.strftime(fmt) if isinstance(value, datetime) else '',
    'random': lambda values: random.choice(values) if values else '',
    'truncate': environment.filters['truncate'],
    'length': len,
    'default': environment.filters['default'],
}


@lru_cache(maxsize=256)
def compile_template(text):
    if len(text) > 100_000:
        raise TemplateError('Template is too long')
    tree = environment.parse(text)
    forbidden = (
        nodes.Call,
        nodes.CallBlock,
        nodes.Macro,
        nodes.Import,
        nodes.FromImport,
        nodes.Include,
        nodes.Extends,
        nodes.Mul,
        nodes.Pow,
        nodes.Mod,
        nodes.Assign,
        nodes.AssignBlock,
        nodes.FilterBlock,
        nodes.Block,
    )
    if next(tree.find_all(forbidden), None) is not None:
        raise TemplateError('Unsupported workflow template operation')
    names = meta.find_undeclared_variables(tree)
    refs = []
    for access in tree.find_all((nodes.Getattr, nodes.Getitem)):
        if isinstance(access.node, nodes.Name) and access.node.name in names:
            key = (
                access.attr
                if isinstance(access, nodes.Getattr)
                else access.arg.value
                if isinstance(access.arg, nodes.Const)
                else None
            )
            refs.append((access.node.name, key))
    for loop in tree.find_all(nodes.For):
        if loop.recursive:
            raise TemplateError('Recursive workflow template loops are not supported')
        loop.iter = nodes.Filter(loop.iter, '_bounded_items', [], [], None, None, lineno=loop.lineno)
    return names, refs, environment.from_string(tree)


def references(text):
    names, refs, _ = compile_template(text)
    return names - {'memory', 'now'}, refs


def render(value, results, memory, now=None):
    context = {**results, 'memory': memory, 'now': now or datetime.now(timezone.utc)}
    deadline = time.monotonic() + 1
    context['_render_budget'] = [10_000, deadline]
    remaining = 100_000

    def field(item):
        nonlocal remaining
        if isinstance(item, list):
            return [field(part) for part in item]
        if isinstance(item, dict):
            return {key: field(part) for key, part in item.items()}
        if not isinstance(item, str):
            return item
        if not any(mark in item for mark in ('{{', '{%', '{#')):
            return item
        _, _, template = compile_template(item)
        chunks = []
        for chunk in template.generate(context):
            remaining -= len(chunk)
            if remaining < 0 or time.monotonic() > deadline:
                raise TemplateError('Template exceeded its render limit')
            chunks.append(chunk)
        return ''.join(chunks)

    return field(value)
