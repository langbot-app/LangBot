from __future__ import annotations

import copy
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SECRET_MASK = '***'
_MISSING_SECRET = object()

_SENSITIVE_NAMES = frozenset(
    {
        'api_key',
        'api_keys',
        'apikey',
        'apikeys',
        'auth',
        'authorization',
        'cookie',
        'credentials',
        'database_url',
        'dsn',
        'header_value',
        'key',
        'proxy_authorization',
        'set_cookie',
        'webhook_url',
    }
)
_SENSITIVE_TOKENS = frozenset(
    {
        'apikey',
        'credential',
        'credentials',
        'passwd',
        'password',
        'secret',
        'token',
    }
)
_KEY_QUALIFIERS = frozenset(
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
_SENSITIVE_URL_QUERY_NAMES = frozenset(
    {
        'code',
        'credential',
        'credentials',
        'password',
        'passwd',
        'sig',
        'signature',
    }
)


def _normalize_key(key: object) -> str:
    value = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', str(key or ''))
    return re.sub(r'[^a-zA-Z0-9]+', '_', value).strip('_').lower()


def is_sensitive_key(key: object) -> bool:
    """Return whether a configuration key conventionally carries a secret."""

    normalized = _normalize_key(key)
    if normalized in _SENSITIVE_NAMES:
        return True
    tokens = frozenset(token for token in normalized.split('_') if token)
    if tokens & _SENSITIVE_TOKENS:
        return True
    return bool(tokens & {'key', 'keys'}) and bool(tokens & _KEY_QUALIFIERS)


def is_url_key(key: object) -> bool:
    """Return whether a configuration field conventionally carries a URL."""

    normalized = _normalize_key(key)
    return normalized == 'url' or normalized.endswith('_url')


def _is_sensitive_url_query_key(key: object) -> bool:
    normalized = _normalize_key(key)
    return (
        is_sensitive_key(key) or normalized in _SENSITIVE_URL_QUERY_NAMES or normalized.endswith(('_sig', '_signature'))
    )


def _redact_url_string(value: str) -> str:
    if not value:
        return value
    try:
        parsed = urlsplit(value)
        netloc = parsed.netloc
        if '@' in netloc:
            _, host = netloc.rsplit('@', 1)
            netloc = f'{SECRET_MASK}@{host}'
        query = urlencode(
            [
                (key, SECRET_MASK if _is_sensitive_url_query_key(key) and item else item)
                for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            ],
            doseq=True,
            safe='*',
        )
        return urlunsplit((parsed.scheme, netloc, parsed.path, query, parsed.fragment))
    except (TypeError, ValueError):
        # A malformed URL cannot be safely decomposed, so fail closed.
        return SECRET_MASK


def redact_url_secrets(value):
    """Redact URL userinfo and credential-like query values."""

    if isinstance(value, str):
        return _redact_url_string(value)
    if isinstance(value, list):
        return [redact_url_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_url_secrets(item) for item in value)
    return copy.deepcopy(value)


def _contains_url_secret_placeholder(value) -> bool:
    if isinstance(value, str):
        if value == SECRET_MASK:
            return True
        try:
            parsed = urlsplit(value)
            if '@' in parsed.netloc and SECRET_MASK in parsed.netloc.rsplit('@', 1)[0]:
                return True
            return any(
                item == SECRET_MASK and _is_sensitive_url_query_key(key)
                for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            )
        except (TypeError, ValueError):
            return False
    if isinstance(value, (list, tuple)):
        return any(_contains_url_secret_placeholder(item) for item in value)
    return False


def _restore_url_string(value: str, current_value) -> str:
    if value == SECRET_MASK:
        if current_value is _MISSING_SECRET:
            raise ValueError('Masked URL secret has no existing value')
        return copy.deepcopy(current_value)

    try:
        submitted = urlsplit(value)
    except (TypeError, ValueError):
        return value

    current = None
    if isinstance(current_value, str):
        try:
            current = urlsplit(current_value)
        except (TypeError, ValueError):
            current = None

    netloc = submitted.netloc
    if '@' in netloc:
        submitted_userinfo, host = netloc.rsplit('@', 1)
        if SECRET_MASK in submitted_userinfo:
            if current is None or '@' not in current.netloc:
                raise ValueError('Masked URL userinfo has no existing value')
            current_userinfo, _ = current.netloc.rsplit('@', 1)
            netloc = f'{current_userinfo}@{host}'

    current_query: dict[str, list[str]] = {}
    if current is not None:
        for key, item in parse_qsl(current.query, keep_blank_values=True):
            current_query.setdefault(_normalize_key(key), []).append(item)
    consumed: dict[str, int] = {}
    restored_query: list[tuple[str, str]] = []
    for key, item in parse_qsl(submitted.query, keep_blank_values=True):
        normalized = _normalize_key(key)
        if item == SECRET_MASK and _is_sensitive_url_query_key(key):
            index = consumed.get(normalized, 0)
            candidates = current_query.get(normalized, [])
            if index >= len(candidates):
                raise ValueError('Masked URL query secret has no existing value')
            item = candidates[index]
            consumed[normalized] = index + 1
        restored_query.append((key, item))

    return urlunsplit(
        (
            submitted.scheme,
            netloc,
            submitted.path,
            urlencode(restored_query, doseq=True, safe='*'),
            submitted.fragment,
        )
    )


def restore_url_secret_placeholders(value, current_value=_MISSING_SECRET):
    """Restore URL placeholders from the corresponding persisted URL."""

    if isinstance(value, str):
        return _restore_url_string(value, current_value)
    if isinstance(value, list):
        current_items = current_value if isinstance(current_value, (list, tuple)) else ()
        return [
            restore_url_secret_placeholders(
                item,
                current_items[index] if index < len(current_items) else _MISSING_SECRET,
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, tuple):
        current_items = current_value if isinstance(current_value, (list, tuple)) else ()
        return tuple(
            restore_url_secret_placeholders(
                item,
                current_items[index] if index < len(current_items) else _MISSING_SECRET,
            )
            for index, item in enumerate(value)
        )
    return copy.deepcopy(value)


def mask_secret_value(value):
    """Return a shape-preserving copy whose non-empty leaves are masked."""

    if isinstance(value, dict):
        return {key: mask_secret_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [mask_secret_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(mask_secret_value(item) for item in value)
    if value is None or value == '':
        return value
    return SECRET_MASK


def redact_secrets(value):
    """Return a recursively redacted copy without mutating the source value."""

    if isinstance(value, dict):
        return {
            key: (
                mask_secret_value(item)
                if is_sensitive_key(key)
                else redact_url_secrets(item)
                if is_url_key(key)
                else redact_secrets(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    return copy.deepcopy(value)


def restore_secret_placeholders(value, current_value=_MISSING_SECRET, *, sensitive: bool = False):
    """Restore masked leaves from existing data before a management write.

    ``***`` is a reserved placeholder only inside a sensitive field. A masked
    leaf without an existing counterpart is rejected so it can never become a
    persisted credential. Empty values and explicit replacements pass through.
    """

    if sensitive and value == SECRET_MASK:
        if current_value is _MISSING_SECRET:
            raise ValueError('Masked secret has no existing value')
        return copy.deepcopy(current_value)
    if isinstance(value, dict):
        current_mapping = current_value if isinstance(current_value, dict) else {}
        return {
            key: (
                restore_url_secret_placeholders(
                    item,
                    current_mapping.get(key, _MISSING_SECRET),
                )
                if not sensitive and not is_sensitive_key(key) and is_url_key(key)
                else restore_secret_placeholders(
                    item,
                    current_mapping.get(key, _MISSING_SECRET),
                    sensitive=sensitive or is_sensitive_key(key),
                )
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        current_items = current_value if isinstance(current_value, (list, tuple)) else ()
        return [
            restore_secret_placeholders(
                item,
                current_items[index] if index < len(current_items) else _MISSING_SECRET,
                sensitive=sensitive,
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, tuple):
        current_items = current_value if isinstance(current_value, (list, tuple)) else ()
        return tuple(
            restore_secret_placeholders(
                item,
                current_items[index] if index < len(current_items) else _MISSING_SECRET,
                sensitive=sensitive,
            )
            for index, item in enumerate(value)
        )
    return copy.deepcopy(value)


def contains_secret_placeholder(value, *, sensitive: bool = False) -> bool:
    """Return whether ``value`` contains a meaningful masked secret leaf."""

    if sensitive and value == SECRET_MASK:
        return True
    if isinstance(value, dict):
        return any(
            (
                _contains_url_secret_placeholder(item)
                if not sensitive and not is_sensitive_key(key) and is_url_key(key)
                else contains_secret_placeholder(item, sensitive=sensitive or is_sensitive_key(key))
            )
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(contains_secret_placeholder(item, sensitive=sensitive) for item in value)
    return False
