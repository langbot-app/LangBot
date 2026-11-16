"""Select P0 acceptance paths without allowing unknown backend changes to escape."""

import json
import os
from pathlib import PurePosixPath
import subprocess


def select(paths):
    paths = set(paths)
    shared = any(
        p.startswith(('sdk/', 'src/', '.github/workflows/'))
        or p
        in {
            'pyproject.toml',
            'uv.lock',
            'scripts/p0_acceptance_scope.py',
            'tests/utils/required_suites.py',
            'tests/e2e/test_image_upgrade.py',
            'tests/integration/api/test_plugin_permission_lifecycle.py',
        }
        for p in paths
    )
    persistence = shared or any(
        p.startswith(
            (
                'src/langbot/pkg/skill/',
                'src/langbot/pkg/storage/',
                'src/langbot/pkg/box/',
                'src/langbot/pkg/persistence/',
                'src/langbot/pkg/entity/persistence/',
                'tests/integration/skill/',
                'tests/integration/storage/',
                'tests/integration/persistence/',
            )
        )
        or 'persistence' in p
        or 'network_file' in p
        or 'skill_network' in p
        for p in paths
    )
    permissions = shared or any(
        p.startswith(
            (
                'src/langbot/pkg/api/',
                'src/langbot/pkg/plugin/',
                'src/langbot/pkg/workspace/',
                'src/langbot/pkg/agent/',
                'tests/integration/api/',
            )
        )
        or 'permission' in p
        for p in paths
    )
    image = (
        shared
        or persistence
        or any(
            p.startswith(('docker/', 'packaging/'))
            or PurePosixPath(p).name in {'Dockerfile', 'MANIFEST.in', '.dockerignore'}
            or p == 'tests/e2e/test_image_upgrade.py'
            for p in paths
        )
    )
    return dict(persistence=bool(persistence), permissions=bool(permissions), image=bool(image))


if __name__ == '__main__':
    base = os.environ.get('BASE_SHA', '')
    head = os.environ['HEAD_SHA']
    if not base or set(base) == {'0'}:
        result = dict.fromkeys(('persistence', 'permissions', 'image'), True)
    else:
        paths = subprocess.check_output(['git', 'diff', '--name-only', base, head], text=True).splitlines()
        result = select(paths)
    print(json.dumps(result, sort_keys=True))
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        for key, value in result.items():
            output.write(f'{key}={str(value).lower()}\n')
