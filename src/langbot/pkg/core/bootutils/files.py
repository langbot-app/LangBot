from __future__ import annotations

import os
import shutil


required_files = {
    'data/config.yaml': 'templates/config.yaml',
}

required_paths = [
    'temp',
    'data',
    'data/metadata',
    'data/logs',
    'data/labels',
]


async def generate_files() -> list[str]:
    global required_files, required_paths

    from ...utils import paths as path_utils

    for required_paths in required_paths:
        if not os.path.exists(required_paths):
            os.mkdir(required_paths)

    generated_files = []
    for file in required_files:
        if not os.path.exists(file):
            template_path = path_utils.get_resource_path(required_files[file])
            shutil.copyfile(template_path, file)
            generated_files.append(file)

    return generated_files
