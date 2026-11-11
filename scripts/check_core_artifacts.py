from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import tarfile
import zipfile


# Official plugins (plugins/) and the plugin SDK (sdk/) share this repository but
# are released independently; Core artifacts must never carry their sources.
INDEPENDENT_ROOTS = ('plugins', 'sdk')


def forbidden_member(name: str) -> bool:
    parts = PurePosixPath(name.replace('\\', '/')).parts
    return any(root in parts[:2] for root in INDEPENDENT_ROOTS) or name.endswith('.lbpkg')


def check_artifact(path: Path) -> None:
    if path.is_dir():
        names = [item.relative_to(path).as_posix() for item in path.rglob('*')]
    elif zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
    elif tarfile.is_tarfile(path):
        with tarfile.open(path) as archive:
            names = archive.getnames()
    else:
        raise ValueError(f'Unsupported Core artifact: {path}')
    forbidden = [name for name in names if forbidden_member(name)]
    if forbidden:
        raise ValueError(f'Plugin or SDK content in {path}: {forbidden[:10]}')
    print(f'Core artifact excludes official plugins and SDK: {path.name} ({len(names)} entries)')


def check_docker_archive(path: Path) -> None:
    with tarfile.open(path) as image:
        manifests = json.load(image.extractfile('manifest.json'))
        for manifest in manifests:
            for layer in manifest['Layers']:
                with tarfile.open(fileobj=image.extractfile(layer), mode='r|*') as contents:
                    for member in contents:
                        if forbidden_member(member.name):
                            raise ValueError(f'Plugin or SDK content in Docker layer {layer}: {member.name}')
    print(f'Docker image layers exclude official plugins and SDK: {path.name}')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--docker-archive', action='store_true')
    parser.add_argument('artifacts', type=Path, nargs='+')
    args = parser.parse_args()
    for artifact in args.artifacts:
        if args.docker_archive:
            check_docker_archive(artifact)
        else:
            check_artifact(artifact)


if __name__ == '__main__':
    main()
