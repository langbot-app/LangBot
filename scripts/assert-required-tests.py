"""Fail closed when a provisioned dependency-contract lane skips or loses tests."""

from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET


def verify_report(path: Path, expected_module: str, expected_tests: int, name_prefix: str = '') -> int:
    cases = list(ET.parse(path).getroot().iter('testcase'))
    if len(cases) != expected_tests:
        raise ValueError(f'Expected {expected_tests} tests, found {len(cases)} in {path}')
    for case in cases:
        if case.get('classname') != expected_module:
            raise ValueError(f'Unexpected test module: {case.get("classname")!r}')
        if not case.get('name', '').startswith(name_prefix):
            raise ValueError(f'Unexpected test name: {case.get("name")!r}')
        for outcome in ('skipped', 'failure', 'error'):
            if case.find(outcome) is not None:
                raise ValueError(f'Required test {case.get("name")!r} reported {outcome}')
    return len(cases)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--module', required=True)
    parser.add_argument('--expected-tests', type=int, required=True)
    parser.add_argument('--name-prefix', default='')
    args = parser.parse_args()
    if args.expected_tests < 1:
        parser.error('--expected-tests must be positive')
    count = verify_report(args.report, args.module, args.expected_tests, args.name_prefix)
    print(f'{args.module}: {count} required tests passed, 0 skipped')


if __name__ == '__main__':
    main()
