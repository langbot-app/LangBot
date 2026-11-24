import io
from pathlib import Path
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
import zipfile

import yaml


def package_archive(data, sha, subdir):
    with TemporaryDirectory() as temp, zipfile.ZipFile(io.BytesIO(data)) as archive:
        files = archive.infolist()
        if not files or len(files) > 10000 or sum(entry.file_size for entry in files) > 128 << 20:
            raise ValueError('GitHub archive exceeds extraction limits')
        top = files[0].filename.split('/')[0]
        if archive.comment != sha.encode() and not top.endswith('-' + sha):
            raise ValueError('GitHub archive commit does not match requested branch')
        for entry in files:
            parts = entry.filename.rstrip('/').split('/')
            if (
                parts[0] != top
                or any(part in {'', '.', '..'} for part in parts)
                or '\\' in entry.filename
                or ':' in entry.filename
            ):
                raise ValueError('Unsafe GitHub archive entry')
            if subdir and not entry.filename.startswith(f'{top}/{subdir}/'):
                continue
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError('Unsafe GitHub archive entry')
            archive.extract(entry, temp)
        top_dir = Path(temp, top).resolve()
        root = (top_dir / subdir).resolve()
        if not root.is_relative_to(top_dir) or not (root / 'manifest.yaml').is_file():
            raise ValueError('No manifest.yaml in requested plugin directory')
        manifest_path = root / 'manifest.yaml'
        manifest = yaml.safe_load(manifest_path.read_bytes())
        if (
            not isinstance(manifest, dict)
            or manifest.get('kind') != 'Plugin'
            or not isinstance(manifest.get('spec'), dict)
        ):
            raise ValueError('Expected a plugin manifest')
        if 'components' not in manifest['spec']:
            manifest['spec']['components'] = {}
            manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True), encoding='utf-8')
        for group in manifest['spec']['components'].values():
            paths = [*group.get('fromFiles', []), *(entry['path'] for entry in group.get('fromDirs', []))]
            for path in paths:
                if Path(path).is_absolute() or not (root / path).resolve().is_relative_to(root):
                    raise ValueError('Component path outside plugin directory')
        with TemporaryDirectory() as output:
            destination = Path(output, 'plugin.lbpkg')
            subprocess.run(
                [
                    sys.executable,
                    '-I',
                    '-m',
                    'langbot.pkg.plugin.github_archive',
                    str(destination),
                ],
                cwd=root,
                check=True,
                timeout=60,
            )
            return destination.read_bytes()


if __name__ == '__main__':
    from langbot_plugin.utils.packaging import build_plugin_package

    Path(sys.argv[1]).write_bytes(build_plugin_package('.')[0])
