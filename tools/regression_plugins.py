"""Prepare source or published regression plugins and verify installed artifacts."""

from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

import yaml


MARKETPLACE = 'https://space.langbot.app'
PLUGIN_IDS = ('langbot-team/LocalAgent', 'langbot-team/LangRAG', 'langbot-team/GeneralParsers')
PLUGIN_PATHS = ('Runner/LocalAgent', 'KnowledgeEngine/LangRAG', 'misc/GeneralParsers')
METADATA_LIMIT = 1024 * 1024
PACKAGE_LIMIT = 64 * 1024 * 1024


def write_manifest(directory, manifest):
    path = directory / 'manifest.json'
    temporary = directory / 'manifest.json.tmp'
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def fetch(url, limit):
    request = urllib.request.Request(url, headers={'User-Agent': 'LangBot-regression/1'})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status != 200:
                raise RuntimeError(f'Marketplace request failed: HTTP {response.status}: {url}')
            content = response.read(limit + 1)
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError(f'Marketplace request failed: {url}: {exc}') from exc
    if len(content) > limit:
        raise ValueError(f'Marketplace response exceeds {limit} bytes: {url}')
    return content


def release_version(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._+-]{0,127}', value):
        raise ValueError(f'Invalid published plugin version: {value!r}')
    return value


def replay_versions(path):
    manifest = json.loads(Path(path).read_text())
    if not isinstance(manifest, dict) or manifest.get('version') != 1 or manifest.get('marketplace') != MARKETPLACE:
        raise ValueError('Replay requires a version 1 official marketplace manifest')
    entries = manifest.get('plugins')
    if not isinstance(entries, list) or len(entries) != len(PLUGIN_IDS):
        raise ValueError('Replay manifest must contain the three regression plugins')
    selected = {}
    for entry in entries:
        if not isinstance(entry, dict) or entry.get('id') not in PLUGIN_IDS or entry['id'] in selected:
            raise ValueError('Replay manifest has an unknown or duplicate plugin')
        version = release_version(entry.get('version'))
        digest = entry.get('sha256')
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Replay manifest requires a package sha256 for every plugin')
        selected[entry['id']] = (version, digest)
    return selected


def check_archive(content, plugin_id, version):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if archive.namelist().count('manifest.yaml') != 1:
                raise ValueError('package needs exactly one root manifest.yaml')
            info = archive.getinfo('manifest.yaml')
            if info.file_size > METADATA_LIMIT:
                raise ValueError('package manifest exceeds the metadata limit')
            manifest = yaml.safe_load(archive.read(info))
        metadata = manifest.get('metadata') if isinstance(manifest, dict) else None
        if (
            not isinstance(metadata, dict)
            or manifest.get('kind') != 'Plugin'
            or f'{metadata.get("author")}/{metadata.get("name")}' != plugin_id
            or metadata.get('version') != version
        ):
            raise ValueError('package manifest identity/version differs from the selected release')
    except (zipfile.BadZipFile, yaml.YAMLError, KeyError, ValueError, RuntimeError) as exc:
        raise ValueError(f'Invalid plugin package for {plugin_id}@{version}: {exc}') from exc


def prepare_published_plugins(directory, replay=None):
    """Download releases; replay reads only identities, versions and hashes, never supplied URLs."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    selected = replay_versions(replay) if replay is not None else None
    manifest = {
        'version': 1,
        'marketplace': MARKETPLACE,
        'resolved_at': datetime.now(timezone.utc).isoformat(),
        'selection': 'replay' if selected is not None else 'latest',
        'plugins': [],
    }
    write_manifest(directory, manifest)
    for plugin_id in PLUGIN_IDS:
        metadata_url = f'{MARKETPLACE}/api/v1/marketplace/plugins/{plugin_id}'
        if selected is None:
            payload = json.loads(fetch(metadata_url, METADATA_LIMIT))
            data = payload.get('data') if isinstance(payload, dict) else None
            plugin = data.get('plugin') if isinstance(data, dict) else None
            if (
                not isinstance(payload, dict)
                or payload.get('code') != 0
                or not isinstance(plugin, dict)
                or plugin.get('plugin_id') != plugin_id
                or f'{plugin.get("author")}/{plugin.get("name")}' != plugin_id
                or plugin.get('status') != 'live'
                or plugin.get('deleted_at') is not None
            ):
                raise ValueError(f'Marketplace did not return a live published plugin: {plugin_id}')
            version = release_version(plugin.get('latest_version'))
        else:
            version = selected[plugin_id][0]
        manifest['plugins'].append(
            {
                'id': plugin_id,
                'version': version,
                'metadata_url': metadata_url,
                'package_url': f'{MARKETPLACE}/api/v1/marketplace/plugins/download/{plugin_id}/{version}',
                'archive': f'{plugin_id.split("/")[1]}-{version}.zip',
            }
        )
        write_manifest(directory, manifest)

    for entry in manifest['plugins']:
        content = fetch(entry['package_url'], PACKAGE_LIMIT)
        digest = hashlib.sha256(content).hexdigest()
        if selected is not None and digest != selected[entry['id']][1]:
            raise ValueError(f'Replay package sha256 changed: {entry["id"]}@{entry["version"]}')
        check_archive(content, entry['id'], entry['version'])
        (directory / entry['archive']).write_bytes(content)
        entry['sha256'] = digest
        write_manifest(directory, manifest)
    return manifest


def prepare_source_plugins(directory, source, extra_plugins=()):
    """Build selected plugin directories with the SDK CLI, without publishing."""
    directory, source = Path(directory).resolve(), Path(source).resolve()
    paths = [*PLUGIN_PATHS, *extra_plugins]
    if len(paths) != len(set(paths)):
        raise ValueError('Duplicate source plugin selection')
    for path in paths:
        if (
            not re.fullmatch(r'(Runner|KnowledgeEngine|misc)/[A-Za-z0-9_.-]+', path)
            or not (source / path).resolve().is_relative_to(source)
            or not (source / path / 'manifest.yaml').is_file()
        ):
            raise ValueError(f'Invalid source plugin path: {path}')
    directory.mkdir(parents=True, exist_ok=False)
    manifest = {'version': 1, 'selection': 'source', 'plugins': []}
    write_manifest(directory, manifest)
    for path in paths:
        metadata = yaml.safe_load((source / path / 'manifest.yaml').read_text())['metadata']
        plugin_id = f'{metadata["author"]}/{metadata["name"]}'
        if any(entry['id'] == plugin_id for entry in manifest['plugins']):
            raise ValueError(f'Duplicate source plugin identity: {plugin_id}')
        if not all(re.fullmatch(r'[A-Za-z0-9_.-]+', metadata[key]) for key in ('author', 'name')):
            raise ValueError(f'Invalid source plugin identity: {plugin_id}')
        version = release_version(metadata['version'])
        entry = {
            'id': plugin_id,
            'version': version,
            'source': path,
            'archive': f'{metadata["author"]}-{metadata["name"]}-{version}.lbpkg',
        }
        manifest['plugins'].append(entry)
        write_manifest(directory, manifest)
        with tempfile.TemporaryDirectory() as temporary:
            package_source = Path(temporary) / 'plugin'
            shutil.copytree(
                source / path, package_source, ignore=shutil.ignore_patterns('.git', '.venv*', '__pycache__')
            )
            with (directory / f'{metadata["name"]}-build.log').open('w') as log:
                subprocess.run(
                    [sys.executable, '-m', 'langbot_plugin.cli.__init__', 'build', '--output', str(directory)],
                    cwd=package_source,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=180,
                )
        content = (directory / entry['archive']).read_bytes()
        check_archive(content, plugin_id, version)
        entry['sha256'] = hashlib.sha256(content).hexdigest()
        write_manifest(directory, manifest)
    return manifest


def install_plugins(call, directory, manifest):
    """Install recorded packages and require exact, initialized CLI readback."""
    directory = Path(directory)
    for entry in manifest['plugins']:
        archive = directory / entry['archive']
        if hashlib.sha256(archive.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError(f'Plugin archive changed before installation: {entry["id"]}')
        try:
            call(['plugin', 'install', 'local', '--file', str(archive), '--wait'])
        except RuntimeError as exc:
            raise RuntimeError(f'Plugin install failed: {entry["id"]}@{entry["version"]}: {exc}') from exc
        response = call(['plugin', 'list'])
        plugins = response.get('plugins') if isinstance(response, dict) else None
        if not isinstance(plugins, list) or any(not isinstance(item, dict) for item in plugins):
            raise RuntimeError('Plugin readback did not return a plugin list')
        matches = [item for item in plugins if f'{item.get("author")}/{item.get("name")}' == entry['id']]
        entry['installed'] = [{key: item.get(key) for key in ('version', 'enabled', 'status')} for item in matches]
        write_manifest(directory, manifest)
        if (
            len(matches) != 1
            or matches[0].get('version') != entry['version']
            or matches[0].get('enabled') is not True
            or matches[0].get('status') != 'initialized'
        ):
            raise RuntimeError(f'Plugin is not ready at the selected version: {entry["id"]}: {entry["installed"]}')
