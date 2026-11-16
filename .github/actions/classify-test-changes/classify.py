"""Select CI boundaries from the full Git diff, never the Actions 300-file paths list."""

import json
import os
import re
import subprocess


LANES = (
    'core',
    'core_full',
    'compatibility',
    'sdk',
    'persistence',
    'permissions',
    'box',
    'frontend',
    'docs',
    'plugins',
    'packaging',
    'production_image',
    'workflows',
    'compiled_cli',
    'plugin_identity',
    'seekdb',
)

ALL = set(LANES)
CORE_BOUNDARIES = {
    'core',
    'core_full',
    'sdk',
    'permissions',
    'persistence',
    'box',
    'frontend',
    'compiled_cli',
    'plugin_identity',
    'seekdb',
}


def under(path, *prefixes):
    return any(path.startswith(prefix) for prefix in prefixes)


def classify(paths):
    lanes = set()
    for path in paths:
        if under(path, 'sdk/', 'docker/', 'packaging/') or path in {
            'Dockerfile',
            '.dockerignore',
            'pyproject.toml',
            'uv.lock',
            'scripts/stamp_build_revision.py',
            'scripts/check_core_artifacts.py',
            '.github/workflows/core-packaging.yml',
            '.github/actions/classify-test-changes/action.yml',
            '.github/actions/classify-test-changes/classify.py',
            'web/package.json',
            'web/pnpm-lock.yaml',
        }:
            lanes.add('production_image')
        if under(path, '.github/workflows/', '.github/actions/', 'tools/'):
            lanes |= ALL - {'production_image'}
        elif path in {'pyproject.toml', 'uv.lock', 'pytest.ini', 'run_tests.sh', 'Makefile'}:
            lanes |= ALL - {'docs', 'workflows'}
        elif under(path, 'sdk/'):
            lanes |= CORE_BOUNDARIES | {'compatibility', 'plugins', 'packaging'}
        elif under(path, 'plugins/'):
            lanes |= {'plugins', 'packaging'}
            if under(path, 'plugins/Runner/', 'plugins/scripts/') or path == 'plugins/catalog.json':
                lanes |= {'core', 'sdk', 'permissions', 'box', 'plugin_identity'}
        elif under(path, 'web/'):
            lanes.add('frontend')
            if path in {'web/package.json', 'web/package-lock.json', 'web/pnpm-lock.yaml'}:
                lanes.add('packaging')
        elif under(path, 'docs/'):
            lanes.add('docs')
        elif under(path, 'dev-docs/', '.github/ISSUE_TEMPLATE/') or (
            '/' not in path and (path.endswith('.md') or path in {'LICENSE', 'CLAUDE.md'})
        ):
            continue
        elif under(path, 'docker/', 'packaging/', 'examples/') or path in {
            'Dockerfile',
            'Dockerfile.acceptance',
            '.dockerignore',
            '.gitattributes',
            '.gitignore',
            'MANIFEST.in',
            'scripts/check_core_artifacts.py',
            'scripts/check_sdk_release_pin.py',
            'scripts/stamp_build_revision.py',
        }:
            lanes |= {'compatibility', 'packaging', 'core_full', 'core', 'sdk', 'box', 'persistence'}
        elif under(path, 'src/langbot/', 'tests/'):
            lanes.add('core')
            if under(
                path,
                'src/langbot/pkg/core/',
                'src/langbot/pkg/config/',
                'src/langbot/templates/',
                'tests/conftest.py',
                'tests/utils/',
                'tests/smoke/',
            ):
                lanes |= CORE_BOUNDARIES
            if under(
                path,
                'src/langbot/pkg/api/',
                'src/langbot/pkg/workspace/',
                'src/langbot/pkg/entity/',
                'tests/unit_tests/api/',
                'tests/unit_tests/workspace/',
            ):
                lanes |= {'permissions', 'persistence', 'sdk', 'compiled_cli', 'frontend'}
            if under(
                path,
                'src/langbot/pkg/persistence/',
                'src/langbot/pkg/storage/',
                'src/langbot/pkg/entity/persistence/',
                'tests/integration/persistence/',
                'tests/unit_tests/persistence/',
                'tests/unit_tests/storage/',
            ):
                lanes |= {'persistence', 'permissions'}
            if under(
                path,
                'src/langbot/pkg/box/',
                'src/langbot/pkg/skill/',
                'src/langbot/pkg/plugin/',
                'src/langbot/pkg/pipeline/',
                'src/langbot/pkg/agent/',
                'src/langbot/pkg/storage/',
                'tests/unit_tests/box/',
                'tests/unit_tests/plugin/',
                'tests/unit_tests/pipeline/',
                'tests/unit_tests/agent/',
                'tests/integration_tests/',
                'tests/e2e/',
            ):
                lanes |= {'box', 'sdk', 'permissions'}
            if under(
                path,
                'src/langbot/pkg/rag/',
                'src/langbot/pkg/vector/',
                'tests/unit_tests/rag/',
                'tests/unit_tests/vector/',
            ):
                lanes |= {'seekdb', 'sdk'}
            if under(
                path,
                'src/langbot/pkg/plugin/',
                'src/langbot/pkg/platform/',
                'src/langbot/pkg/pipeline/',
                'src/langbot/pkg/entity/',
                'tests/unit_tests/plugin/',
                'tests/unit_tests/platform/',
            ):
                lanes |= {'plugin_identity', 'plugins'}
            if under(path, 'tests/integration/', 'tests/e2e/', 'src/langbot/web/'):
                lanes |= {'box', 'persistence', 'permissions', 'sdk', 'frontend'}
        elif under(path, 'scripts/', 'res/', 'skills/') or path == 'main.py':
            lanes |= CORE_BOUNDARIES | {'packaging', 'plugins'}
        else:
            # A new top-level source/config location must not silently bypass CI.
            lanes |= ALL
    return lanes


def diff(base):
    if not re.fullmatch('[0-9a-f]{40}', base) or base == '0' * 40:
        raise ValueError('No valid base commit')
    # HEAD is the synthetic PR merge commit. Do not hide the source side of renames.
    data = subprocess.check_output(['git', 'diff', '--name-only', '--no-renames', '-z', base, 'HEAD', '--'])
    return [path.decode('utf-8') for path in data.split(b'\0') if path]


def main():
    event = os.environ['EVENT_NAME']
    paths = []
    if event in {'pull_request', 'push'}:
        try:
            paths = diff(os.environ.get('BASE_SHA', ''))
        except (subprocess.CalledProcessError, ValueError) as exc:
            print(f'Change detection unavailable ({exc}); selecting all CI lanes.')
            lanes = ALL
        else:
            lanes = classify(paths)
    else:
        lanes = ALL
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        print('changed_paths=' + json.dumps(paths, ensure_ascii=True), file=output)
        for lane in LANES:
            print(f'{lane}={str(lane in lanes).lower()}', file=output)
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as output:
            print('### Regression selection\n', file=output)
            print(f'Compared {len(paths)} paths. Selected: {", ".join(sorted(lanes)) or "none"}.', file=output)
            print(f'Not selected: {", ".join(sorted(ALL - lanes)) or "none"}.', file=output)


if __name__ == '__main__':
    main()
