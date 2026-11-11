"""Release gate between Core and the in-tree plugin SDK (``sdk/``).

Core is published with an exact ``langbot-plugin==X`` requirement and installs
the SDK from PyPI, never from ``sdk/``. Before a Core release this gate proves
that the pinned SDK is the one in the tree:

1. Core pins ``langbot-plugin`` exactly, and the pin equals ``sdk/pyproject.toml``.
2. ``langbot-plugin==X`` is already on PyPI (release the SDK first).
3. The SDK release tag ``sdk/vX`` exists and the shipped SDK sources are
   unchanged since that tag, so Core is not released against unreleased SDK code.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SDK_PACKAGE = 'langbot-plugin'
SHIPPED_SDK_PATHS = ('sdk/src', 'sdk/pyproject.toml')


def core_sdk_pin(root: Path = ROOT) -> str:
    dependencies = tomllib.loads((root / 'pyproject.toml').read_text())['project']['dependencies']
    for requirement in dependencies:
        match = re.fullmatch(r'langbot-plugin\s*==\s*([0-9A-Za-z.+-]+)', requirement.strip())
        if match:
            return match.group(1)
        if re.match(r'langbot-plugin\b', requirement.strip()):
            raise SystemExit(f'Core must pin {SDK_PACKAGE} exactly (found {requirement!r})')
    raise SystemExit(f'Core does not depend on {SDK_PACKAGE}')


def sdk_version(root: Path = ROOT) -> str:
    return tomllib.loads((root / 'sdk/pyproject.toml').read_text())['project']['version']


def on_pypi(version: str) -> bool:
    url = f'https://pypi.org/pypi/{SDK_PACKAGE}/{version}/json'
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.status == 200
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise


def git(*args: str, root: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(['git', *args], cwd=root, capture_output=True, text=True)


def check(root: Path = ROOT, *, check_pypi: bool = True, revision: str = 'HEAD') -> str | None:
    if not (root / 'sdk/pyproject.toml').is_file():
        # Releases cut before the SDK moved into this repository.
        return None
    pin = core_sdk_pin(root)
    in_tree = sdk_version(root)
    if pin != in_tree:
        raise SystemExit(
            f'Core pins {SDK_PACKAGE}=={pin} but sdk/pyproject.toml is {in_tree}. '
            'Release the SDK (tag sdk/v<version>) and update the Core pin first.'
        )
    if check_pypi and not on_pypi(pin):
        raise SystemExit(f'{SDK_PACKAGE}=={pin} is not on PyPI yet. Publish the SDK before releasing Core.')
    tag = f'sdk/v{pin}'
    if git('rev-parse', '--verify', '--quiet', f'refs/tags/{tag}^{{commit}}', root=root).returncode != 0:
        raise SystemExit(f'SDK release tag {tag} does not exist. Tag the SDK release commit before releasing Core.')
    diff = git('diff', '--quiet', tag, revision, '--', *SHIPPED_SDK_PATHS, root=root)
    if diff.returncode == 1:
        raise SystemExit(
            f'sdk/ changed since {tag}. Release a new SDK version and bump the Core pin, '
            'or revert the unreleased SDK changes, before releasing Core.'
        )
    if diff.returncode != 0:
        raise SystemExit(f'git diff against {tag} failed: {diff.stderr.strip()}')
    return pin


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--skip-pypi', action='store_true', help='Do not query PyPI (offline tests only).')
    parser.add_argument('--revision', default='HEAD')
    args = parser.parse_args()
    pin = check(check_pypi=not args.skip_pypi, revision=args.revision)
    if pin is None:
        print('No in-tree SDK (sdk/pyproject.toml); nothing to check.')
        return
    print(f'Core pins {SDK_PACKAGE}=={pin}; it matches sdk/ at tag sdk/v{pin}.')


if __name__ == '__main__':
    sys.exit(main())
