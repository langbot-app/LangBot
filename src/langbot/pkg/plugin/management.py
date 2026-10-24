"""Shared plugin management validation and secret handling."""

from __future__ import annotations

import copy
import posixpath
import re
from urllib.parse import urlparse


_SECRET_MASK = '***'
_MISSING_SECRET = object()
_SENSITIVE_CONFIG_NAMES = frozenset(
    {
        'api_key',
        'apikey',
        'auth',
        'authorization',
        'cookie',
        'credentials',
        'database_url',
        'dsn',
        'key',
        'proxy_authorization',
        'set_cookie',
    }
)
_SENSITIVE_CONFIG_TOKENS = frozenset(
    {
        'credential',
        'credentials',
        'passwd',
        'password',
        'secret',
        'token',
    }
)
_SENSITIVE_KEY_QUALIFIERS = frozenset(
    {
        'access',
        'api',
        'auth',
        'bearer',
        'client',
        'debug',
        'encryption',
        'private',
        'signing',
    }
)


def _normalize_config_key(key: object) -> str:
    value = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', str(key or ''))
    return re.sub(r'[^a-zA-Z0-9]+', '_', value).strip('_').lower()


def _is_sensitive_config_key(key: object) -> bool:
    normalized = _normalize_config_key(key)
    if normalized in _SENSITIVE_CONFIG_NAMES:
        return True
    tokens = frozenset(token for token in normalized.split('_') if token)
    if tokens & _SENSITIVE_CONFIG_TOKENS:
        return True
    return 'key' in tokens and bool(tokens & _SENSITIVE_KEY_QUALIFIERS)


def _mask_secret_structure(value):
    """Mask every non-empty leaf while preserving container structure."""

    if isinstance(value, dict):
        return {key: _mask_secret_structure(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_mask_secret_structure(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_mask_secret_structure(item) for item in value)
    if value is None or value == '':
        return value
    return _SECRET_MASK


def redact_plugin_secrets(value):
    """Return a recursively redacted copy of plugin-facing data."""

    if isinstance(value, dict):
        return {
            key: (_mask_secret_structure(item) if _is_sensitive_config_key(key) else redact_plugin_secrets(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_plugin_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_plugin_secrets(item) for item in value)
    return value


def restore_plugin_secret_placeholders(value, current_value=_MISSING_SECRET, *, sensitive: bool = False):
    """Restore masked leaves from the current config before a management write."""

    if sensitive and value == _SECRET_MASK:
        if current_value is _MISSING_SECRET:
            raise ValueError('Masked plugin secret has no existing value')
        return copy.deepcopy(current_value)
    if isinstance(value, dict):
        current_mapping = current_value if isinstance(current_value, dict) else {}
        return {
            key: restore_plugin_secret_placeholders(
                item,
                current_mapping.get(key, _MISSING_SECRET),
                sensitive=sensitive or _is_sensitive_config_key(key),
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        current_items = current_value if isinstance(current_value, (list, tuple)) else ()
        return [
            restore_plugin_secret_placeholders(
                item,
                current_items[index] if index < len(current_items) else _MISSING_SECRET,
                sensitive=sensitive,
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, tuple):
        current_items = current_value if isinstance(current_value, (list, tuple)) else ()
        return tuple(
            restore_plugin_secret_placeholders(
                item,
                current_items[index] if index < len(current_items) else _MISSING_SECRET,
                sensitive=sensitive,
            )
            for index, item in enumerate(value)
        )
    return value


def normalize_plugin_asset_path(filepath: str) -> str | None:
    filepath = filepath.replace('\\', '/')
    if filepath.startswith('/'):
        return None

    normalized = posixpath.normpath(filepath)
    if normalized == '.' or normalized.startswith('../') or normalized == '..':
        return None

    if normalized.startswith('components/pages/'):
        return normalized

    return f'assets/{normalized}'


def _normalize_archive_path(path: str) -> str:
    normalized = str(path or '').replace('\\', '/').strip('/')
    return posixpath.normpath(normalized) if normalized else ''


def _component_source_path(entry) -> str:
    if isinstance(entry, dict):
        return _normalize_archive_path(entry.get('path') or '')
    return _normalize_archive_path(str(entry or ''))


def _count_component_configs(component_config, archive_names: list[str]) -> int:
    normalized_names = [_normalize_archive_path(name) for name in archive_names]
    component_files: set[str] = set()

    if isinstance(component_config, list):
        return len(component_config)
    if not isinstance(component_config, dict):
        return 1 if component_config else 0

    for entry in component_config.get('fromFiles') or []:
        source_path = _component_source_path(entry)
        if source_path and source_path in normalized_names:
            component_files.add(source_path)

    for entry in component_config.get('fromDirs') or []:
        source_dir = _component_source_path(entry).rstrip('/')
        if not source_dir:
            continue
        prefix = f'{source_dir}/'
        for archive_name in normalized_names:
            if not archive_name.startswith(prefix):
                continue
            if archive_name.lower().endswith(('.yaml', '.yml')):
                component_files.add(archive_name)

    if component_files:
        return len(component_files)

    return 1 if any(key in component_config for key in ('path', 'name', 'kind')) else 0


def count_plugin_components(components, archive_names: list[str]) -> dict[str, int]:
    if not isinstance(components, dict):
        return {}

    component_counts: dict[str, int] = {}
    for kind, component_config in components.items():
        count = _count_component_configs(component_config, archive_names)
        if count > 0:
            component_counts[str(kind)] = count
    return component_counts


def parse_github_repo_url(repo_url: str) -> dict | None:
    raw_url = str(repo_url or '').strip()
    if not raw_url:
        return None

    if not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', raw_url):
        raw_url = f'https://{raw_url}'

    parsed = urlparse(raw_url)
    if parsed.netloc.lower() not in ('github.com', 'www.github.com'):
        return None

    parts = [part for part in parsed.path.strip('/').split('/') if part]
    if len(parts) < 2:
        return None

    owner = parts[0]
    repo = parts[1]
    if repo.endswith('.git'):
        repo = repo[:-4]
    if not owner or not repo:
        return None

    ref = ''
    subdir = ''
    if len(parts) >= 4 and parts[2] in ('tree', 'blob'):
        ref = parts[3]
        subdir = '/'.join(parts[4:]).strip('/')

    return {
        'owner': owner,
        'repo': repo,
        'ref': ref,
        'subdir': subdir,
    }
