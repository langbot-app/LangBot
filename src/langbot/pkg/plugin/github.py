from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote, urlparse


_GITHUB_OWNER_PATTERN = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$')
_GITHUB_REPO_PATTERN = re.compile(r'^[A-Za-z0-9._-]{1,100}$')


def _positive_github_id(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f'{field_name} must be a positive GitHub identifier')
    try:
        identifier = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{field_name} must be a positive GitHub identifier') from exc
    if identifier <= 0 or str(value).strip() != str(identifier):
        raise ValueError(f'{field_name} must be a positive GitHub identifier')
    return identifier


def validate_github_release_asset_url(
    asset_url: object,
    *,
    owner: str,
    repo: str,
    release_tag: str,
) -> str:
    """Accept only a GitHub browser release URL tied to the requested release."""

    normalized_url = str(asset_url or '').strip()
    parsed = urlparse(normalized_url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError('asset_url has an invalid port') from exc
    if (
        parsed.scheme != 'https'
        or (parsed.hostname or '').lower() != 'github.com'
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.fragment
    ):
        raise ValueError('asset_url must be an HTTPS GitHub release asset URL')
    decoded_path = unquote(parsed.path)
    expected_prefix = f'/{owner}/{repo}/releases/download/{release_tag}/'
    if not decoded_path.casefold().startswith(
        f'/{owner}/{repo}/releases/download/'.casefold()
    ) or not decoded_path.startswith(expected_prefix):
        raise ValueError('asset_url does not match the requested GitHub release')
    if decoded_path == expected_prefix or decoded_path.endswith('/'):
        raise ValueError('asset_url must identify a GitHub release asset')
    return normalized_url


def validate_github_plugin_install_info(install_info: dict[str, Any]) -> dict[str, Any]:
    """Normalize a GitHub install request without trusting a tenant-provided URL."""

    owner = str(install_info.get('owner') or '').strip()
    repo = str(install_info.get('repo') or '').strip()
    release_tag = str(install_info.get('release_tag') or '').strip()
    if _GITHUB_OWNER_PATTERN.fullmatch(owner) is None:
        raise ValueError('owner must be a valid GitHub repository owner')
    if _GITHUB_REPO_PATTERN.fullmatch(repo) is None:
        raise ValueError('repo must be a valid GitHub repository name')
    if not release_tag or '\x00' in release_tag or len(release_tag) > 255:
        raise ValueError('release_tag must identify a GitHub release')

    release_id_value = install_info.get('release_id')
    asset_id_value = install_info.get('asset_id')
    normalized = dict(install_info)
    normalized.update(
        {
            'owner': owner,
            'repo': repo,
            'release_tag': release_tag,
            'github_url': f'https://github.com/{owner}/{repo}',
        }
    )
    if release_id_value is not None or asset_id_value is not None:
        if release_id_value is None or asset_id_value is None:
            raise ValueError('release_id and asset_id must be provided together')
        normalized['release_id'] = _positive_github_id(release_id_value, 'release_id')
        normalized['asset_id'] = _positive_github_id(asset_id_value, 'asset_id')
        normalized.pop('asset_url', None)
        return normalized

    normalized['asset_url'] = validate_github_release_asset_url(
        install_info.get('asset_url'),
        owner=owner,
        repo=repo,
        release_tag=release_tag,
    )
    return normalized
