"""Cloud-only WebUI notice banner resolved from the instance configuration.

The banner is a deployment statement, not a Workspace or tenant resource: it
describes the instance the browser is currently talking to, so it is exposed
through the unauthenticated ``/api/v1/system/info`` payload and only ever
resolved on Cloud deployments. OSS deployments never render it even when the
configuration block is present, which keeps self-hosters from inheriting copy
that only makes sense for the managed service.
"""

from __future__ import annotations

import re
from typing import Any

SUPPORTED_LEVELS = ('info', 'warning', 'maintenance')

DEFAULT_LEVEL = 'info'
DEFAULT_DEDICATED_URL = 'https://space.langbot.app/cloud?environment=dedicated'
DEFAULT_REPOSITORY_URL = 'https://github.com/langbot-app/LangBot'

# Copy is rendered as text, never as markup, so only the length is bounded.
MAX_CONTENT_CHARS = 600
MAX_URL_CHARS = 500
MAX_LANGUAGES = 8

_LANGUAGE_KEY_RE = re.compile(r'[^a-z0-9]+')
_SAFE_URL_PREFIXES = ('https://', 'http://')


def normalize_language_key(value: str) -> str:
    """Normalize a language tag to the ``zh_hans``/``en_us`` config key form.

    ``config.yaml`` cannot express dashes through the ``CLOUD__...`` environment
    override (the override namespace only splits on ``__``), so both the file
    and the environment expose languages with underscores. Browser locales and
    i18next codes use dashes, hence the normalization here.
    """

    return _LANGUAGE_KEY_RE.sub('_', value.strip().lower()).strip('_')


def _bounded_text(raw: Any, limit: int) -> str:
    if not isinstance(raw, str):
        return ''
    return raw.strip()[:limit]


def _bounded_url(raw: Any, fallback: str) -> str:
    candidate = _bounded_text(raw, MAX_URL_CHARS)
    if not candidate:
        return fallback
    if not candidate.lower().startswith(_SAFE_URL_PREFIXES):
        # Only absolute web URLs are rendered as links; anything else (for
        # example ``javascript:``) falls back to the canonical destination.
        return fallback
    return candidate


def _as_bool(raw: Any, fallback: bool) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if normalized in ('true', '1', 'yes', 'on'):
            return True
        if normalized in ('false', '0', 'no', 'off', ''):
            return False
    return fallback


def resolve_cloud_banner(ap) -> dict | None:
    """Return the sanitized banner payload, or ``None`` when it is not shown.

    ``None`` means "render nothing": either the deployment is not Cloud, the
    switch is off, or no content can be resolved for any language.
    """

    if getattr(getattr(ap, 'deployment', None), 'mode', None) != 'cloud':
        return None

    config = getattr(getattr(ap, 'instance_config', None), 'data', None) or {}
    if not isinstance(config, dict):
        return None
    section = config.get('cloud')
    if not isinstance(section, dict):
        return None
    raw_banner = section.get('banner')
    if not isinstance(raw_banner, dict):
        return None
    if not _as_bool(raw_banner.get('enabled', False), False):
        return None

    level = _bounded_text(raw_banner.get('level'), 32).lower() or DEFAULT_LEVEL
    if level not in SUPPORTED_LEVELS:
        level = DEFAULT_LEVEL

    content: dict[str, str] = {}
    raw_content = raw_banner.get('content')
    if isinstance(raw_content, dict):
        for language, text in list(raw_content.items())[:MAX_LANGUAGES]:
            if not isinstance(language, str):
                continue
            key = normalize_language_key(language)
            value = _bounded_text(text, MAX_CONTENT_CHARS)
            if key and value:
                content[key] = value

    return {
        'enabled': True,
        'level': level,
        'dismissible': _as_bool(raw_banner.get('dismissible', True), True),
        'show_links': _as_bool(raw_banner.get('show_links', True), True),
        'dedicated_url': _bounded_url(raw_banner.get('dedicated_url'), DEFAULT_DEDICATED_URL),
        'repository_url': _bounded_url(raw_banner.get('repository_url'), DEFAULT_REPOSITORY_URL),
        'content': content,
    }
