from __future__ import annotations

import os
import shutil
import sys


required_files = {
    "config.py": "config-template.py",
    "banlist.py": "banlist-template.py",
    "tips.py": "tips-custom-template.py",
    "sensitive.json": "res/templates/sensitive-template.json",
    "scenario/default.json": "scenario/default-template.json",
    "cmdpriv.json": "res/templates/cmdpriv-template.json",
}

required_paths = [
    "plugins",
    "prompts",
    "temp",
    "logs"
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
