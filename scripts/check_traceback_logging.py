"""Reject Ruff TID251 diagnostics for raw tracebacks on added service code lines."""

import argparse
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import tokenize


SERVICE_ROOTS = ('src/langbot/', 'sdk/src/langbot_plugin/')
TRACEBACK_FUNCTIONS = ('print_exc', 'print_exception')
HUNK = re.compile(rb'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', re.MULTILINE)


def git_diff(*args):
    return subprocess.check_output(['git', '--literal-pathspecs', 'diff', '--no-ext-diff', '--no-textconv', *args])


def added_lines(base):
    paths = git_diff('--name-status', '-z', '--find-renames', '--diff-filter=AMRT', base, 'HEAD')
    fields = iter(os.fsdecode(paths).split('\0')[:-1])
    added = {}
    for status in fields:
        old_path = next(fields)
        path = next(fields) if status.startswith('R') else old_path
        if not path.startswith(SERVICE_ROOTS) or not path.endswith('.py') or Path(path).is_symlink():
            continue
        # Diff both names so an unchanged rename does not expose historical lines as additions.
        pathspec = [old_path, path] if path != old_path else [path]
        patch = git_diff('--unified=0', '--find-renames', base, 'HEAD', '--', *pathspec)
        ranges = []
        for match in HUNK.finditer(patch):
            start = int(match[1])
            count = int(match[2]) if match[2] is not None else 1
            if count:
                ranges.append(range(start, start + count))
        if ranges:
            added[path] = ranges
    return added


def lint(ruff, paths, suffix='', source=None):
    entries = ', '.join(
        f'"traceback.{name}{suffix}" = {{ msg = "Use the service logger with exc_info" }}'
        for name in TRACEBACK_FUNCTIONS
    )
    banned = 'lint.flake8-tidy-imports.banned-api = {' + entries + '}'
    result = subprocess.run(
        [
            *ruff,
            'check',
            '--isolated',
            '--select',
            'TID251',
            '--config',
            banned,
            '--ignore-noqa',
            '--output-format',
            'json',
            *paths,
        ],
        input=source,
        stdout=subprocess.PIPE,
        text=True,
    )
    if result.returncode not in (0, 1):
        result.check_returncode()
    return [item for item in json.loads(result.stdout) if item['code'] == 'TID251']


def direct_call_violations(ruff, path, ranges):
    with tokenize.open(path) as handle:
        source = handle.read()
    tree = ast.parse(source)
    aliases = {
        name.asname or name.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and not node.level and node.module == 'traceback'
        for name in node.names
        if name.name in TRACEBACK_FUNCTIONS
    }
    if not aliases:
        return []

    calls = sorted(
        (node.func.lineno, node.func.end_col_offset)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in aliases
        and any(node.func.lineno in rows for rows in ranges)
    )
    if not calls:
        return []

    # TID251 resolves attributes at the use site. Spelling f() as f.__call__() in the
    # lint input lets Ruff distinguish a traceback import from a shadowing local binding.
    lines = source.encode().split(b'\n')
    for row, end in reversed(calls):
        line = lines[row - 1]
        lines[row - 1] = line[:end] + b'.__call__' + line[end:]
    diagnostics = lint(ruff, ['--stdin-filename', path, '-'], '.__call__', b'\n'.join(lines).decode())
    return [
        f'{path}:{item["location"]["row"]}: TID251 {item["message"].replace(".__call__`", "`")}'
        for item in diagnostics
        if any(item['location']['row'] in rows for rows in ranges)
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base', help='Base commit to compare with the checked-out HEAD')
    parser.add_argument('ruff', nargs='*', default=['ruff'], help='Ruff command, default: ruff')
    args = parser.parse_args()

    changed = added_lines(args.base)
    if not changed:
        return 0

    violations = []
    root = Path.cwd()
    reported = set()
    for diagnostic in lint(args.ruff, ['--', *changed]):
        path = Path(diagnostic['filename']).relative_to(root).as_posix()
        reported.add(path)
        first = diagnostic['location']['row']
        last = diagnostic['end_location']['row']
        if any(rows.start <= last and first < rows.stop for rows in changed[path]):
            column = diagnostic['location']['column']
            violations.append(f'{path}:{first}:{column}: TID251 {diagnostic["message"]}')

    for path in sorted(reported):
        violations.extend(direct_call_violations(args.ruff, path, changed[path]))

    if violations:
        print('\n'.join(violations))
    return int(bool(violations))


if __name__ == '__main__':
    raise SystemExit(main())
