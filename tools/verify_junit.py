"""Reject missing evidence, zero cases, skips, xfails and failures in a mandatory suite."""

import argparse
from pathlib import Path
from xml.etree import ElementTree


def verify_report(path: Path) -> int:
    root = ElementTree.parse(path).getroot()
    cases = list(root.iter('testcase'))
    if not cases:
        raise ValueError(f'{path}: no executed cases')
    nonpassing = [
        node.attrib['name']
        for node in cases
        if any(node.find(outcome) is not None for outcome in ('error', 'failure', 'skipped'))
    ]
    if nonpassing:
        raise ValueError(f'{path}: mandatory cases did not pass: {", ".join(nonpassing)}')
    return len(cases)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports', type=Path, nargs='+')
    for path in parser.parse_args().reports:
        try:
            print(f'{path}: {verify_report(path)} mandatory cases passed.')
        except (OSError, ValueError, ElementTree.ParseError) as exc:
            parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
