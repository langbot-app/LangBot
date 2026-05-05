"""Safe expression evaluator for workflow nodes.

Uses Python's ``ast`` module to whitelist only comparison, boolean, arithmetic,
and simple attribute / subscript access.  No function calls, imports, or
arbitrary code execution.

The public API is :func:`safe_eval_with_vars` which accepts a mapping of
allowed variable names so that expressions like ``input == "hello"`` or
``data.x > 3`` work without resorting to :func:`eval`.
"""
from __future__ import annotations

import ast
import operator
from typing import Any


_SAFE_OPS = {
    # Arithmetic
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    # Unary
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Not: operator.not_,
    # Comparison
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


def safe_eval_with_vars(expr: str, variables: dict[str, Any] | None = None) -> Any:
    """Evaluate an expression safely with an optional variable mapping.

    Supports:
    - Literals (numbers, strings, booleans, None)
    - Comparisons (==, !=, <, >, <=, >=, in, not in, is, is not)
    - Boolean logic (and, or, not)
    - Arithmetic (+, -, *, /, //, %, **)
    - Ternary (x if cond else y)
    - Variable references from *variables* dict (e.g. ``input``, ``data``)
    - Attribute access on known variables (e.g. ``data.name``)
    - Subscript access on known variables (e.g. ``data["key"]``, ``items[0]``)

    Raises :class:`ValueError` on any disallowed construct (function calls,
    starred expressions, walrus operator, etc.).
    """
    variables = variables or {}
    tree = ast.parse(expr.strip(), mode='eval')
    return _eval_node(tree.body, variables)


def _eval_node(node: ast.AST, variables: dict[str, Any]) -> Any:
    # Literals
    if isinstance(node, ast.Constant):
        return node.value

    # Variable references
    if isinstance(node, ast.Name):
        if node.id in ('None', 'True', 'False'):
            return {'None': None, 'True': True, 'False': False}[node.id]
        if node.id in variables:
            return variables[node.id]
        raise ValueError(f"Unsupported variable reference: {node.id}")

    # Attribute access: obj.attr  (only on allowed variables)
    if isinstance(node, ast.Attribute):
        obj = _eval_node(node.value, variables)
        attr = node.attr
        if isinstance(obj, dict):
            return obj.get(attr)
        if hasattr(obj, attr):
            return getattr(obj, attr)
        return None

    # Subscript access: obj[key]  (only on allowed variables)
    if isinstance(node, ast.Subscript):
        obj = _eval_node(node.value, variables)
        key = _eval_node(node.slice, variables)
        try:
            return obj[key]
        except (KeyError, IndexError, TypeError):
            return None

    # Unary operators
    if isinstance(node, ast.UnaryOp):
        op_fn = _SAFE_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Unsupported unary op: {type(node.op).__name__}")
        return op_fn(_eval_node(node.operand, variables))

    # Binary operators
    if isinstance(node, ast.BinOp):
        op_fn = _SAFE_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Unsupported binary op: {type(node.op).__name__}")
        return op_fn(_eval_node(node.left, variables), _eval_node(node.right, variables))

    # Comparisons (chained)
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, variables)
        for op, comparator in zip(node.ops, node.comparators):
            op_fn = _SAFE_OPS.get(type(op))
            if op_fn is None:
                raise ValueError(f"Unsupported comparison: {type(op).__name__}")
            right = _eval_node(comparator, variables)
            if not op_fn(left, right):
                return False
            left = right
        return True

    # Boolean operators
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_eval_node(v, variables) for v in node.values)
        if isinstance(node.op, ast.Or):
            return any(_eval_node(v, variables) for v in node.values)

    # Ternary
    if isinstance(node, ast.IfExp):
        return (
            _eval_node(node.body, variables)
            if _eval_node(node.test, variables)
            else _eval_node(node.orelse, variables)
        )

    # Tuples / Lists (e.g. ``x in [1, 2, 3]``)
    if isinstance(node, (ast.Tuple, ast.List)):
        return [_eval_node(e, variables) for e in node.elts]

    # Dict literals (e.g. ``{"a": 1}``)
    if isinstance(node, ast.Dict):
        return {
            _eval_node(k, variables): _eval_node(v, variables)
            for k, v in zip(node.keys, node.values)
        }

    raise ValueError(f"Unsupported expression node: {type(node).__name__}")
