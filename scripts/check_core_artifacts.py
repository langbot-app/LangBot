from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import tarfile
import zipfile


# Source deployments carry the SDK; the independently installed wheel must not
# own files from the langbot-plugin distribution.
SDK_SOURCE_FILES = (
    'pyproject.toml',
    'README.md',
    'LICENSE',
    'src/langbot_plugin/__init__.py',
    'src/langbot_plugin/box/client.py',
    'src/langbot_plugin/runtime/app.py',
    'src/langbot_plugin/assets/templates/.github/workflows/release.yml.example',
    'src/langbot_plugin/assets/templates/.vscode/launch.json.example',
    'src/langbot_plugin/assets/templates/.gitignore.example',
    'src/langbot_plugin/assets/templates/.env.example.example',
)


def forbidden_member(name: str, *, source: bool = False) -> bool:
    parts = PurePosixPath(name.replace('\\', '/').lstrip('/')).parts
    roots = ('plugins',) if source else ('plugins', 'sdk')
    return any(root in parts[:2] for root in roots) or name.endswith('.lbpkg')


def check_sdk_source(names: list[str], path: Path) -> None:
    files = {PurePosixPath(name.replace('\\', '/').lstrip('/')).as_posix() for name in names}
    roots = [
        name.removesuffix('pyproject.toml')
        for name in files
        if PurePosixPath(name).parts[-2:] == ('sdk', 'pyproject.toml')
    ]
    if not roots:
        raise ValueError(f'Core source artifact is missing the in-tree SDK: {path}')
    for root in roots:
        missing = [root + name for name in SDK_SOURCE_FILES if root + name not in files]
        if missing:
            raise ValueError(f'Incomplete in-tree SDK in {path}: {missing}')


def check_artifact(path: Path, *, source: bool = False) -> None:
    if path.is_dir():
        names = [item.relative_to(path).as_posix() for item in path.rglob('*')]
        files = [item.relative_to(path).as_posix() for item in path.rglob('*') if item.is_file()]
    elif zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            files = [member.filename for member in archive.infolist() if not member.is_dir()]
    elif tarfile.is_tarfile(path):
        with tarfile.open(path) as archive:
            names = archive.getnames()
            files = [member.name for member in archive.getmembers() if member.isfile()]
    else:
        raise ValueError(f'Unsupported Core artifact: {path}')
    if path.suffix == '.whl' and source:
        raise ValueError('Core wheels cannot carry the in-tree SDK; --source applies to source deployments')
    forbidden = [name for name in names if forbidden_member(name, source=source)]
    if path.suffix == '.whl':
        forbidden.extend(
            name
            for name in names
            if any(
                part in {'langbot_plugin', 'langbot_plugin.py'} or part.startswith('langbot_plugin-')
                for part in PurePosixPath(name).parts
            )
        )
    if forbidden:
        raise ValueError(f'Unexpected plugin or SDK content in {path}: {forbidden[:10]}')
    if source:
        check_sdk_source(files, path)
    print(f'Core {"source" if source else "package"} artifact verified: {path.name} ({len(names)} entries)')


def check_docker_archive(path: Path, *, source: bool = False) -> None:
    with tarfile.open(path) as image:
        manifests = json.load(image.extractfile('manifest.json'))
        for manifest in manifests:
            files = set()
            for layer in manifest['Layers']:
                with tarfile.open(fileobj=image.extractfile(layer), mode='r|*') as contents:
                    for member in contents:
                        if forbidden_member(member.name, source=source):
                            raise ValueError(f'Unexpected plugin or SDK content in Docker layer {layer}: {member.name}')
                        if member.isfile():
                            files.add(member.name)
            if source:
                check_sdk_source(list(files), path)
    print(f'Docker image package boundary verified: {path.name}')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--docker-archive', action='store_true')
    parser.add_argument('--source', action='store_true', help='Require the in-tree SDK in a source deployment.')
    parser.add_argument('artifacts', type=Path, nargs='+')
    args = parser.parse_args()
    for artifact in args.artifacts:
        if args.docker_archive:
            check_docker_archive(artifact, source=args.source)
        else:
            check_artifact(artifact, source=args.source)


if __name__ == '__main__':
    main()
