"""Reject Ruff TID251 diagnostics for raw tracebacks on added service code lines."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess


SERVICE_ROOTS = ('src/langbot/', 'sdk/src/langbot_plugin/')
BANNED_APIS = (
    'lint.flake8-tidy-imports.banned-api = {'
    '"traceback.print_exc" = { msg = "Use the service logger with exc_info" }, '
    '"traceback.print_exception" = { msg = "Use the service logger with exc_info" }}'
)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base', help='Base commit to compare with the checked-out HEAD')
    parser.add_argument('ruff', nargs='*', default=['ruff'], help='Ruff command, default: ruff')
    args = parser.parse_args()

    changed = added_lines(args.base)
    if not changed:
        return 0

    result = subprocess.run(
        [
            *args.ruff,
            'check',
            '--isolated',
            '--select',
            'TID251',
            '--config',
            BANNED_APIS,
            '--ignore-noqa',
            '--output-format',
            'json',
            '--',
            *changed,
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    if result.returncode not in (0, 1):
        result.check_returncode()

    violations = []
    root = Path.cwd()
    for diagnostic in json.loads(result.stdout):
        if diagnostic['code'] != 'TID251':
            continue
        path = Path(diagnostic['filename']).relative_to(root).as_posix()
        first = diagnostic['location']['row']
        last = diagnostic['end_location']['row']
        if any(rows.start <= last and first < rows.stop for rows in changed[path]):
            column = diagnostic['location']['column']
            violations.append(f'{path}:{first}:{column}: TID251 {diagnostic["message"]}')

    if violations:
        print('\n'.join(violations))
    return int(bool(violations))


if __name__ == '__main__':
    raise SystemExit(main())
