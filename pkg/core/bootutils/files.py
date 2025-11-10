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

    for required_paths in required_paths:
        if not os.path.exists(required_paths):
            os.mkdir(required_paths)

    generated_files = []
    for file in required_files:
        if not os.path.exists(file):
            shutil.copyfile(required_files[file], file)
            generated_files.append(file)

    return generated_files
