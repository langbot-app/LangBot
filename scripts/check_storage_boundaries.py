"""Enforce static storage abstraction and layer dependency boundaries across src/langbot/.

This gate prevents business and domain modules from bypassing persistence abstractions:
- ``STORAGE_DIALECT_IMPORT``: importing SQLite/PostgreSQL dialects or drivers outside
  ``src/langbot/pkg/persistence/`` (and ``pgvector_db.py``).
- ``DIALECT_NAME_BRANCH``: branching on ``.dialect.name`` outside persistence.
- ``DIALECT_SQL_FUNC``: calling dialect-specific SQLAlchemy ``func.date_trunc`` /
  ``func.json_extract`` / ``func.strftime`` outside persistence.
- ``RAW_DIALECT_SQL``: embedding dialect-specific SQL tokens (``sqlite_master``,
  ``information_schema.tables``, ``PRAGMA ...``, ``set_config('langbot.workspace_uuid'...)``)
  outside persistence.
- ``RAW_ENGINE_BYPASS``: calling ``get_db_engine().connect()/begin()`` (chained or via
  local engine variable assignment) outside persistence.
- ``LAYER_IMPORT_VIOLATION``:
  * HTTP controllers importing ``sqlalchemy*`` or ``langbot.pkg.persistence*``;
  * any non-persistence module importing ``langbot.pkg.persistence.write_admission``;
  * ``pkg/persistence/`` (excluding frozen Alembic migrations) importing upper layers at
    runtime (outside ``if TYPE_CHECKING:``).

Existing debt tracked in #3196 is recorded in ``scripts/storage_boundaries_baseline.json``
as a ratchet: any new or increased violation fails immediately with replacement guidance,
while removing legacy debt prints a tightening hint (or fails under ``--strict-baseline``).
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
import tokenize


DEFAULT_BASELINE = Path(__file__).with_name('storage_boundaries_baseline.json')

PERSISTENCE_PREFIX = 'src/langbot/pkg/persistence/'
PERSISTENCE_MIGRATIONS_PREFIX = 'src/langbot/pkg/persistence/alembic/versions/'
CONTROLLER_PREFIX = 'src/langbot/pkg/api/http/controller/'
LIBS_PREFIX = 'src/langbot/libs/'

ALLOWED_STORAGE_FILES = frozenset(
    {
        'src/langbot/pkg/vector/vdbs/pgvector_db.py',
    }
)

BANNED_STORAGE_IMPORTS: dict[str, str] = {
    'sqlalchemy.dialects.sqlite': 'use persistence dialect helpers in langbot.pkg.persistence',
    'sqlalchemy.dialects.postgresql': 'use persistence dialect helpers in langbot.pkg.persistence',
    'sqlite3': 'use persistence transaction helpers in langbot.pkg.persistence',
    'aiosqlite': 'use persistence transaction helpers in langbot.pkg.persistence',
    'asyncpg': 'use persistence transaction helpers in langbot.pkg.persistence',
    'psycopg': 'use persistence transaction helpers in langbot.pkg.persistence',
    'psycopg2': 'use persistence transaction helpers in langbot.pkg.persistence',
}

CONTROLLER_BANNED_IMPORTS: dict[str, str] = {
    'sqlalchemy': 'move SQL/ORM and DB exception handling to the Service or persistence layer',
    'langbot.pkg.persistence': 'HTTP controllers must go through Service abstractions, not persistence internals',
}

WRITE_ADMISSION_MODULE = 'langbot.pkg.persistence.write_admission'

# Persistence may only depend at runtime on foundational packages (plus itself).
PERSISTENCE_ALLOWED_PKG_DEPS = frozenset(
    {
        'persistence',
        'entity',
        'config',
        'utils',
        'i18n',
        'telemetry',
        'operation_trace',
    }
)

DIALECT_SQL_FUNCS = frozenset({'date_trunc', 'json_extract', 'strftime'})

RAW_DIALECT_SQL_RE = re.compile(
    r"\b(sqlite_master|information_schema\.tables|PRAGMA\s+\w+|set_config\s*\(\s*['\"]langbot\.workspace_uuid)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    rule: str
    detail: str
    guidance: str

    def format(self) -> str:
        return f'{self.path}:{self.line}: {self.rule} {self.detail} -> {self.guidance}'


def _is_storage_allowed(rel_path: str) -> bool:
    return rel_path.startswith(PERSISTENCE_PREFIX) or rel_path in ALLOWED_STORAGE_FILES


def _matches_prefix(target: str, prefix: str) -> bool:
    return target == prefix or target.startswith(prefix + '.')


def _resolve_import_from(rel_path: str, node: ast.ImportFrom) -> str:
    module = node.module or ''
    if node.level == 0:
        return module
    parts = Path(rel_path).parts
    pkg_parts = list(parts[1:-1]) if parts and parts[0] == 'src' else list(parts[:-1])
    keep = max(0, len(pkg_parts) - (node.level - 1))
    base = pkg_parts[:keep]
    if module:
        base.append(module)
    return '.'.join(base)


def _collect_type_checking_nodes(tree: ast.AST) -> set[int]:
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        is_tc = (isinstance(test, ast.Name) and test.id == 'TYPE_CHECKING') or (
            isinstance(test, ast.Attribute) and test.attr == 'TYPE_CHECKING'
        )
        if is_tc:
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    guarded.add(id(sub))
    return guarded


def _is_get_db_engine_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'get_db_engine'


def _check_import_target(
    rel_path: str,
    line: int,
    target: str,
    in_type_checking: bool,
    violations: list[Violation],
) -> None:
    if not _is_storage_allowed(rel_path):
        for banned, guidance in BANNED_STORAGE_IMPORTS.items():
            if _matches_prefix(target, banned):
                violations.append(
                    Violation(
                        path=rel_path,
                        line=line,
                        rule='STORAGE_DIALECT_IMPORT',
                        detail=f'forbidden storage/dialect import `{target}`',
                        guidance=guidance,
                    )
                )
                break

    if rel_path.startswith(CONTROLLER_PREFIX):
        for banned, guidance in CONTROLLER_BANNED_IMPORTS.items():
            if _matches_prefix(target, banned):
                violations.append(
                    Violation(
                        path=rel_path,
                        line=line,
                        rule='LAYER_IMPORT_VIOLATION',
                        detail=f'HTTP controller must not import `{target}`',
                        guidance=guidance,
                    )
                )
                break

    if not rel_path.startswith(PERSISTENCE_PREFIX) and _matches_prefix(target, WRITE_ADMISSION_MODULE):
        violations.append(
            Violation(
                path=rel_path,
                line=line,
                rule='LAYER_IMPORT_VIOLATION',
                detail=f'non-persistence module must not import `{target}`',
                guidance='use unified persistence transaction primitives in langbot.pkg.persistence',
            )
        )

    if (
        rel_path.startswith(PERSISTENCE_PREFIX)
        and not rel_path.startswith(PERSISTENCE_MIGRATIONS_PREFIX)
        and not in_type_checking
        and target.startswith('langbot.pkg.')
    ):
        top_pkg = target.split('.')[2]
        if top_pkg not in PERSISTENCE_ALLOWED_PKG_DEPS:
            violations.append(
                Violation(
                    path=rel_path,
                    line=line,
                    rule='LAYER_IMPORT_VIOLATION',
                    detail=f'persistence layer runtime import of upper layer `{target}`',
                    guidance='guard type-only references with `if typing.TYPE_CHECKING:` or invert the dependency',
                )
            )


class _EngineBypassVisitor(ast.NodeVisitor):
    """Track local variables bound to ``get_db_engine()`` per lexical scope."""

    def __init__(self, rel_path: str, violations: list[Violation]) -> None:
        self.rel_path = rel_path
        self.violations = violations
        self._scopes: list[set[str]] = [set()]

    def _is_engine_var(self, name: str) -> bool:
        return any(name in scope for scope in reversed(self._scopes))

    def _bind_name(self, name: str, is_engine: bool) -> None:
        if is_engine:
            self._scopes[-1].add(name)
        else:
            self._scopes[-1].discard(name)

    def _visit_scoped(self, node: ast.AST) -> None:
        self._scopes.append(set())
        self.generic_visit(node)
        self._scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_scoped(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_scoped(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_scoped(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        is_engine = _is_get_db_engine_call(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._bind_name(target.id, is_engine)
            else:
                self.visit(target)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.visit(node.value)
            is_engine = _is_get_db_engine_call(node.value)
            if isinstance(node.target, ast.Name):
                self._bind_name(node.target.id, is_engine)
                return
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and node.func.attr in ('connect', 'begin'):
            recv = node.func.value
            if _is_get_db_engine_call(recv):
                self.violations.append(
                    Violation(
                        path=self.rel_path,
                        line=node.lineno,
                        rule='RAW_ENGINE_BYPASS',
                        detail=f'direct `get_db_engine().{node.func.attr}()` bypasses persistence abstraction',
                        guidance='use `persistence_mgr.tenant_uow(...)` or a persistence transaction helper',
                    )
                )
            elif isinstance(recv, ast.Name) and self._is_engine_var(recv.id):
                self.violations.append(
                    Violation(
                        path=self.rel_path,
                        line=node.lineno,
                        rule='RAW_ENGINE_BYPASS',
                        detail=f'`{recv.id}.{node.func.attr}()` via `get_db_engine()` bypasses persistence abstraction',
                        guidance='use `persistence_mgr.tenant_uow(...)` or a persistence transaction helper',
                    )
                )
        self.generic_visit(node)


def scan_file(rel_path: str, source: str) -> list[Violation]:
    tree = ast.parse(source, filename=rel_path)
    tc_nodes = _collect_type_checking_nodes(tree)
    violations: list[Violation] = []
    storage_allowed = _is_storage_allowed(rel_path)

    for node in ast.walk(tree):
        in_tc = id(node) in tc_nodes
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_import_target(rel_path, node.lineno, alias.name, in_tc, violations)
        elif isinstance(node, ast.ImportFrom):
            full_mod = _resolve_import_from(rel_path, node)
            # For statement-level module bans (e.g., controller importing `from sqlalchemy import a, b`),
            # check the module once when it matches a banned prefix to avoid multiplying counts by symbol count,
            # while still checking individual aliases for `from sqlalchemy.dialects import postgresql, sqlite`.
            matched_aliases = False
            for alias in node.names:
                target = f'{full_mod}.{alias.name}' if full_mod else alias.name
                before = len(violations)
                _check_import_target(rel_path, node.lineno, target, in_tc, violations)
                if len(violations) > before:
                    matched_aliases = True
            if not matched_aliases and full_mod:
                _check_import_target(rel_path, node.lineno, full_mod, in_tc, violations)
        elif not storage_allowed and isinstance(node, ast.Attribute):
            if node.attr == 'name' and isinstance(node.value, ast.Attribute) and node.value.attr == 'dialect':
                violations.append(
                    Violation(
                        path=rel_path,
                        line=node.lineno,
                        rule='DIALECT_NAME_BRANCH',
                        detail='direct `.dialect.name` inspection outside persistence layer',
                        guidance='move dialect-specific SQL/behavior behind a helper in langbot.pkg.persistence',
                    )
                )
        elif not storage_allowed and isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in DIALECT_SQL_FUNCS:
                recv = node.func.value
                is_sa_func = (isinstance(recv, ast.Name) and recv.id == 'func') or (
                    isinstance(recv, ast.Attribute) and recv.attr == 'func'
                )
                if is_sa_func:
                    violations.append(
                        Violation(
                            path=rel_path,
                            line=node.lineno,
                            rule='DIALECT_SQL_FUNC',
                            detail=f'dialect-specific SQLAlchemy `func.{node.func.attr}()` outside persistence layer',
                            guidance='use a dialect-agnostic query helper in langbot.pkg.persistence',
                        )
                    )
        elif (
            not storage_allowed
            and not rel_path.startswith(LIBS_PREFIX)
            and isinstance(node, ast.Constant)
            and isinstance(node.value, str)
        ):
            match = RAW_DIALECT_SQL_RE.search(node.value)
            if match:
                violations.append(
                    Violation(
                        path=rel_path,
                        line=node.lineno,
                        rule='RAW_DIALECT_SQL',
                        detail=f'dialect-specific SQL token `{match.group(0)}` outside persistence layer',
                        guidance='delegate schema/tenant/locking SQL to langbot.pkg.persistence',
                    )
                )

    if not storage_allowed:
        _EngineBypassVisitor(rel_path, violations).visit(tree)

    violations.sort(key=lambda item: (item.path, item.line, item.rule, item.detail))
    return violations


def scan_repo(root: Path) -> list[Violation]:
    src_root = root / 'src' / 'langbot'
    if not src_root.exists():
        return []
    violations: list[Violation] = []
    for path in sorted(src_root.rglob('*.py')):
        if path.is_symlink():
            continue
        rel_path = path.relative_to(root).as_posix()
        with tokenize.open(path) as handle:
            source = handle.read()
        violations.extend(scan_file(rel_path, source))
    return violations


def build_baseline(violations: list[Violation]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for item in violations:
        counts[item.path][item.rule] += 1
    return {path: dict(sorted(counter.items())) for path, counter in sorted(counts.items())}


def evaluate(
    violations: list[Violation],
    baseline: dict[str, dict[str, int]],
) -> tuple[list[Violation], list[str]]:
    by_key: dict[tuple[str, str], list[Violation]] = defaultdict(list)
    for item in violations:
        by_key[(item.path, item.rule)].append(item)

    failures: list[Violation] = []
    stale_notices: list[str] = []

    all_keys = sorted(set(by_key.keys()) | {(path, rule) for path, rules in baseline.items() for rule in rules})
    for path, rule in all_keys:
        found = by_key.get((path, rule), [])
        allowed = baseline.get(path, {}).get(rule, 0)
        if len(found) > allowed:
            failures.extend(found)
        elif len(found) < allowed:
            stale_notices.append(
                f'{path}: {rule} baseline allows {allowed} but only {len(found)} remain '
                '(run `python scripts/check_storage_boundaries.py --update-baseline`)'
            )

    return failures, stale_notices


def load_baseline(path: Path) -> dict[str, dict[str, int]]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw, dict):
        raise ValueError(f'Baseline must be a JSON object: {path}')
    result: dict[str, dict[str, int]] = {}
    for file_path, rules in raw.items():
        if not isinstance(file_path, str) or not isinstance(rules, dict):
            raise ValueError(f'Invalid baseline entry for {file_path!r}')
        parsed_rules: dict[str, int] = {}
        for rule, count in rules.items():
            if not isinstance(rule, str) or not isinstance(count, int) or count < 0:
                raise ValueError(f'Invalid baseline count for {file_path}:{rule}')
            if count > 0:
                parsed_rules[rule] = count
        if parsed_rules:
            result[file_path] = parsed_rules
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='Repository root directory')
    parser.add_argument(
        '--baseline',
        type=Path,
        default=DEFAULT_BASELINE,
        help='Path to ratchet baseline JSON file',
    )
    parser.add_argument(
        '--strict-baseline',
        action='store_true',
        help='Also fail when existing baseline entries exceed actual violation counts',
    )
    parser.add_argument(
        '--update-baseline',
        action='store_true',
        help='Write the current violation counts to the baseline file and exit 0',
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    violations = scan_repo(root)

    if args.update_baseline:
        data = build_baseline(violations)
        args.baseline.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        print(f'Updated baseline at {args.baseline} ({len(violations)} tracked legacy violations).')
        return 0

    baseline = load_baseline(args.baseline)
    failures, stale_notices = evaluate(violations, baseline)

    if failures:
        print('Storage / layer boundary violations detected (exceeds ratchet baseline):')
        for item in failures:
            print('  ' + item.format())
        return 1

    if stale_notices:
        prefix = 'ERROR (strict baseline)' if args.strict_baseline else 'INFO (baseline can be tightened)'
        for notice in stale_notices:
            print(f'{prefix}: {notice}')
        if args.strict_baseline:
            return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
