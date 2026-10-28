from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import zipfile

import yaml

from check_catalog import ROOT, check_catalog


def package_plugin(plugin: str, output: Path) -> Path:
    catalog = {entry['path']: entry for entry in check_catalog()}
    if plugin not in catalog:
        raise ValueError('Select an exact relative plugin path from plugins/catalog.json')
    source = ROOT / plugin
    destination = output.resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise ValueError('Build output must be outside the plugin source tree')
    destination.mkdir(parents=True, exist_ok=True)
    metadata = yaml.safe_load((source / 'manifest.yaml').read_text())['metadata']
    archive = destination / f'{metadata["author"]}-{metadata["name"]}-{metadata["version"]}.lbpkg'
    if archive.exists():
        raise ValueError(f'Build output already exists: {archive.name}')
    subprocess.run(['lbp', 'build', '--output', str(destination)], cwd=source, check=True)
    with zipfile.ZipFile(archive) as package:
        manifest = yaml.safe_load(package.read('manifest.yaml'))
        for field in ('author', 'name', 'version', 'repository'):
            if manifest['metadata'][field] != metadata[field]:
                raise ValueError(f'Built plugin metadata differs: {field}')
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('plugin')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(package_plugin(args.plugin, args.output))
