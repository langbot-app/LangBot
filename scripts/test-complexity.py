#!/usr/bin/env python3
"""Report Ruff's McCabe C901 scores, optionally against an explicit Git revision.

Scope: every Python file in src/langbot, including libs, migrations and templates.
No complexity threshold is enforced. Ruff is the sole complexity calculator; AST
parsing supplies qualified names, source ranges and change fingerprints only.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile

SOURCE = 'src/langbot'


def command(args: list[str], root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=root, capture_output=True, check=False)


def git(root: Path, *args: str) -> bytes:
    result = command(['git', *args], root)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors='replace').strip())
    return result.stdout


def index_functions(path: Path) -> dict[int, dict]:
    """Identify functions without trying to reimplement Ruff's complexity metric."""
    functions = {}
    occurrences = Counter()

    def visit(node: ast.AST, parents: tuple[str, ...] = ()) -> None:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            parents = (*parents, node.name)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = '.'.join(parents)
            occurrences[name] += 1
            functions[node.lineno] = {
                'name': name,
                'occurrence': occurrences[name],
                'line': node.lineno,
                'end_line': node.end_lineno,
                'fingerprint': hashlib.sha256(ast.dump(node).encode()).hexdigest(),
            }
        for child in ast.iter_child_nodes(node):
            visit(child, parents)

    visit(ast.parse(path.read_bytes(), filename=str(path)))
    return functions


def measure(root: Path) -> list[dict]:
    source = root / SOURCE
    if not source.is_dir():
        return []
    result = command(
        [
            sys.executable,
            '-m',
            'ruff',
            'check',
            '--isolated',
            '--no-cache',
            '--select',
            'C901',
            '--config',
            'lint.mccabe.max-complexity=0',
            '--config',
            'include=["*.py"]',
            '--target-version',
            'py312',
            '--ignore-noqa',
            '--no-respect-gitignore',
            '--exclude',
            '',
            '--output-format',
            'json',
            SOURCE,
        ],
        root,
    )
    # Exit 1 is expected: max-complexity=0 intentionally reports every function.
    if result.returncode not in (0, 1):
        raise ValueError(f'Ruff failed: {result.stderr.decode(errors="replace").strip()}')
    diagnostics = json.loads(result.stdout)
    functions = []
    indexes = {}
    for diagnostic in diagnostics:
        match = re.fullmatch(r'`.+` is too complex \((\d+) > 0\)', diagnostic['message'])
        if diagnostic['code'] != 'C901' or not match:
            raise ValueError(f'Unexpected Ruff diagnostic: {diagnostic}')
        path = Path(diagnostic['filename'])
        if path not in indexes:
            indexes[path] = index_functions(path)
        line = diagnostic['location']['row']
        if line not in indexes[path]:
            raise ValueError(f'Cannot identify Ruff function at {path}:{line}')
        functions.append(
            {
                'path': path.relative_to(root).as_posix(),
                **indexes[path][line],
                'complexity': int(match[1]),
            }
        )
    return sorted(functions, key=lambda item: (item['path'], item['line']))


def baseline(root: Path, ref: str) -> tuple[str, list[dict]]:
    revision = git(root, 'rev-parse', '--verify', '--end-of-options', f'{ref}^{{commit}}').decode().strip()
    # Snapshot source only. Never execute baseline code or load baseline config.
    entries = git(root, 'ls-tree', '--name-only', revision, '--', SOURCE)
    if not entries:
        return revision, []
    archive = git(root, 'archive', '--format=tar', revision, '--', SOURCE)
    with tempfile.TemporaryDirectory(prefix='langbot-complexity-') as directory:
        snapshot = Path(directory)
        with tarfile.open(fileobj=io.BytesIO(archive)) as contents:
            for member in contents:
                path = PurePosixPath(member.name)
                if not member.isfile() or path.suffix != '.py':
                    continue
                if path.is_absolute() or '..' in path.parts or not path.is_relative_to(SOURCE):
                    raise ValueError(f'Unsafe source archive path: {member.name}')
                destination = snapshot / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                with contents.extractfile(member) as handle:
                    destination.write_bytes(handle.read())
        return revision, measure(snapshot)


def file_renames(root: Path, revision: str) -> dict[str, str]:
    parts = git(root, 'diff', '--name-status', '-z', '--find-renames', revision, '--', SOURCE).split(b'\0')
    renames = {}
    index = 0
    while index < len(parts) and parts[index]:
        status = parts[index].decode()
        index += 1
        old_path = parts[index].decode()
        index += 1
        if status.startswith(('R', 'C')):
            new_path = parts[index].decode()
            index += 1
            if status.startswith('R'):
                renames[new_path] = old_path
    return renames


def function_key(function: dict, path: str | None = None) -> tuple:
    return path or function['path'], function['name'], function['occurrence']


def compare(before: list[dict], after: list[dict], renames: dict[str, str]) -> list[dict]:
    """Do not infer function renames; show unmatched identities as added/deleted."""
    remaining = {function_key(item): item for item in before}
    changes = []
    for current in after:
        key = function_key(current, renames.get(current['path']))
        previous = remaining.pop(key, None)
        if previous is None:
            status = 'added'
        elif current['path'] != previous['path']:
            status = 'renamed_file'
        elif current['fingerprint'] != previous['fingerprint']:
            status = 'modified'
        else:
            continue
        changes.append(
            {
                'status': status,
                'before': previous,
                'after': current,
                'delta': current['complexity'] - previous['complexity'] if previous else None,
            }
        )
    changes.extend({'status': 'deleted', 'before': item, 'after': None, 'delta': None} for item in remaining.values())
    return changes


def percentage(covered: int, total: int) -> float | None:
    return round(100 * covered / total, 2) if total else None


def attach_coverage(functions: list[dict], coverage: dict, root: Path) -> dict:
    files = {}
    for filename, data in coverage['files'].items():
        path = Path(filename)
        if not path.is_absolute():
            path = root / path
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if PurePosixPath(relative).is_relative_to(SOURCE):
            files[relative] = data
    branch_enabled = coverage.get('meta', {}).get('branch_coverage', False)
    for function in functions:
        data = files.get(function['path'])
        if data is None:
            function['coverage'] = None
            continue
        start, end = function['line'], function['end_line']
        excluded = set(data.get('excluded_lines', []))
        executed = {line for line in data['executed_lines'] if start <= line <= end} - excluded
        missing = {line for line in data['missing_lines'] if start <= line <= end} - excluded
        executed_branches = {tuple(arc) for arc in data.get('executed_branches', []) if start <= arc[0] <= end}
        missing_branches = {tuple(arc) for arc in data.get('missing_branches', []) if start <= arc[0] <= end}
        function['coverage'] = {
            'line_percent': percentage(len(executed), len(executed | missing)),
            'branch_percent': percentage(len(executed_branches), len(executed_branches | missing_branches))
            if branch_enabled
            else None,
            'covered_lines': len(executed),
            'missing_lines': len(missing),
            'covered_branches': len(executed_branches) if branch_enabled else None,
            'missing_branches': len(missing_branches) if branch_enabled else None,
        }
    summaries = [data['summary'] for data in files.values()]
    covered = sum(item['covered_lines'] for item in summaries)
    statements = sum(item['num_statements'] for item in summaries)
    covered_branches = sum(item.get('covered_branches', 0) for item in summaries)
    branches = sum(item.get('num_branches', 0) for item in summaries)
    return {
        'matched_source_files': len(files),
        'functions_without_coverage': sum(item.get('coverage') is None for item in functions),
        'line_percent': percentage(covered, statements),
        'branch_percent': percentage(covered_branches, branches) if branch_enabled else None,
        'covered_lines': covered,
        'statements': statements,
        'covered_branches': covered_branches if branch_enabled else None,
        'branches': branches if branch_enabled else None,
        'note': 'Coverage covers matching source files only. Function coverage uses inclusive def-to-end source '
        'ranges; nested functions overlap. Unmatched coverage is unknown, not zero. '
        'No-branch functions have null branch_percent. Coverage must come from this same checkout.',
    }


def statistics(functions: list[dict]) -> dict:
    scores = [item['complexity'] for item in functions]
    return {
        'function_count': len(scores),
        'mean': round(sum(scores) / len(scores), 2) if scores else None,
        'maximum': max(scores, default=None),
        'distribution': {
            '1-5': sum(score <= 5 for score in scores),
            '6-10': sum(6 <= score <= 10 for score in scores),
            '11-20': sum(11 <= score <= 20 for score in scores),
            '21-50': sum(21 <= score <= 50 for score in scores),
            '51+': sum(score > 50 for score in scores),
        },
    }


def hotspot_key(function: dict) -> tuple:
    coverage = function.get('coverage') or {}
    line = coverage.get('line_percent')
    return -function['complexity'], line if line is not None else 101, function['path'], function['line']


def format_percent(value: float | None) -> str:
    return f'{value:.2f}%' if value is not None else 'n/a'


def describe(function: dict) -> str:
    text = f'`{function["path"]}:{function["line"]}` {function["name"]} CC={function["complexity"]}'
    coverage = function.get('coverage')
    if coverage:
        text += (
            f'; lines {format_percent(coverage["line_percent"])}, branches {format_percent(coverage["branch_percent"])}'
        )
    return text


def render_summary(report: dict, limit: int) -> str:
    stats = report['current']
    lines = [
        '# Source complexity report',
        '',
        f'Analyzer: {report["analyzer"]} (C901, report only; no complexity gate)',
        f'Scope: {SOURCE}/**/*.py, including libs, migrations and templates',
        '',
        f'Functions: {stats["function_count"]}; mean CC: {stats["mean"]}; maximum CC: {stats["maximum"]}',
        'Distribution: ' + ', '.join(f'{key}: {value}' for key, value in stats['distribution'].items()),
        '',
    ]
    if 'coverage' in report:
        coverage = report['coverage']
        lines.extend(
            [
                f'Source line coverage: {format_percent(coverage["line_percent"])}; '
                f'source branch coverage: {format_percent(coverage["branch_percent"])}',
                f'Matched coverage files: {coverage["matched_source_files"]}; functions with unknown coverage: '
                f'{coverage["functions_without_coverage"]}',
                coverage['note'],
                '',
            ]
        )
    if 'baseline' in report:
        base = report['baseline']
        lines.extend(
            [
                f'## Changes against {report["base_revision"]}',
                '',
                f'Baseline functions: {base["function_count"]}; mean CC: {base["mean"]}; maximum CC: {base["maximum"]}',
                'Baseline distribution: ' + ', '.join(f'{key}: {value}' for key, value in base['distribution'].items()),
                'Statuses: '
                + ', '.join(
                    f'{key}: {value}' for key, value in Counter(c['status'] for c in report['changes']).items()
                ),
                'Matches use file path, qualified name and duplicate-definition occurrence. Git-detected file renames '
                'are matched; function renames appear as added/deleted. Changes are AST changes, excluding comments/formatting.',
                '',
            ]
        )
        changes = sorted(report['changes'], key=lambda change: hotspot_key(change['after'] or change['before']))
        for change in changes[:limit]:
            delta = f'; delta {change["delta"]:+d}' if change['delta'] is not None else ''
            lines.append(f'- {change["status"]}: {describe(change["after"] or change["before"])}{delta}')
        if not changes:
            lines.append('No function changes in scope.')
        lines.append('')
    lines.extend(
        [f'## Top {limit} hotspots', '', 'Ordered by complexity, then lower known line coverage for ties.', '']
    )
    lines.extend(f'- {describe(function)}' for function in report['hotspots'])
    lines.extend(
        [
            '',
            'Scores are Ruff McCabe values, not a composite quality score. Nested functions are included '
            'as reported by Ruff. Full function records and changes are in the JSON artifact.',
            '',
        ]
    )
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--base-ref', help='Explicit commit/ref to compare with the current working tree')
    parser.add_argument('--coverage-json', type=Path, help='coverage.py JSON generated from this checkout')
    parser.add_argument('--json', type=Path, default=Path('complexity.json'))
    parser.add_argument('--summary', type=Path, default=Path('complexity.md'))
    parser.add_argument('--top', type=int, default=20)
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error('--top must be positive')
    root = args.root.resolve()
    try:
        if not (root / SOURCE).is_dir():
            raise ValueError(f'Missing source directory: {root / SOURCE}')
        version = command([sys.executable, '-m', 'ruff', '--version'], root)
        if version.returncode:
            raise ValueError('Ruff is required; run uv sync --dev first')
        functions = measure(root)
        report = {
            'schema_version': 1,
            'analyzer': version.stdout.decode().strip(),
            'metric': 'Ruff C901 McCabe complexity',
            'scope': f'{SOURCE}/**/*.py (including libs)',
            'current': statistics(functions),
            'functions': functions,
        }
        if args.coverage_json:
            report['coverage'] = attach_coverage(functions, json.loads(args.coverage_json.read_text()), root)
        report['hotspots'] = sorted(functions, key=hotspot_key)[: args.top]
        if args.base_ref:
            revision, previous = baseline(root, args.base_ref)
            report.update(
                {
                    'base_ref': args.base_ref,
                    'base_revision': revision,
                    'baseline': statistics(previous),
                    'changes': compare(previous, functions, file_renames(root, revision)),
                }
            )
        summary = render_summary(report, args.top)
        for output in (args.json, args.summary):
            output.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + '\n')
        args.summary.write_text(summary)
        print(summary)
        return 0
    except (OSError, ValueError, SyntaxError, KeyError, tarfile.TarError) as error:
        print(f'Complexity report failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
