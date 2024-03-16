from __future__ import annotations

import os
import shutil
import sys


required_files = {
    "plugins/__init__.py": "templates/__init__.py",
    "plugins/plugins.json": "templates/plugin-settings.json",
    "data/config/command.json": "templates/command.json",
    "data/config/pipeline.json": "templates/pipeline.json",
    "data/config/platform.json": "templates/platform.json",
    "data/config/provider.json": "templates/provider.json",
    "data/config/system.json": "templates/system.json",
    "data/scenario/default.json": "templates/scenario-template.json",
}

required_paths = [
    "temp",
    "data",
    "data/metadata",
    "data/prompts",
    "data/scenario",
    "data/logs",
    "data/config",
    "plugins"
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
