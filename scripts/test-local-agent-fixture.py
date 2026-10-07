#!/usr/bin/env python3
"""Resolve the latest official LocalAgent from Space and prepare its E2E fixture.

Resolution always contacts Space. Cache only the version/checksum-resolved
archive, preserving its certification envelope for normal Runtime admission.
The saved resolution JSON can also replay the exact package used by a CI run.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import time
import zipfile

import httpx
import yaml

SPACE_URL = 'https://space.langbot.app'
PLUGIN_AUTHOR = 'langbot-team'
PLUGIN_NAME = 'LocalAgent'
VERSIONS_URL = f'{SPACE_URL}/api/v1/marketplace/plugins/{PLUGIN_AUTHOR}/{PLUGIN_NAME}/versions'
MAX_PACKAGE_BYTES = 16 * 1024 * 1024
MAX_METADATA_BYTES = 1024 * 1024


def download_package(url: str, *, max_bytes: int = MAX_PACKAGE_BYTES) -> bytes:
    """Use Core's HTTP client with bounded responses and network retries."""
    for attempt in range(3):
        try:
            with httpx.stream('GET', url, timeout=30, follow_redirects=True) as response:
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise ValueError(f'Space response exceeds the {max_bytes}-byte limit')
            return bytes(body)
        except httpx.HTTPError as exc:
            if attempt == 2:
                raise RuntimeError(f'Cannot fetch LocalAgent fixture from Space: {url}: {exc}') from exc
            time.sleep(attempt + 1)
    raise AssertionError('Unreachable download retry state')


def resolve_latest() -> dict:
    """Select the first published version, matching Core's marketplace resolver."""
    payload = json.loads(download_package(VERSIONS_URL, max_bytes=MAX_METADATA_BYTES))
    if payload.get('code') != 0:
        raise ValueError('Space did not return a successful plugin version response')
    versions = payload.get('data', {}).get('versions', [])
    if not versions or not isinstance(versions, list) or not isinstance(versions[0], dict):
        raise ValueError('Space returned no LocalAgent versions')
    latest = versions[0]
    version = latest.get('version', '')
    checksum = latest.get('checksum', '')
    if not isinstance(version, str) or not re.fullmatch(r'[A-Za-z0-9._+-]+', version):
        raise ValueError('Space returned an invalid LocalAgent version')
    if not isinstance(checksum, str) or not re.fullmatch(r'[a-fA-F0-9]{64}', checksum):
        raise ValueError('Space did not provide a valid archive SHA256 checksum')
    if latest.get('plugin_id') != f'{PLUGIN_AUTHOR}/{PLUGIN_NAME}' or latest.get('status') != 'live':
        raise ValueError('Latest Space entry is not the published LocalAgent plugin')
    return {
        'author': PLUGIN_AUTHOR,
        'name': PLUGIN_NAME,
        'version': version,
        'url': f'{SPACE_URL}/api/v1/marketplace/plugins/download/{PLUGIN_AUTHOR}/{PLUGIN_NAME}/{version}',
        'sha256': checksum.lower(),
        'resolved_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'versions_url': VERSIONS_URL,
    }


def validate_package(package: bytes, resolution: dict) -> None:
    """Check the original archive bytes and manifest identity before installation."""
    actual = hashlib.sha256(package).hexdigest()
    if actual != resolution['sha256']:
        raise ValueError(f'LocalAgent SHA256 mismatch: expected {resolution["sha256"]}, got {actual}')
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        manifest = yaml.safe_load(archive.read('manifest.yaml'))
    metadata = manifest['metadata']
    for field in ('author', 'name', 'version'):
        if str(metadata[field]) != resolution[field]:
            raise ValueError(f'LocalAgent manifest {field} does not match the resolved artifact')


def fetch_package(destination: Path, resolution: dict) -> Path:
    """Reuse only a verified resolved archive or download it atomically."""
    if destination.is_file():
        try:
            validate_package(destination.read_bytes(), resolution)
            return destination
        except (ValueError, KeyError, zipfile.BadZipFile):
            print('Cached LocalAgent package does not match this run; downloading resolved artifact', file=sys.stderr)

    package = download_package(resolution['url'])
    validate_package(package, resolution)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.tmp')
    temporary.write_bytes(package)
    temporary.replace(destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    resolve = commands.add_parser('resolve', help='Query Space latest and save replay metadata; never cached')
    resolve.add_argument('resolution', type=Path)
    resolve.add_argument('--github-output', type=Path, help='Write the resolved artifact cache key for Actions')
    fetch = commands.add_parser('fetch', help='Download/verify the artifact described by saved resolution metadata')
    fetch.add_argument('resolution', type=Path)
    fetch.add_argument('destination', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'resolve':
            resolution = resolve_latest()
            args.resolution.parent.mkdir(parents=True, exist_ok=True)
            args.resolution.write_text(json.dumps(resolution, indent=2) + '\n', encoding='utf-8')
            if args.github_output:
                with args.github_output.open('a', encoding='utf-8') as output:
                    output.write(f'cache_key={resolution["version"]}-{resolution["sha256"]}\n')
            print(json.dumps(resolution, indent=2))
        else:
            resolution = json.loads(args.resolution.read_text(encoding='utf-8'))
            package = fetch_package(args.destination.resolve(), resolution)
            print(f'{resolution["author"]}/{resolution["name"]}:{resolution["version"]} verified at {package}')
            print(f'Archive SHA256: {resolution["sha256"]}')
    except (OSError, ValueError, KeyError, RuntimeError, zipfile.BadZipFile) as exc:
        parser.exit(1, f'LocalAgent fixture provisioning failed: {exc}\n')


if __name__ == '__main__':
    main()
