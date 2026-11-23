"""Stamp the exact source revision into distributable artifacts (build time only)."""

import argparse
from pathlib import Path
import re
import subprocess


def stamp(root: Path, revision: str | None = None) -> str:
    if revision is None:
        revision = subprocess.check_output(['git', 'rev-parse', '--verify', 'HEAD'], cwd=root, text=True).strip()
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Build revision must be a full lowercase Git SHA')
    target = root / 'src/langbot/_build_info.py'
    target.write_text(f'"""Exact source revision stamped at artifact build time."""\n\nCORE_REVISION = {revision!r}\n')
    return revision


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision')
    args = parser.parse_args()
    print(stamp(Path(__file__).resolve().parents[1], args.revision))
