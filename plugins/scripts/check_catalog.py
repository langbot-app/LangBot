#!/usr/bin/env python3
"""Validate categorized plugin sources without importing plugin code."""

from __future__ import annotations

import ast
import argparse
from collections import Counter
import json
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = ('Runner', 'KnowledgeEngine', 'misc')
REPOSITORY = 'https://github.com/langbot-app/LangBot/tree/master/plugins/'


def check_catalog(root: Path = ROOT) -> list[dict]:
    manifests = sorted(p for category in CATEGORIES for p in (root / category).glob('*/manifest.yaml'))
    if not manifests:
        raise ValueError('No categorized plugin manifests found')
    plugins = []
    identities = set()
    for path in manifests:
        plugin = path.parent
        manifest = yaml.safe_load(path.read_text())
        metadata = manifest['metadata']
        identity = f'{metadata["author"]}/{metadata["name"]}'
        if identity in identities:
            raise ValueError(f'Duplicate plugin ID: {identity}')
        identities.add(identity)
        kinds = manifest['spec']['components']
        category = 'Runner' if 'Runner' in kinds else 'KnowledgeEngine' if 'KnowledgeEngine' in kinds else 'misc'
        assert plugin.parent.name == category, path
        assert metadata['repository'] == REPOSITORY + plugin.relative_to(root).as_posix(), path
        assert re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?', str(metadata['version'])), path
        for required in ('README.md', metadata['icon'], manifest['execution']['python']['path']):
            assert (plugin / required).is_file(), (path, required)
        for kind, declaration in kinds.items():
            for directory in declaration.get('fromDirs', []):
                assert (plugin / directory['path']).is_dir(), (path, kind, directory)
            for source in declaration.get('fromFiles', []):
                assert (plugin / source).is_file(), (path, kind, source)
        for source in plugin.rglob('*.py'):
            if not any(part in {'.venv', '__pycache__', 'dist'} for part in source.parts):
                ast.parse(source.read_text(), filename=str(source))
        plugins.append(
            {
                'id': identity,
                'version': metadata['version'],
                'category': category,
                'path': plugin.relative_to(root).as_posix(),
                'repository': metadata['repository'],
            }
        )
    return plugins


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    catalog = check_catalog()
    index = ROOT / 'catalog.json'
    if args.write:
        index.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + '\n')
    elif json.loads(index.read_text()) != catalog:
        raise SystemExit('Plugin catalog is stale; run python plugins/scripts/check_catalog.py --write')
    print(f'Validated {len(catalog)} plugins: {dict(Counter(p["category"] for p in catalog))}')
