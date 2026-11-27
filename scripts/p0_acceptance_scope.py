"""Select P0 acceptance paths without allowing unknown backend changes to escape."""

import json
import os
from pathlib import PurePosixPath
import subprocess


# Files used by the image build or its image-selection contract, but not
# necessarily by any of the separate permission and persistence suites.
IMAGE_INPUTS = {
    '.github/actions/classify-test-changes/action.yml',
    '.github/actions/classify-test-changes/classify.py',
    'scripts/check_core_artifacts.py',
    'scripts/stamp_build_revision.py',
    'web/package.json',
    'web/pnpm-lock.yaml',
}


def select(paths):
    paths = set(paths)
    shared = any(
        p.startswith(('sdk/', 'src/', 'res/', '.github/workflows/'))
        or p
        in {
            'pyproject.toml',
            'uv.lock',
            'main.py',
            'pytest.ini',
            'tests/conftest.py',
            'tests/e2e/conftest.py',
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
            or p in IMAGE_INPUTS
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
        # A rename also removes the old path, which can have a stricter lane than its destination.
        data = subprocess.check_output(['git', 'diff', '--name-only', '--no-renames', '-z', base, head, '--'])
        paths = [os.fsdecode(path) for path in data.split(b'\0') if path]
        result = select(paths)
    print(json.dumps(result, sort_keys=True))
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        for key, value in result.items():
            output.write(f'{key}={str(value).lower()}\n')
