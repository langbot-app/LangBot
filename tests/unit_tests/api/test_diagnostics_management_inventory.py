"""Verify identities across every source-declared management registration."""

import ast
from pathlib import Path
import re
from types import SimpleNamespace

from langbot.pkg.api.management_diagnostics import operation_id


def test_every_http_registration_has_a_distinct_wire_safe_operation():
    root = Path(__file__).resolve().parents[3] / 'src/langbot/pkg/api/http/controller/groups'
    identities = []
    for path in root.rglob('*.py'):
        module = 'langbot.pkg.api.http.controller.groups.' + '.'.join(path.relative_to(root).with_suffix('').parts)
        for cls in ast.walk(ast.parse(path.read_text())):
            if not isinstance(cls, ast.ClassDef):
                continue
            prefix = ''
            for decorator in cls.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == 'group_class'
                ):
                    prefix = ast.literal_eval(decorator.args[1])
            for fn in ast.walk(cls):
                if not isinstance(fn, ast.AsyncFunctionDef):
                    continue
                for decorator in fn.decorator_list:
                    if not (
                        isinstance(decorator, ast.Call)
                        and isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr == 'route'
                    ):
                        continue
                    rule = prefix + ast.literal_eval(decorator.args[0])
                    methods = next(
                        (ast.literal_eval(k.value) for k in decorator.keywords if k.arg == 'methods'), ['GET']
                    )
                    operation = operation_id(
                        'http', SimpleNamespace(__module__=module, __name__=fn.name), rule=rule, methods=methods
                    )
                    assert re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.:-]{0,127}', operation), operation
                    identities.append(operation)
    assert len(identities) >= 200  # Guard against accidentally scanning an empty/subset tree.
    assert len(set(identities)) == len(identities)
