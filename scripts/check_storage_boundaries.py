"""Enforce static storage abstraction and layer dependency boundaries across src/langbot/.

This gate prevents business and domain modules from bypassing persistence abstractions
(e.g. importing SQLite/PostgreSQL dialects or drivers, branching on ``.dialect.name``,
embedding raw dialect SQL, calling ``get_db_engine().connect()/begin()`` directly, or
violating core layer dependency directions).

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
ORCHESTRATOR_PATH = 'src/langbot/pkg/agent/runner/orchestrator.py'
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
    'sqlalchemy.exc.IntegrityError': 'handle DB errors in the Service layer and raise ApplicationAPIException',
    'langbot.pkg.persistence.write_admission': 'do not access storage write admission from HTTP controllers',
}

ORCHESTRATOR_BANNED_IMPORTS: dict[str, str] = {
    'langbot.pkg.persistence.write_admission': (
        'keep storage write admission and retry budgets inside persistence / AgentRunJournal'
    ),
}

PERSISTENCE_UPWARD_IMPORTS: tuple[str, ...] = (
    'langbot.pkg.core.app',
    'langbot.pkg.api',
    'langbot.pkg.pipeline',
    'langbot.pkg.agent',
    'langbot.pkg.command',
)

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
    # rel_path is e.g. src/langbot/pkg/agent/runner/orchestrator.py -> package parts under src/
    parts = Path(rel_path).parts
    if parts and parts[0] == 'src':
        pkg_parts = list(parts[1:-1])
    else:
        pkg_parts = list(parts[:-1])
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

    if rel_path == ORCHESTRATOR_PATH:
        for banned, guidance in ORCHESTRATOR_BANNED_IMPORTS.items():
            if _matches_prefix(target, banned):
                violations.append(
                    Violation(
                        path=rel_path,
                        line=line,
                        rule='LAYER_IMPORT_VIOLATION',
                        detail=f'business orchestrator must not import `{target}`',
                        guidance=guidance,
                    )
                )
                break

    if (
        rel_path.startswith(PERSISTENCE_PREFIX)
        and not rel_path.startswith(PERSISTENCE_MIGRATIONS_PREFIX)
        and not in_type_checking
    ):
        for upward in PERSISTENCE_UPWARD_IMPORTS:
            if _matches_prefix(target, upward):
                violations.append(
                    Violation(
                        path=rel_path,
                        line=line,
                        rule='LAYER_IMPORT_VIOLATION',
                        detail=f'persistence layer runtime import of upper layer `{target}`',
                        guidance='guard type-only references with `if typing.TYPE_CHECKING:` or invert the dependency',
                    )
                )
                break


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
            matched_module = False
            for alias in node.names:
                target = f'{full_mod}.{alias.name}' if full_mod else alias.name
                before = len(violations)
                _check_import_target(rel_path, node.lineno, target, in_tc, violations)
                if len(violations) > before:
                    matched_module = True
            if not matched_module and full_mod:
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
            if isinstance(node.func, ast.Attribute) and node.func.attr in ('connect', 'begin'):
                recv = node.func.value
                if (
                    isinstance(recv, ast.Call)
                    and isinstance(recv.func, ast.Attribute)
                    and recv.func.attr == 'get_db_engine'
                ):
                    violations.append(
                        Violation(
                            path=rel_path,
                            line=node.lineno,
                            rule='RAW_ENGINE_BYPASS',
                            detail=f'direct `get_db_engine().{node.func.attr}()` bypasses persistence abstraction',
                            guidance='use `persistence_mgr.tenant_uow(...)` or a persistence transaction helper',
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
